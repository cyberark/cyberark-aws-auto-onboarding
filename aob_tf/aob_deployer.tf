terraform {
  experiments = [variable_validation]
}

variable "region" {
  type    = string
  default = "eu-west-2"
}
variable "bucket_name" {
  type    = string
  default = "aoblondondemoref"
}
variable "subnet_id" {
  type    = string
  default = "subnet-0640e4c5bdc6631da"

  validation {
    condition     = can(regex("^subnet-", var.subnet_id))
    error_message = "The subnet_id value must be a valid subnet id, starting with \"subnet-\"."
  }
}
variable "pvwa_sg" {
  type    = string
  default = "sg-010594faa0c7cbd11"
  
  validation {
    condition     = can(regex("^sg-", var.pvwa_sg))
    error_message = "The pvwa_sg value must be a valid security-group id, starting with \"sg-\"."
  }
}
variable "pvwa_ip" {
  type    = string
  default = "aobpoc.pegasus.cyberark.com"
}
variable "vault_user" {
  type    = string
  default = "Administrator"
}
variable "vault_password" {
  type    = string
  default = "Cyber123!"

  validation {
    condition     = length(var.vault_password) > 7
    error_message = "The vault_password value must be at least with 8 chars."
  }
}
variable "unix_safe" {
  type    = string
  default = "Usafe"
}
variable "winodws_safe" {
  type    = string
  default = "Wsafe"
}
variable "key_pair_safe" {
  type    = string
  default = "KPsafe"
}
variable "key_pair_name" {
  type    = string
  default = "AOB-ref-tf"
}
variable "environment_type" {
  type    = string
  default = "Production"

  validation {
    condition     = contains(["Production", "POC"], var.environment_type)
    error_message = "The environment_type value must 1 of [\"Production\", \"POC\"]."
  }
}
variable "debug_level" {
  type    = string
  default = "Trace"

  validation {
    condition     = contains(["Trace", "Debug"], var.debug_level)
    error_message = "The debug_level value must 1 of [\"Trace\", \"Debug\"]."
  }
}
variable "verification_key" {
  type    = string
  default = "aob-cert.crt"
}
variable "regions" {
  type    = list(string)
  default = ["eu-west-2", "eu-central-1"]
}

provider "aws" {
  profile = "ref"
  region  = var.region
}

data "aws_caller_identity" "current" { }

data "aws_s3_bucket" "aob" {
  bucket = var.bucket_name
}

data "aws_subnet" "pvwa" {
  id = var.subnet_id
}

resource "aws_cloudformation_stack" "elasticity" {
  name          = "AOB-prod-env"
  template_body = file("../dist/multi-region-cft/CyberArk-AOB-MultiRegion-CF.json")
  capabilities  = ["CAPABILITY_NAMED_IAM"]
  
  parameters = {
    LambdasBucket    = data.aws_s3_bucket.aob.bucket
    ComponentsSubnet = data.aws_subnet.pvwa.id
    ComponentsVPC    = data.aws_subnet.pvwa.vpc_id
    PVWASG           = var.pvwa_sg
  }

  tags = {
    terraform = "true"
  }
}

resource "aws_cloudformation_stack" "safe_handler" {
  name          = "AOB-prod-safe"
  template_body = file("../dist/multi-region-cft/CyberArk-AOB-MultiRegion-CF-VaultEnvCreation.yaml")
  
  parameters = {
    Environment                 = var.environment_type
    SafeHandlerLambdaARN        = aws_cloudformation_stack.elasticity.outputs.SafeHandlerLambdaARN
    PvwaIP                      = var.pvwa_ip
    S3BucketWithVerificationKey = data.aws_s3_bucket.aob.bucket
    PVWAVerificationKeyFileName = var.verification_key
    VaultUser                   = var.vault_user
    VaultPassword               = var.vault_password
    UnixSafeName                = var.unix_safe
    CPMNameUnixSafe             = "PasswordManager"
    WindowsSafeName             = var.winodws_safe
    CPMNameWindowsSafe          = "PasswordManager"
    KeyPairsSafe                = var.key_pair_safe
    EnableDebugLevel            = var.debug_level
    KeyPairName                 = var.key_pair_name
  }

  tags = {
    terraform = "true"
  }
  
  depends_on = [
    aws_cloudformation_stack.elasticity
  ]
}

resource "aws_cloudformation_stack" "ss1" {
  name         = "AOB-prod-ss1"
  template_url = "https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetAdministrationRole.yml"
  capabilities = ["CAPABILITY_NAMED_IAM"]
  
  tags = {
    terraform = "true"
  }
}

resource "aws_cloudformation_stack" "ss2" {
  name         = "AOB-prod-ss2"
  template_url = "https://s3.amazonaws.com/cloudformation-stackset-sample-templates-us-east-1/AWSCloudFormationStackSetExecutionRole.yml"
  capabilities = ["CAPABILITY_NAMED_IAM"]
  
  parameters = {
    AdministratorAccountId = data.aws_caller_identity.current.account_id
  }
  
  tags = {
    terraform = "true"
  }
}

data "aws_iam_role" "AWSCloudFormationStackSetAdministrationRole" {
  name = "AWSCloudFormationStackSetAdministrationRole"
  
  depends_on = [
    aws_cloudformation_stack.ss2
  ]
}

resource "aws_cloudformation_stack_set" "aob" {
  administration_role_arn = data.aws_iam_role.AWSCloudFormationStackSetAdministrationRole.arn
  name                    = "example"
  template_body           = file("../dist/multi-region-cft/CyberArk-AOB-MultiRegion-StackSet.json")
  
  parameters = {
    LambdaARN = aws_cloudformation_stack.elasticity.outputs.ElasticityLambdaARN
  }

  tags = {
    terraform = "true"
  }
  
  depends_on = [
    aws_cloudformation_stack.ss1,
    aws_cloudformation_stack.safe_handler
  ]
}

resource "aws_cloudformation_stack_set_instance" "example" {
  for_each = toset(var.regions)

  account_id     = data.aws_caller_identity.current.account_id
  region         = each.key
  stack_set_name = aws_cloudformation_stack_set.aob.name
}