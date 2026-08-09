resource "aws_sfn_state_machine" "enqueue" {
  name     = "${local.name}-enqueue"
  role_arn = aws_iam_role.sfn.arn
  type     = "STANDARD"

  definition = templatefile("${path.module}/templates/enqueue-job.asl.json.tftpl", {
    jobs_table_name  = aws_dynamodb_table.jobs.name
    jobs_queue_url   = aws_sqs_queue.jobs.url
    alerts_topic_arn = aws_sns_topic.alerts.arn
  })
}
