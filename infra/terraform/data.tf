data "aws_caller_identity" "current" {}

data "aws_vpc" "default" {
  default = true
}

data "aws_security_group" "default" {
  name   = "default"
  vpc_id = data.aws_vpc.default.id
}

locals {
  account_id = data.aws_caller_identity.current.account_id
  name       = var.project_name
  ecr_image  = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
}
