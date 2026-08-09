#!/usr/bin/env bash
# Import existing hand-built resources into Terraform state.
# Run from infra/terraform after: terraform init
set -euo pipefail

REGION="${AWS_REGION:-eu-north-1}"
ACCOUNT="139675292967"
NAME="deep-research"

terraform import aws_sns_topic.alerts "arn:aws:sns:${REGION}:${ACCOUNT}:${NAME}-alerts" || true
terraform import aws_sns_topic_subscription.alerts_email "arn:aws:sns:${REGION}:${ACCOUNT}:${NAME}-alerts:e2bb5b8f-3ca9-4dce-a28a-7583558370ef" || true

terraform import aws_cloudwatch_event_bus.main "${NAME}" || true
terraform import aws_cloudwatch_event_rule.research_job_alerts "${NAME}/research-job-alerts" || true
terraform import aws_cloudwatch_event_target.research_job_alerts_sns "${NAME}/research-job-alerts/sns-alerts" || true

terraform import aws_ecr_repository.app deep-research-agent || true
terraform import aws_cloudwatch_log_group.api /ecs/deep-research-api || true
terraform import aws_cloudwatch_log_group.worker /ecs/deep-research-worker || true
terraform import aws_cloudwatch_log_group.agent /ecs/deep-research-agent || true

terraform import aws_iam_role.ecs_execution "${NAME}-ecs-execution" || true
terraform import aws_iam_role_policy_attachment.ecs_execution "${NAME}-ecs-execution/arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy" || true
terraform import aws_iam_role.ecs_task "${NAME}-ecs-task" || true
terraform import aws_iam_role_policy.ecs_task "${NAME}-ecs-task:DeepResearchAgentRuntime" || true
terraform import aws_iam_role.sfn "${NAME}-sfn" || true
terraform import aws_iam_role_policy.sfn "${NAME}-sfn:deep-research-sfn-access" || true

terraform import aws_sfn_state_machine.enqueue "arn:aws:states:${REGION}:${ACCOUNT}:stateMachine:${NAME}-enqueue" || true

terraform import aws_security_group.alb sg-03317db026cd063b5 || true
terraform import aws_security_group.api sg-0b04b3ba2c89944d7 || true

terraform import aws_lb_target_group.api "arn:aws:elasticloadbalancing:${REGION}:${ACCOUNT}:targetgroup/${NAME}-api/0c0b8b19f3612769" || true
terraform import aws_lb.api "arn:aws:elasticloadbalancing:${REGION}:${ACCOUNT}:loadbalancer/app/${NAME}-api/29a8193d98418081" || true
terraform import aws_lb_listener.api_http "arn:aws:elasticloadbalancing:${REGION}:${ACCOUNT}:listener/app/${NAME}-api/29a8193d98418081/a79fb3f23c036775" || true

terraform import aws_ecs_cluster.main "${NAME}-agent" || true
terraform import aws_ecs_task_definition.api "arn:aws:ecs:${REGION}:${ACCOUNT}:task-definition/${NAME}-api:3" || true
terraform import aws_ecs_task_definition.worker "arn:aws:ecs:${REGION}:${ACCOUNT}:task-definition/${NAME}-worker:2" || true
terraform import aws_ecs_service.api "${NAME}-agent/${NAME}-api" || true
terraform import aws_ecs_service.worker "${NAME}-agent/${NAME}-worker" || true

# SNS topic policy has no separate import id in older providers - may need apply once
terraform import aws_sns_topic_policy.alerts "arn:aws:sns:${REGION}:${ACCOUNT}:${NAME}-alerts" || true

terraform plan -no-color
