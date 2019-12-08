import pvwa_api_calls
import pvwa_integration
import boto3
# import pytest

EC2 = boto3.resource('ec2')
EC2_DETAILS = boto3.client('ec2')
LINUX_OWNER = "137112412989"
LINUX = "amzn2-ami-hvm*"
WINDOWS_OWNER = "801119661308"
WINDOWS = "Windows_Server-2019-English"


def create_vm(key_pair, subnet_id, security_group_id, ami_owner, image_type, guest_os):
    ami = EC2_DETAILS.describe_images(
        Owners=[ami_owner],
        Filters=[
            {'Name': 'name', 'Values': [image_type]},
            {'Name': 'architecture', 'Values': ['x86_64']},
            {'Name': 'root-device-type', 'Values': ['ebs']},
        ],
    )
    vm = EC2.create_instances(ImageId=ami['Images'][0]['ImageId'],
                              InstanceType='t2.medium',
                              KeyName=key_pair,
                              SecurityGroupIds=[security_group_id],
                              SubnetId=subnet_id,
                              MinCount=1,
                              MaxCount=1,
                              TagSpecifications=[
                                  {
                                      'ResourceType': 'instance',
                                      'Tags': [
                                          {
                                              'Key': 'Name',
                                              'Value': guest_os
                                          },
                                      ]
                                  },
                              ]
                              )
    vm_info = EC2_DETAILS.describe_instances(InstanceIds=[vm[0].id])
    vm_info = vm_info['Reservations'][0]['Instances'][0]['PrivateIpAddress']
    return vm_info


def main():
    # windows_vm = create_vm('pcloud-test-instances-KP',
    #                        'subnet-007426a62cd617ec2',
    #                        'sg-06a491b55aa7a197e',
    #                        WINDOWS_OWNER,
    #                        WINDOWS,
    #                        '[AOB-Test]Windows')
    linux_vm = create_vm('pcloud-test-instances-KP',
                         'subnet-007426a62cd617ec2',
                         'sg-06a491b55aa7a197e',
                         LINUX_OWNER,
                         LINUX,
                         '[AOB-Test]Linux')
    print(linux_vm)


main()
