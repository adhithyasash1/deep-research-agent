resource "aws_ecr_repository" "app" {
  name                 = "deep-research-agent"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name = "/ecs/deep-research-api"
  # Existing groups have no retention (never expire). Keep as-is.
  retention_in_days = 0
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/deep-research-worker"
  retention_in_days = 0
}

resource "aws_cloudwatch_log_group" "agent" {
  name              = "/ecs/deep-research-agent"
  retention_in_days = 0
}
