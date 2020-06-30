import unittest
from unittest.mock import Mock
from unittest.mock import MagicMock
from unittest.mock import patch
import sys
import boto3
from boto.ec2.connection import EC2Connection
import requests
from moto import mock_ec2, mock_iam, mock_dynamodb2, mock_sts, mock_ssm
sys.path.append('../shared_libraries')
import aws_services
import kp_processing
import instance_processing
import pvwa_api_calls as pvwa_api
from pvwa_integration import PvwaIntegration

@mock_iam
@mock_dynamodb2
@mock_sts
@mock_ec2
@mock_ssm

class AwsServicesTest(unittest.TestCase):
    ssm = boto3.client('ssm')
    ssm.put_parameter(
        Name='AOB_Debug_Level',
        Description='string',
        Value='Trace',
        Type='String',
        Overwrite=True)

    def test_get_account_details(self):
        print('test_get_account_details')
        solution_account_id = boto3.client('sts').get_caller_identity().get('Account')
        event_region = 'eu-west-2'
        diff_accounts = aws_services.get_account_details('138339392836', solution_account_id, event_region)
        same_account = aws_services.get_account_details(solution_account_id, solution_account_id, event_region)
        self.assertEqual('ec2.ServiceResource()', str(diff_accounts))
        self.assertEqual('ec2.ServiceResource()', str(same_account))

    def test_get_ec2_details(self):
        print('test_get_ec2_details')
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object, ec2_windows_object = generate_ec2(ec2_resource)
        linux = aws_services.get_ec2_details(ec2_linux_object, ec2_resource, '138339392836')
        windows = aws_services.get_ec2_details(ec2_windows_object, ec2_resource, '138339392836')
        self.assertIn('Amazon Linux', linux['image_description'])
        self.assertIn('Windows', windows['image_description'])

    def test_get_instance_data_from_dynamo_table(self):
        print('test_get_instance_data_from_dynamo_table')
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object, ec2_windows_object = generate_ec2(ec2_resource)
        dynamodb = boto3.resource('dynamodb')
        table = dynamo_create_instances_table(dynamodb)
        dynamo_put_ec2_object(dynamodb, ec2_linux_object)
        new_response = aws_services.get_instance_data_from_dynamo_table(ec2_windows_object)
        exist_response = aws_services.get_instance_data_from_dynamo_table(ec2_linux_object)
        self.assertFalse(new_response)
        self.assertEqual(str(exist_response), f'{{\'InstanceId\': {{\'S\': \'{ec2_linux_object}\'}}}}')
        table.delete()

    def test_put_instance_to_dynamo_table(self):
        print('test_put_instance_to_dynamo_table')
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object, ec2_windows_object = generate_ec2(ec2_resource)
        dynamodb = boto3.resource('dynamodb')
        table = dynamo_create_instances_table(dynamodb)
        on_boarded = aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'on boarded')
        on_boarded_failed = aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'on board failed')
        delete_failed = aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'delete failed')
        self.assertTrue(on_boarded)
        self.assertTrue(on_boarded_failed)
        self.assertTrue(delete_failed)
        table.delete()

    def test_release_session_on_dynamo(self):
        print('test_release_session_on_dynamo')
        sessions_table_lock_client = Mock()
        self.assertTrue(aws_services.release_session_on_dynamo('123', '222332', sessions_table_lock_client))
        sessions_table_lock_client = MagicMock(Exception('AssertError'))
        self.assertFalse(aws_services.release_session_on_dynamo('123', '222332', sessions_table_lock_client))

    def test_remove_instance_from_dynamo_table(self):
        print('test_remove_instance_from_dynamo_table')
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object, ec2_windows_object = generate_ec2(ec2_resource)
        dynamodb = boto3.resource('dynamodb')
        table = dynamo_create_instances_table(dynamodb)
        aws_services.put_instance_to_dynamo_table(ec2_linux_object, '1.1.1.1', 'on boarded')
        remove_linux = aws_services.remove_instance_from_dynamo_table(ec2_linux_object)
        remove_windows = aws_services.remove_instance_from_dynamo_table(ec2_windows_object)
        self.assertTrue(remove_linux)
        self.assertTrue(remove_windows)
        table.delete()

    def test_get_session_from_dynamo(self):
        print('test_get_session_from_dynamo')
        sessions_table_lock_client = Mock()
        def fake_acquire(a, b):
            return 'ab-1232'
        @patch.object(sessions_table_lock_client, 'acquire', fake_acquire)
        def invoke():
            session_number, guid = aws_services.get_session_from_dynamo(sessions_table_lock_client)
            return session_number, guid
        session_number, guid = invoke()
        self.assertIn('mock.guid', str(guid))
        self.assertEqual(type('1'), type(session_number))
        @patch.object(sessions_table_lock_client, 'acquire', fake_exc)
        def invoke2():
            with self.assertRaises(Exception) as context:
                aws_services.get_session_from_dynamo(sessions_table_lock_client)
            self.assertTrue('fake_exc' in str(context.exception))
        invoke2()

    def test_update_instances_table_status(self):
        print('test_update_instances_table_status')
        ec2_resource = boto3.resource('ec2')
        ec2_linux_object, ec2_windows_object = generate_ec2(ec2_resource)
        dynamodb = boto3.resource('dynamodb')
        table = dynamo_create_instances_table(dynamodb)
        status = aws_services.update_instances_table_status(ec2_linux_object, 'on boarded')
        self.assertTrue(status)
        table.delete()

@mock_iam
@mock_dynamodb2
@mock_sts
@mock_ec2
@mock_ssm
class KpProcessingTest(unittest.TestCase):
    def test_save_key_pair(self):
        print('test_save_key_pair')
        with open('pemValue.pem', 'r') as file:
            keyf = file.read()
        kp = kp_processing.save_key_pair(keyf)
        self.assertEqual(None, kp)

    def test_convert_pem_to_ppk(self):
        print('test_convert_pem_to_ppk')
        with self.assertRaises(Exception) as context:
            kp_processing.convert_pem_to_ppk('3')
        self.assertEqual('Failed to convert pem', str(context.exception))
        with open('pemValue.pem', 'r') as file:
            keyf = file.read()
        ppk_key = kp_processing.convert_pem_to_ppk(keyf)
        self.assertIn('Private-MAC:', ppk_key)

    def test_run_command_on_container(self):
        print('test_run_command_on_container')
        command = kp_processing.run_command_on_container(
            ["echo", str.strip('V2KFpNbdQM5x90z7KCSqU2Iw8t/kA+8WhWpngtbrZ737Jax9Hj6RBPqyB+qrT0kpVAiAJ9+oXHIU8d7y2OlGdYWjPGB/FFJ'\
            'aVDcOsX+kwQBzeVswv+aD2GgnhvoSRX3feanN7jjbBOLpE+BpqV6a97qYiDSEoEU6l22Vh1TVlMUQ+rytt7c8oUnT3s/nJc01xFSmE1tVx6QNCeJLY'\
            'yfAJCkj6dWYJj7SxpReuBuqmyqvGiPe3pEFDqpl+Tvkz2qg62f8WYWv2dYdQ+/NLFL6nwEKQnyQjBfYoZfmrJev9kejHqLf3zjNWxYK+L62F8g1gZS'\
            'TNkB3U4IDrg/vLiB4YQ=='), "|", "base64", "--decode", "|", "openssl", "rsautl", "-decrypt",
             "-inkey", "/tmp/pemValue.pem"], True)
        self.assertEqual('Ziw$B-HC-9cLEZ?ypza$PUdWQdliW-i9', command[1])

@mock_iam
@mock_dynamodb2
@mock_sts
@mock_ec2
@mock_ssm
class InstanceProcessing(unittest.TestCase):
    pvwa_integration_class = PvwaIntegration()
    def test_delete_instance(self):
        print('test_delete_instance')
        ec2_resource = boto3.resource('ec2')
        linux, windows = generate_ec2(ec2_resource)
        instance_data = {}
        string = {}
        string['S'] = '192.192.192.192'
        instance_data["Address"] = string
        details = dict()
        details['key_name'] = 'myKey'
        details['address'] = '192.192.192.192'
        details['platform'] = 'windows'
        details['image_description'] = 'windows'
        details['aws_account_id'] = '199183736223'
        sp_class = aws_services.StoreParameters('unix', 'windows', 'user', 'password', '1.1.1.1', 'kp', 'cert', 'POC', 'trace')
        sp_class.pvwa_url = 'https://cyberarkaob.cyberark'
        #pvwa_api_calls = Mock()
        def retrieve():
            return '1231'
        req = Mock()
        req.status_code = 200
        dynamodb = boto3.resource('dynamodb')
        table = dynamo_create_instances_table(dynamodb)
        dynamo_put_ec2_object(dynamodb,linux)
        @patch('requests.get', return_value='', status_code='')
        @patch('pvwa_integration.PvwaIntegration.call_rest_api_delete', return_value=req)
        def invoke(a, b, c='c', d='d'):
            with patch('pvwa_api_calls.retrieve_account_id_from_account_name') as mp:
                mp.return_value = '1231'
                deleted_instance = instance_processing.delete_instance(windows, 1, sp_class, instance_data, details)
                instance_data['platform'] = 'Linix'
                instance_data['image_description'] = 'Very Linix'
                failed_instance = instance_processing.delete_instance(linux, 2, sp_class, instance_data, details)     
            return deleted_instance, failed_instance
        return_windows, return_linux = invoke('a', 'b')
        self.assertTrue(return_windows)
        self.assertTrue(return_linux)
        table.delete()

    def test_get_instance_password_data(self):
        print('test_get_instance_password_data')
        ec2_resource = boto3.resource('ec2')
        linux, windows = generate_ec2(ec2_resource)
        with patch('boto.ec2.connection.EC2Connection.get_password_data', return_value='StrongPassword'): #### to improve
            respone = instance_processing.get_instance_password_data(windows, '123456789012', 'eu-west-2', '123456789012')
        self.assertEqual(None, respone)




def fake_exc(a, b):
    raise Exception('fake_exc')

def generate_ec2(ec2_resource, returnObject=False):
    ec2_linux_object = ec2_resource.create_instances(ImageId='ami-760aaa0f', MinCount=1, MaxCount=5)
    ec2_windows_object = ec2_resource.create_instances(ImageId='ami-56ec3e2f', MinCount=1, MaxCount=5)
    if returnObject:
        return ec2_linux_object, ec2_windows_object
    return ec2_linux_object[0].id, ec2_windows_object[0].id

def dynamo_create_instances_table(dynamo_resource):
    table = dynamo_resource.Table('Instances')
    table = dynamo_resource.create_table(TableName='Instances',
                                         KeySchema=[{"AttributeName": "InstanceId", "KeyType": "HASH"}],
                                         AttributeDefinitions=[{"AttributeName": "InstanceId", "AttributeType": "S"}])
    return table

def dynamo_put_ec2_object(dynamo_resource, ec2_object):
    table = dynamo_resource.Table('Instances')
    table.put_item(Item={'InstanceId': ec2_object})
    return True

if __name__ == '__main__':
    unittest.main()
