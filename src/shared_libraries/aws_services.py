import boto3
import json
import time
import random
from log_mechanism import LogMechanism
from dynamo_lock import LockerClient

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = LogMechanism()


# return ec2 instance relevant data:
# keyPair_name, instance_address, platform
def get_ec2_details(instance_id, solution_account_id, event_region, event_account_id):
    logger.trace(instance_id, solution_account_id, event_region, event_account_id, caller_name='get_ec2_details')
    logger.info('Gathering details about EC2 - ' + instance_id )
    if event_account_id == solution_account_id:
        try:
            ec2_resource = boto3.resource('ec2', event_region)
        except Exception as e:
            logger.error('Error on creating boto3 session: {0}'.format(str(e)))
    else:
        try:
            logger.info('Assuming Role')
            sts_connection = boto3.client('sts')
            acct_b = sts_connection.assume_role(
                RoleArn="arn:aws:iam::{0}:role/CyberArk-AOB-AssumeRoleForElasticityLambda".format(event_account_id),
                RoleSessionName="cross_acct_lambda"
            )

            access_key = acct_b['Credentials']['AccessKeyId']
            secret_key = acct_b['Credentials']['SecretAccessKey']
            session_token = acct_b['Credentials']['SessionToken']

            # create service client using the assumed role credentials, e.g. S3
            ec2_resource = boto3.resource(
                'ec2',
                region_name=event_region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
            )
        except Exception as e:
            logger.error('Error on getting token from account: {0}'.format(event_account_id))

    try:
        instance_resource = ec2_resource.Instance(instance_id)
        instance_image = ec2_resource.Image(instance_resource.image_id)
        logger.info('Image Detected: ' + str(instance_image))
        image_description = instance_image.description
    except Exception as e:
        logger.error('Error on getting instance details: {0}'.format(str(e)))
        raise e

    #  We take the instance address in the order of: public dns -> public ip -> private ip ##
    if instance_resource.private_ip_address:
        address = instance_resource.private_ip_address
    else:  # unable to retrieve address from aws
        address = None

    if not image_description:
        raise Exception("Determining OS type failed")

    details = dict()
    details['key_name'] = instance_resource.key_name
    details['address'] = address
    details['platform'] = instance_resource.platform
    details['image_description'] = image_description
    details['aws_account_id'] = event_account_id
    return details


# Check on DynamoDB if instance exists
# Return False when not found, or row data from table
def get_instance_data_from_dynamo_table(instance_id):
    logger.trace(instance_id, caller_name='get_instance_data_from_dynamo_table')
    logger.info('Check with DynamoDB if instance {0} exists'.format(instance_id))
    dynamo_resource = boto3.client('dynamodb')

    try:
        dynamo_response = dynamo_resource.get_item(TableName='Instances', Key={"instance_id": {"S": instance_id}})
    except Exception:
        logger.error("Error occurred when trying to call dynamoDB")
        return False
    # DynamoDB "Item" response: {'Address': {'S': 'xxx.xxx.xxx.xxx'}, 'instance_id': {'S': 'i-xxxxxyyyyzzz'},
    #               'Status': {'S': 'on-boarded'}, 'Error': {'S': 'Some Error'}}
    if 'Item' in dynamo_response:
        if dynamo_response["Item"]["instance_id"]["S"] == instance_id:
            logger.info(instance_id + ' exists in DynamoDB')
            return dynamo_response["Item"]
        else:
            return False
    else:
        return False


def get_params_from_param_store():
    # Parameters that will be retrieved from parameter store
    logger.info('Getting parameters from parameter store')
    UNIX_SAFE_NAME_PARAM = "AOB_Unix_Safe_Name"
    WINDOWS_SAFE_NAME_PARAM = "AOB_Windows_Safe_Name"
    VAULT_USER_PARAM = "AOB_Vault_User"
    PVWA_IP_PARAM = "AOB_PVWA_IP"
    AWS_KEYPAIR_SAFE = "AOB_KeyPair_Safe"
    VAULT_PASSWORD_PARAM_ = "AOB_Vault_Pass"
    PVWA_VERIFICATION_KEY = "AOB_PVWA_Verification_Key"
    AOB_MODE="aob_mode"
    AOB_DEBUG_LEVEL = "AOB_Debug_Level"

    lambda_client = boto3.client('lambda')
    lambda_request_data = dict()
    lambda_request_data["Parameters"] = [UNIX_SAFE_NAME_PARAM, WINDOWS_SAFE_NAME_PARAM, VAULT_USER_PARAM, PVWA_IP_PARAM,
                                       AWS_KEYPAIR_SAFE, VAULT_PASSWORD_PARAM_, PVWA_VERIFICATION_KEY, AOB_MODE, AOB_DEBUG_LEVEL]
    try:
        response = lambda_client.invoke(FunctionName='TrustMechanism',
                                       InvocationType='RequestResponse',
                                       Payload=json.dumps(lambda_request_data))
    except Exception as e:
        logger.error("Error retrieving parameters from parameter parameter store:{0}".format(str(e)))
        raise Exception("Error retrieving parameters from parameter parameter store:{0}".format(str(e))) 

    json_parsed_response = json.load(response['Payload'])
    # parsing the parameters, json_parsed_response is a list of dictionaries
    for ssm_store_item in json_parsed_response:
        if ssm_store_item['Name'] == UNIX_SAFE_NAME_PARAM:
            unix_safe_name = ssm_store_item['Value']
        elif ssm_store_item['Name'] == WINDOWS_SAFE_NAME_PARAM:
            windows_safe_name = ssm_store_item['Value']
        elif ssm_store_item['Name'] == VAULT_USER_PARAM:
            vault_username = ssm_store_item['Value']
        elif ssm_store_item['Name'] == PVWA_IP_PARAM:
            pvwa_ip = ssm_store_item['Value']
        elif ssm_store_item['Name'] == AWS_KEYPAIR_SAFE:
            key_pair_safe_name = ssm_store_item['Value']
        elif ssm_store_item['Name'] == VAULT_PASSWORD_PARAM_:
            vault_password = ssm_store_item['Value']
        elif ssm_store_item['Name'] == PVWA_VERIFICATION_KEY:
            pvwa_verification_key = ssm_store_item['Value']
        elif ssm_store_item['Name'] == AOB_DEBUG_LEVEL:
            debug_level = ssm_store_item['Value']
        elif ssm_store_item['Name'] == AOB_MODE:
            aob_mode = ssm_store_item['Value']
            if aob_mode == 'POC':
                pvwa_verification_key = ''
        else:
            continue
    store_parameters_class = StoreParameters(unix_safe_name, windows_safe_name, vault_username, vault_password, pvwa_ip,
                                           key_pair_safe_name, pvwa_verification_key, aob_mode, debug_level)
    return store_parameters_class


def put_instance_to_dynamo_table(instance_id, ip_address, on_board_status, on_board_error="None", log_name="None"):
    logger.trace(instance_id, ip_address, on_board_status, on_board_error, log_name, caller_name='put_instance_to_dynamo_table')
    logger.info('Adding  {instance_id} to DynamoDB'.format(instance_id=instance_id))
    dynamodb_resource = boto3.resource('dynamodb')
    instances_table = dynamodb_resource.Table("Instances")
    try:
        instances_table.put_item(
            Item={
                'instance_id': instance_id,
                'Address': ip_address,
                'Status': on_board_status,
                'Error': on_board_error,
                'LogId': log_name
            }
        )
    except Exception:
        logger.error('Exception occurred on add item to DynamoDB')
        return None

    logger.info('Item {0} added successfully to DynamoDB'.format(instance_id))
    return


def release_session_on_dynamo(session_id, session_guid):
    logger.trace(session_id, session_guid, caller_name='release_session_on_dynamo')
    logger.info('Releasing session lock from DynamoDB')
    try:
        sessions_table_lock_client = LockerClient('Sessions')
        sessions_table_lock_client.locked = True
        sessions_table_lock_client.guid = session_guid
        sessions_table_lock_client.release(session_id)
    except Exception as e:
        logger.error('Failed to release session lock from DynamoDB:\n{error}'.format(error=str(e)))
        return False

    return True


def remove_instance_from_dynamo_table(instance_id):
    logger.trace(instance_id, caller_name='remove_instance_from_dynamo_table')
    logger.info('Removing ' + instance_id +' from DynamoDB')
    dynamodb_resource = boto3.resource('dynamodb')
    instances_table = dynamodb_resource.Table("Instances")
    try:
        instances_table.delete_item(
            Key={
                'instance_id': instance_id
            }
        )
    except Exception as e:
        logger.error('Exception occurred on deleting {instance_id} on dynamodb:\n{error}'.format(instance_id=instance_id, error=str(e)))
        return None

    logger.info('Item {0} successfully deleted from DB'.format(instance_id))
    return


def get_available_session_from_dynamo():
    logger.info("Getting available Session from DynamoDB")
    sessions_table_lock_client = LockerClient('Sessions')
    timeout = 20000  # Setting the timeout to 20 seconds on a row lock
    random_session_number = str(random.randint(1, 100))  # A number between 1 and 100

    try:
        for i in range(0, 20):

            lock_response = sessions_table_lock_client.acquire(random_session_number, timeout)
            if lock_response:  # no lock on connection number, return it
                logger.info("Successfully retrieved session from DynamoDB")
                return random_session_number, sessions_table_lock_client.guid
            else:  # connection number is locked, retry in 5 seconds
                time.sleep(5)
                continue
        #  if reached here, 20 retries with 5 seconds between retry - ended
        logger.info("Connection limit has been reached")
        return False, ""
    except Exception as e:
        print("Failed to retrieve session from DynamoDB:{0}".format(str(e)))
        raise Exception("Exception on get_available_session_from_dynamo:{0}".format(str(e)))


def update_instances_table_status(instance_id, status, error="None"):
    logger.trace(instance_id, status, error, caller_name='update_instances_table_status')
    logger.info('Updating DynamoDB with {instance_id} onboarding status. \nStatus: {status}'.format(status=status,instance_id=instance_id))
    dynamodb_resource = boto3.resource('dynamodb')
    instances_table = dynamodb_resource.Table("Instances")
    try:
        instances_table.update_item(
            Key={
                'instance_id': instance_id
            },
            AttributeUpdates={
                'Status': {
                    "Value": status,
                    "Action": "PUT"
                },
                'Error': {
                    "Value": error,
                    "Action": "PUT"
                }
            }
        )
    except Exception:
        logger.error('Exception occurred on updating session on dynamoDB')
        return None
    logger.info("Instance data updated successfully")
    return


class StoreParameters:
    unix_safe_name = ""
    windows_safe_name = ""
    vault_username = ""
    vault_password = ""
    pvwa_url = "https://{0}/PasswordVault"
    key_pair_safe_name = ""
    pvwa_verification_key = ""
    aob_mode = ""


    def __init__(self, unix_safe_name, windows_safe_name, username, password, ip, key_pair_safe, pvwa_verification_key, mode, debug):
        self.unix_safe_name = unix_safe_name
        self.windows_safe_name = windows_safe_name
        self.vault_username = username
        self.vault_password = password
        self.pvwa_url = self.pvwa_url.format(ip)
        self.key_pair_safe_name = key_pair_safe
        self.pvwa_verification_key = pvwa_verification_key
        self.aob_mode = mode
        self.debug_level = debug