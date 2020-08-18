data "aws_subnet" "this" { # get data
  id = var.subnet_id
}

resource "aws_instance" "this" {
  count = var.pcs <= 300 ? var.pcs : 1

  ami               = var.image_id
  instance_type     = var.instance_type
  subnet_id         = data.aws_subnet.this.id
  key_name          = var.key_pair
  get_password_data = true
  user_data = <<-EOF
    <script>
    netsh firewall set service RemoteAdmin enable
    </script>
  EOF

  tags = {
    "Terraform" : "true"
    "Name"      : "${var.instance_name}-win-${count.index}"
    "Testing"   : "true"
    "Platform"  : "Windows"
  }
}
