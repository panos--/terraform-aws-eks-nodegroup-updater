provider "aws" {
  version = "~> 2.60"
  region = "eu-central-1"
}

provider "archive" {
  version = "~> 1.3"
}

module "eks_nodegroup_updater" {
  source = "../../"

  cluster_name = "eks-itop01"
  schedule = "cron(37 3 * * ? *)"
  schedule_enabled = false
  error_notification_sns_topic_arn = var.sns_topic_arn
  sns_topic_kms_key_arn = var.kms_key_arn
}
