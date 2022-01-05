# TODO:
# sfn logging (not yet supported by aws provider)

terraform {
  required_version = ">= 0.12"
  required_providers {
    aws = ">= 2.60, < 4.0"
    archive = "~> 1.3"
  }
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  region = data.aws_region.current.name
  account_id = data.aws_caller_identity.current.account_id
}

## State Machine

resource "aws_sfn_state_machine" "this" {
  name = "eks-nodegroup-updater-${var.cluster_name}"
  role_arn = aws_iam_role.sfn.arn
  definition = templatefile("${path.module}/statemachine/nodegroup_updater.asl.json", {
    ClusterName = var.cluster_name
    GetNodegroupsNeedingUpdateFunctionArn = aws_lambda_function.lambda["get_updatable_nodegroups"].arn
    UpdateNodegroupFunctionArn = aws_lambda_function.lambda["update_nodegroup"].arn
    GetNodegroupUpdateStatusFunctionArn = aws_lambda_function.lambda["get_nodegroup_update_status"].arn
    ErrorNotificationSNSTopicArn = var.error_notification_sns_topic_arn
  })
}

resource "aws_iam_role" "sfn" {
  name = "eks-nodegroup-updater-sfn-${var.cluster_name}"

  assume_role_policy = data.aws_iam_policy_document.sfn_assume_role.json

  tags = {}
}

data "aws_iam_policy_document" "sfn_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "sfn" {
  name = "policy"
  role = aws_iam_role.sfn.id
  policy = data.aws_iam_policy_document.sfn.json
}

data "aws_iam_policy_document" "sfn" {
  statement {
    actions = ["lambda:InvokeFunction"]
    resources = [
      aws_lambda_function.lambda["get_updatable_nodegroups"].arn,
      aws_lambda_function.lambda["update_nodegroup"].arn,
      aws_lambda_function.lambda["get_nodegroup_update_status"].arn,
    ]
  }

  statement {
    actions = ["sns:Publish"]
    resources = [var.error_notification_sns_topic_arn]
  }

  statement {
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]
    resources = [var.sns_topic_kms_key_arn]
  }

  statement {
    actions = [
      "logs:CreateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:DescribeLogGroups",
      "logs:DescribeResourcePolicies",
      "logs:GetLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:UpdateLogDelivery",
    ]
    resources = ["*"]
  }
}

## Lambdas

locals {
  lambdas = toset([
    "get_updatable_nodegroups",
    "update_nodegroup",
    "get_nodegroup_update_status",
  ])
}

resource "aws_lambda_function" "lambda" {
  for_each = local.lambdas
  filename = data.archive_file.lambda[each.key].output_path
  function_name = "${replace(each.key, "_", "-")}-${var.cluster_name}"
  source_code_hash = data.archive_file.lambda[each.key].output_base64sha256
  role = aws_iam_role.lambda.arn
  handler = "app.lambda_handler"
  runtime = "python3.8"
  memory_size = 128
  timeout = 10
}

data "archive_file" "lambda" {
  for_each = local.lambdas
  type = "zip"
  output_path = "${path.module}/build/${each.key}.zip"
  source_dir = "${path.module}/functions/${each.key}"
}

resource "aws_cloudwatch_log_group" "lambda" {
  for_each = local.lambdas
  name = "/aws/lambda/${aws_lambda_function.lambda[each.key].function_name}"
  retention_in_days = 30
}

resource "aws_iam_role" "lambda" {
  name = "eks-nodegroup-updater-lambda-${var.cluster_name}"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "lambda" {
  role = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda" {
  name = "policy"
  role = aws_iam_role.lambda.name
  policy = data.aws_iam_policy_document.lambda.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    actions = [
      "eks:DescribeCluster",
      "eks:ListNodegroups",
    ]
    resources = ["arn:aws:eks:${local.region}:${local.account_id}:cluster/${var.cluster_name}"]
  }

  statement {
    actions = [
      "eks:DescribeNodegroup",
      "eks:UpdateNodegroupVersion",
    ]
    resources = ["arn:aws:eks:${local.region}:${local.account_id}:nodegroup/${var.cluster_name}/*"]
  }

  statement {
    actions = [
      "eks:DescribeUpdate",
    ]
    resources = [
      "arn:aws:eks:${local.region}:${local.account_id}:cluster/${var.cluster_name}/*",
      "arn:aws:eks:${local.region}:${local.account_id}:nodegroup/${var.cluster_name}/*",
    ]
  }

  statement {
    actions = [
      "ssm:GetParameter",
    ]
    resources = [
      "arn:aws:ssm:${local.region}::parameter/aws/service/eks/*",
      "arn:aws:ssm:${local.region}:${local.account_id}:parameter/aws/service/eks/*",
    ]
  }

  statement {
    actions = [
      "ec2:DescribeLaunchTemplates",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:RunInstances",
      "ec2:CreateTags",
    ]
    resources = ["*"]
  }
}

## CloudWatch Event Rule (Schedule)

locals {
  create_event = var.schedule != ""
}

resource "aws_cloudwatch_event_rule" "this" {
  count = local.create_event ? 1 : 0
  name = "eks-nodegroup-updater-${var.cluster_name}"
  schedule_expression = var.schedule
  is_enabled = var.schedule_enabled
}

resource "aws_cloudwatch_event_target" "this" {
  count = local.create_event ? 1 : 0
  rule = aws_cloudwatch_event_rule.this[0].id
  arn = aws_sfn_state_machine.this.id
  role_arn = aws_iam_role.event[0].arn
}

resource "aws_iam_role" "event" {
  count = local.create_event ? 1 : 0
  name = "eks-nodegorup-updater-event-${var.cluster_name}"
  assume_role_policy = data.aws_iam_policy_document.event_assume_role[0].json
}

data "aws_iam_policy_document" "event_assume_role" {
  count = local.create_event ? 1 : 0

  statement {
    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type = "Service"
      identifiers = [
        "states.${data.aws_region.current.name}.amazonaws.com",
        "events.amazonaws.com"
      ]
    }
  }
}

resource "aws_iam_role_policy" "event" {
  count = local.create_event ? 1 : 0

  name = "ExecuteStateMachine"
  role = aws_iam_role.event[0].id
  policy = data.aws_iam_policy_document.event_policy[0].json
}

data "aws_iam_policy_document" "event_policy" {
  count = local.create_event ? 1 : 0

  statement {
    actions = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.this.id]
  }
}
