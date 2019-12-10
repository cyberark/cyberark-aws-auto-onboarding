import boto3


def main():
    # Builds a string of parameters for jenkins automation
    ec2 = boto3.client('ec2')
    account_id = boto3.client('sts').get_caller_identity().get('Account')
    getdetails = instance_details = ec2.describe_instances(Filters=[{'Name': 'tag:Name', 'Values': ['[AOB] PVWA']}])
    details = ("PvwaIp=\'" + getdetails['Reservations'][0]['Instances'][0]['PrivateIpAddress'] + "\' ")
    details += ("ComponentsVPC=\'" + getdetails['Reservations'][0]['Instances'][0]['VpcId'] + "\' ")
    details += ("ComponentsSubnet=\'" + getdetails['Reservations'][0]['Instances'][0]['SubnetId'] + "\' ")
    details += ("PVWAS=\'" + getdetails['Reservations'][0]['Instances'][0]['SecurityGroups'][0]['GroupId'] + "\' ")
    details += ("Accounts \'[" + account_id + "]\'")
    print(details)



main()
