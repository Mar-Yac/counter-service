terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # The name of S3 bucket store the state of terraform
    bucket         = "counter-service-tf-state"
    key            = "prod/counter-service/terraform.tfstate"
    region         = "eu-west-2"

    # The name of DynamoDB table for locking terraform state
    dynamodb_table = "counter-service-tf-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = "eu-west-2"
}
