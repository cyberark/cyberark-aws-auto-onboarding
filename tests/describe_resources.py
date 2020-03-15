import boto3


class PvwaInstance:
    ip = "1.1.1.1"
    vpc_id = "vpc-123123"
    subnet_id = "sub-123123"
    group_id = "sg-123123"
    account_id = "123123"

    def __init__(self, ip, vpc_id, subnet_id, group_id, account_id):
        self.ip = ip
        self.vpc_id = vpc_id
        self.subnet_id = subnet_id
        self.group_id = group_id
        self.account_id = account_id


def main():
    # Builds a string of parameters for jenkins automation
    ec2 = boto3.client('ec2')
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    details = []
    getdetails = ec2.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['[AOB] PVWA']}])
    details.append(getdetails['Reservations'][0]['Instances'][0]['PrivateIpAddress'])
    details.append(getdetails['Reservations'][0]['Instances'][0]['VpcId'])
    details.append(getdetails['Reservations'][0]['Instances'][0]['SubnetId'])
    details.append(getdetails['Reservations'][0]['Instances'][0]['SecurityGroups'][0]['GroupId'])
    details.append(account_id)
    instance_details =PvwaInstance(details[0],details[1],details[2],details[3],details[4])
    return instance_details
