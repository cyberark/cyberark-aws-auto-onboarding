variable "region_main" {
  type = string
}
variable "region_sec" {
  type = string
}
variable "instance_name" { # Set by parameter
  type = string
}
variable "instance_type" {
  type    = string
  default = "t2.nano"
}
variable "subnet_id_main" {
  type = string
}
variable "subnet_id_sec" {
  type = string
}
variable "key_pair_main" {
  type = string
}
variable "key_pair_sec" {
  type = string
}
variable "pcs" { # Static
  type = number
}

provider "aws" {
  profile = "default"
  region  = var.region_main
  alias   = "main"
}

provider "aws" {
  profile = "default"
  region  = var.region_sec
  alias   = "sec"
}

data "aws_ami" "amazon_linux_main" {
  provider = aws.main

  owners      = ["137112412989"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "fedora_main" {
  provider = aws.main

  owners      = ["125523088429"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["fedora-coreos-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "open_suse_main" {
  provider = aws.main

  owners      = ["679593333241"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["openSUSE-Leap-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "debian_main" {
  provider = aws.main

  owners      = ["379101102735"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["debian-stretch-hvm-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "centos_main" {
  provider = aws.main

  owners      = ["679593333241"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["CentOS Linux 7*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "ubuntu_main" {
  provider = aws.main

  owners      = ["099720109477"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-xenial-16.04-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "windows_main" {
  provider = aws.main

  owners      = ["801119661308"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["Windows_Server-2016-English-Core-Base-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "amazon_linux_sec" {
  provider = aws.sec

  owners      = ["137112412989"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "fedora_sec" {
  provider = aws.sec

  owners      = ["125523088429"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["fedora-coreos-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "open_suse_sec" {
  provider = aws.sec

  owners      = ["679593333241"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["openSUSE-Leap-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "debian_sec" {
  provider = aws.sec

  owners      = ["379101102735"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["debian-stretch-hvm-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "centos_sec" {
  provider = aws.sec

  owners      = ["679593333241"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["CentOS Linux 7*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "ubuntu_sec" {
  provider = aws.sec

  owners      = ["099720109477"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-xenial-16.04-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

data "aws_ami" "windows_sec" {
  provider = aws.sec

  owners      = ["801119661308"]
  most_recent = true
  
  filter {
    name   = "name"
    values = ["Windows_Server-2016-English-Core-Base-*"]
  }
  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

module "deploy_win_main" {
  source = "./modules/win_deploy"
  
  image_id      = data.aws_ami.windows_main.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_main
  key_pair      = var.key_pair_main
  pcs           = 1

  providers = {
    aws = aws.main
  }
}

module "deploy_win_sec" {
  source = "./modules/win_deploy"
  
  image_id      = data.aws_ami.windows_sec.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_sec
  key_pair      = var.key_pair_sec
  pcs           = var.pcs

  providers = {
    aws = aws.sec
  }
}

module "deploy_amazon_main" {
  source = "./modules/linux_deploy"
  
  image_id      = data.aws_ami.amazon_linux_main.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_main
  key_pair      = var.key_pair_main
  pcs           = 1
  
  providers = {
    aws = aws.main
  }
}

module "deploy_amazon_sec" {
  source = "./modules/linux_deploy"
  
  image_id      = data.aws_ami.amazon_linux_sec.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_sec
  key_pair      = var.key_pair_sec
  pcs           = var.pcs

  providers = {
    aws = aws.sec
  }
}

module "deploy_centos_main" {
  source = "./modules/linux_deploy"
  
  image_id      = data.aws_ami.centos_main.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_main
  key_pair      = var.key_pair_main
  pcs           = var.pcs
  
  providers = {
    aws = aws.main
  }
}

module "deploy_fedora_sec" {
  source = "./modules/linux_deploy"
  
  image_id      = data.aws_ami.fedora_sec.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_sec
  key_pair      = var.key_pair_sec
  pcs           = var.pcs

  providers = {
    aws = aws.sec
  }
}

module "deploy_ubuntu_main" {
  source = "./modules/linux_deploy"
  
  image_id      = data.aws_ami.ubuntu_main.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_main
  key_pair      = var.key_pair_main
  pcs           = var.pcs
  
  providers = {
    aws = aws.main
  }
}

module "deploy_suse_sec" {
  source = "./modules/linux_deploy"
  
  image_id      = data.aws_ami.open_suse_sec.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_sec
  key_pair      = var.key_pair_sec
  pcs           = var.pcs

  providers = {
    aws = aws.sec
  }
}


module "deploy_debian_main" {
  source = "./modules/linux_deploy"
  
  image_id      = data.aws_ami.debian_main.id
  instance_name = var.instance_name
  instance_type = var.instance_type
  subnet_id     = var.subnet_id_main
  key_pair      = var.key_pair_main
  pcs           = var.pcs
  
  providers = {
    aws = aws.main
  }
}