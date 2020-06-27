import unittest
#from unittest.mock import Mock
import boto3
import sys
sys.path.append('../shared_libraries')
from moto import mock_ec2
from moto import mock_iam
from moto import mock_dynamodb2
from moto import mock_sts
from moto import mock_ssm
import aws_services


@mock_iam
@mock_dynamodb2
@mock_sts
@mock_ec2
@mock_ssm

class servicesTest(unittest.TestCase):
    ssm = boto3.client('ssm')
    ssm.put_parameter(
        Name='AOB_Debug_Level',
        Description='string',
        Value='Trace',
        Type='String',
        Overwrite=True)

    def test_get_account_details(self):
        solution_account_id = boto3.client('sts').get_caller_identity().get('Account')
        print (solution_account_id)
        event_region = 'eu-west-2'
        diff_accounts = aws_services.get_account_details('138339392836', solution_account_id, event_region)
        same_account = aws_services.get_account_details(solution_account_id, solution_account_id, event_region)
        self.assertEqual('ec2.ServiceResource()', str(diff_accounts))
        self.assertEqual('ec2.ServiceResource()', str(same_account))

    def test_get_ec2_details(self):   
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object = ec2_resource.create_instances(ImageId='ami-760aaa0f', MinCount=1, MaxCount=5)[0].id
        ec2_windows_object = ec2_resource.create_instances(ImageId='ami-56ec3e2f', MinCount=1, MaxCount=5)[0].id
        linux = aws_services.get_ec2_details(ec2_linux_object, ec2_resource, '138339392836')
        windows = aws_services.get_ec2_details(ec2_windows_object, ec2_resource, '138339392836')
        self.assertIn('Amazon Linux', linux['image_description'])
        self.assertIn('Windows', windows['image_description'])

    def test_get_instance_data_from_dynamo_table(self):
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object = ec2_resource.create_instances(ImageId='ami-760aaa0f', MinCount=1, MaxCount=5)[0].id
        ec2_windows_object = ec2_resource.create_instances(ImageId='ami-56ec3e2f', MinCount=1, MaxCount=5)[0].id
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.create_table(TableName='Instances',
                                      KeySchema=[{"AttributeName": "InstanceId", "KeyType": "HASH"}],
                                      AttributeDefinitions=[{"AttributeName": "InstanceId", "AttributeType": "S"}])
        #dynamodb = boto3.client('dynamodb')
        table = dynamodb.Table('Instances')
        table.put_item(Item={'InstanceId': ec2_linux_object })
        new_response = aws_services.get_instance_data_from_dynamo_table(ec2_windows_object)
        exist_response = aws_services.get_instance_data_from_dynamo_table(ec2_linux_object)
        self.assertFalse(new_response)
        self.assertEqual(str(exist_response), f'{{\'InstanceId\': {{\'S\': \'{ec2_linux_object}\'}}}}')

    def test_put_instance_to_dynamo_table(self):
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object = ec2_resource.create_instances(ImageId='ami-760aaa0f', MinCount=1, MaxCount=5)[0].id
        ec2_windows_object = ec2_resource.create_instances(ImageId='ami-56ec3e2f', MinCount=1, MaxCount=5)[0].id
        dynamodb = boto3.resource('dynamodb')     
        on_boarded = aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'on boarded')
        on_boarded_failed = aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'on board failed')
        delete_failed = aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'delete failed')
        self.assertTrue(on_boarded)
        self.assertTrue(on_boarded_failed)
        self.assertTrue(delete_failed)  

if __name__ == '__main__':
    unittest.main()