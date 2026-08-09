resource "aws_cloudwatch_event_bus" "main" {
  name = local.name
}

resource "aws_cloudwatch_event_rule" "research_job_alerts" {
  name           = "research-job-alerts"
  description    = "Notify SNS when research jobs complete or fail"
  event_bus_name = aws_cloudwatch_event_bus.main.name
  state          = "ENABLED"

  event_pattern = jsonencode({
    source      = ["deep.research.agent"]
    detail-type = ["ResearchCompleted", "ResearchFailed"]
  })
}

resource "aws_cloudwatch_event_target" "research_job_alerts_sns" {
  rule           = aws_cloudwatch_event_rule.research_job_alerts.name
  event_bus_name = aws_cloudwatch_event_bus.main.name
  target_id      = "sns-alerts"
  arn            = aws_sns_topic.alerts.arn
}
