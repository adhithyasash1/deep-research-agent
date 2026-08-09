output "jobs_table_name" {
  description = "DynamoDB jobs table name"
  value       = aws_dynamodb_table.jobs.name
}

output "jobs_queue_url" {
  description = "Main SQS queue URL"
  value       = aws_sqs_queue.jobs.url
}

output "jobs_dlq_url" {
  description = "Dead-letter queue URL"
  value       = aws_sqs_queue.jobs_dlq.url
}

output "alb_dns_name" {
  description = "Public ALB DNS name"
  value       = aws_lb.api.dns_name
}

output "state_machine_arn" {
  description = "Step Functions enqueue state machine ARN"
  value       = aws_sfn_state_machine.enqueue.arn
}

output "event_bus_name" {
  description = "EventBridge custom bus name"
  value       = aws_cloudwatch_event_bus.main.name
}

output "sns_topic_arn" {
  description = "Alerts SNS topic ARN"
  value       = aws_sns_topic.alerts.arn
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.app.repository_url
}
