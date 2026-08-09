terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state for learning (later: S3 backend).
  # Do not commit *.tfstate - it can contain resource IDs.
}

provider "aws" {
  region = var.aws_region

  # Lesson 2: turn default_tags on after imports are clean.
  # Applying tags now would change live resources on first apply.
}
