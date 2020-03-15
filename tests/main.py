import pvwa_api_calls
import pvwa_integration
import boto3
import aws_services
import time
import kp_processing
from datetime import datetime
import instance_processing

# Constants:
win_account_name = "Administrator"
lin_account_name = "ec2-user"
EC2 = boto3.resource('ec2')
EC2_DETAILS = boto3.client('ec2')
DDB = boto3.client('dynamodb')
LINUX_OWNER = "137112412989"
LINUX = "amzn2-ami-hvm*"
WINDOWS_OWNER = "801119661308"
WINDOWS = "Windows_Server-2019-English"
PVWA_URL = "https://10.10.1.10/passwordvault"
PVWA_IP = "10.10.1.10"
UNIX_PLATFORM = "UnixSSHKeys"
WINDOWS_PLATFORM = "WinServerLocal"


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
    vm_info += vm_info['Reservations'][0]['Instances'][0]['PrivateIpAddress']
    print(vm)
    return vm_info


def create_kp():
    kp_name = str(datetime.utcnow())
    kp_name = kp_name.replace(" ", "_")
    kp_name = kp_name.replace(":", "-")
    kp_name = kp_name.split(".")[0]
    kp_value = EC2_DETAILS.create_key_pair(KeyName=kp_name)
    return kp_name, kp_value


def delete_kp(kp_name):
    EC2_DETAILS.delete_key_pair(KeyName=kp_name)


def main():
    session_token = pvwa_integration.logon_pvwa("Administrator", "Noam3110!", PVWA_URL, 1)
    kp = create_kp()
    windows_vm = create_vm(kp[0],
                           'subnet-007426a62cd617ec2',
                           'sg-06a491b55aa7a197e',
                           WINDOWS_OWNER,
                           WINDOWS,
                           '[AOB-Test]Windows')
    print("Windows Deployed")
    linux_vm = create_vm(kp[0],
                         'subnet-007426a62cd617ec2',
                         'sg-06a491b55aa7a197e',
                         LINUX_OWNER,
                         LINUX,
                         '[AOB-Test]Linux')
    print("Linux Deployed")
    time.sleep(60)
    LinuxDDBQuery = aws_services.get_instance_data_from_dynamo_table(linux_vm)
    if "on boarded" in LinuxDDBQuery:
        print("Linux succuess")
        vault_onbaord = pvwa_api_calls.retrieve_accountId_from_account_name(session_token, 'pcloud-test-instances-KP',
                                                                            'KpSafe5',
                                                                            linux_vm,
                                                                            PVWA_URL)
        print(vault_onbaord)
    WindowsDDBQuery = aws_services.get_instance_data_from_dynamo_table(windows_vm[1])
    if "on boarded" in WindowsDDBQuery:
        time.sleep(360)
        print("Windows succuess")
        vault_onbaord = pvwa_api_calls.retrieve_accountId_from_account_name(session_token, 'pcloud-test-instances-KP',
                                                                            'KpSafe5',
                                                                            windows_vm[1],
                                                                            PVWA_URL)
        print(vault_onbaord)
    storeParametersClass = aws_services.StoreParameters("UxSafeCark", "WinSafeCark", "Administrator", "Noam3110!",
                                                        PVWA_IP, "KpSafe2")
    windows_account = pvwa_api_calls.create_account_on_vault(session_token, str(windows_vm[1]), kp[1],
                                                             storeParametersClass,
                                                             WINDOWS_PLATFORM, windows_vm[1],
                                                             windows_vm[0], win_account_name, "KpSafe2")
    linux_account = pvwa_api_calls.create_account_on_vault(session_token, str(linux_vm[1]), kp[1],
                                                           storeParametersClass,
                                                           UNIX_PLATFORM, linux_vm[1],
                                                           windows_vm[0], win_account_name, "KpSafe2")
    print(linux_account + " " + windows_account)
    delete_kp(kp[0])
    pvwa_integration.logoff_pvwa(PVWA_URL, session_token)


main()
