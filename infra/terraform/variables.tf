variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "eu-north-1"
}

variable "environment" {
  description = "Environment name tag"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Name prefix used in resource names"
  type        = string
  default     = "deep-research"
}

variable "allowed_cidr" {
  description = "CIDR allowed to hit the ALB (your IP /32)"
  type        = string
  default     = "202.191.1.199/32"
}

variable "alert_email" {
  description = "Email subscribed to SNS alerts"
  type        = string
  default     = "sashiradhithya@gmail.com"
}

variable "public_subnet_ids" {
  description = "Public subnets for ALB + Fargate (default VPC)"
  type        = list(string)
  default = [
    "subnet-0d9cfff47da4e93b7",
    "subnet-0320effc18ba1005f",
  ]
}

variable "image_tag" {
  description = "ECR image tag for API and worker"
  type        = string
  default     = "v3"
}

variable "s3_bucket" {
  description = "Existing reports bucket name (not destroyed by this stack)"
  type        = string
  default     = "deep-research-agent-139675292967-eu-north-1-an"
}

variable "secrets_manager_secret_id" {
  description = "Secrets Manager secret id for API keys"
  type        = string
  default     = "deep-research-agent/dev"
}

variable "model" {
  description = "LLM model id for the worker"
  type        = string
  default     = "google_genai:gemini-3.5-flash-lite"
}
