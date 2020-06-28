import unittest
from unittest.mock import Mock
from unittest.mock import MagicMock
from unittest.mock import patch
import sys
import boto3
from moto import mock_ec2, mock_iam, mock_dynamodb2, mock_sts, mock_ssm
sys.path.append('../shared_libraries')
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
        table = dynamodb.Table('Instances')
        table.put_item(Item={'InstanceId': ec2_linux_object})
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

    def test_release_session_on_dynamo(self):
        sessions_table_lock_client = Mock()
        self.assertTrue(aws_services.release_session_on_dynamo('123', '222332', sessions_table_lock_client))
        sessions_table_lock_client = MagicMock(Exception('AssertError'))
        self.assertFalse(aws_services.release_session_on_dynamo('123', '222332', sessions_table_lock_client))

    def test_remove_instance_from_dynamo_table(self):
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object = ec2_resource.create_instances(ImageId='ami-760aaa0f', MinCount=1, MaxCount=5)[0].id
        ec2_windows_object = ec2_resource.create_instances(ImageId='ami-56ec3e2f', MinCount=1, MaxCount=5)[0].id
        dynamodb = boto3.resource('dynamodb')
        aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'on boarded')
        remove_linux = aws_services.remove_instance_from_dynamo_table(ec2_linux_object)
        remove_windows = aws_services.remove_instance_from_dynamo_table(ec2_windows_object)
        self.assertTrue(remove_linux)
        self.assertTrue(remove_windows)

    def test_get_session_from_dynamo(self):
        sessions_table_lock_client = Mock()
        def fake_acquire(a, b):
            return 'ab-1232'
        def fake_acquire_exc(a, b):
            raise(Exception('fake_acquire_exc'))
        @patch.object(sessions_table_lock_client, 'acquire', fake_acquire)
        def invoke():
            session_number, guid = aws_services.get_session_from_dynamo(sessions_table_lock_client)
            return session_number, guid
        session_number, guid = invoke()
        self.assertIn('mock.guid', str(guid))
        self.assertEqual(type('1'), type(session_number))
        @patch.object(sessions_table_lock_client, 'acquire', fake_acquire_exc)
        def invoke2():
            with self.assertRaises(Exception) as context:
                aws_services.get_session_from_dynamo(sessions_table_lock_client)
            self.assertTrue('fake_acquire_exc' in str(context.exception))
        invoke2()

if __name__ == '__main__':
    unittest.main()
