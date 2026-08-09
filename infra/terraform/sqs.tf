# Dead-letter queue: messages that fail too many times land here
resource "aws_sqs_queue" "jobs_dlq" {
  name                       = "${var.project_name}-jobs-dlq"
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 30

  # AWS queue allows 1 MiB; AWS provider v5 schema max is still 256 KiB.
  # Keep live value; do not fight provider validation on apply.
  lifecycle {
    ignore_changes = [max_message_size]
  }
}

# Main job queue: worker long-polls this
resource "aws_sqs_queue" "jobs" {
  name                       = "${var.project_name}-jobs"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 3
  })

  lifecycle {
    ignore_changes = [max_message_size]
  }
}
