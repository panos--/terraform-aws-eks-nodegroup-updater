variable "cluster_name" {
  type = string
}

# See https://docs.aws.amazon.com/AmazonCloudWatch/latest/events/ScheduledEvents.html
variable "schedule" {
  type = string
}

variable "schedule_enabled" {
  type = bool
  default = true
}

variable "error_notification_sns_topic_arn" {
  type = string
}

variable "sns_topic_kms_key_arn" {
  type = string
}
