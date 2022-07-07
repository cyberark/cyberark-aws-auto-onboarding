import json
import time
import random
import boto3
from log_mechanism import LogMechanism
from dynamo_lock import LockerClient

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
SAFE = "AOB_Safe"
USERNAME = "AOB_Username"
PLATFORM = "AOB_Platform"

logger = LogMechanism()


# return ec2 instance relevant data:
# keyPair_name, instance_address, platform
def get_account_details(solution_account_id, event_account_id, event_region):
    logger.trace(solution_account_id, event_region, event_account_id, caller_name='get_account_details')
    if event_account_id == solution_account_id:
        try:
            ec2_resource = boto3.resource('ec2', event_region)
        except Exception as e:
            logger.error(f'Error on creating boto3 session: {str(e)}')
    else:
        logger.debug('Event occurred in different account')
        try:
            logger.debug('Assuming Role')
            sts_connection = boto3.client('sts')
            acct_b = sts_connection.assume_role(
                RoleArn=f"arn:aws:iam::{event_account_id}:role/CyberArk-AOB-AssumeRoleForElasticityLambda",
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
            logger.error(f'Error on getting token from account: {event_account_id}')
    return ec2_resource


def get_ec2_details(instance_id, ec2_object, event_account_id):
    logger.trace(instance_id, ec2_object, event_account_id, caller_name='get_ec2_details')
    logger.debug(f"Gathering details about EC2 - '{instance_id}'")
    try:
        instance_resource = ec2_object.Instance(instance_id)
        instance_image = ec2_object.Image(instance_resource.image_id)
        logger.debug(f'Image Detected: {str(instance_image)}')
        image_description = instance_image.description
    except Exception as e:
        logger.error(f'Error on getting instance details: {str(e)}')
        raise e

    #  We take the instance address in the order of: public dns -> public ip -> private ip ##
    if instance_resource.private_ip_address:
        address = instance_resource.private_ip_address
    else:  # unable to retrieve address from aws
        address = None

    if not image_description:
        raise Exception("Determining OS type failed")

    logger.debug(f'Gathering details from parameter store')
    parmstore= get_params_from_param_store()
    logger.debug(f'Successfully retrived details from parameter store')
    logger.debug(f'Starting to set tag values')
    try: 
        for tag in instance_resource.tags:
            if tag['Key']==parmstore.EC2SafeTag:
                AOBSafe = tag['Value']
                logger.trace(f'AOBSafe = {AOBSafe}', caller_name='get_ec2_details_AOBSafe')
            elif tag['Key']==parmstore.EC2UsernameTag:
                AOBUsername=tag['Value']
                logger.trace(f'AOBUsername = {AOBUsername}', caller_name='get_ec2_details_AOBUsername')
            elif tag['Key']==parmstore.EC2PlatformTag:
                AOBPlatform=tag['Value']
                logger.trace(f'AOBPlatform = {AOBPlatform}', caller_name='get_ec2_details_AOBPlatform')
    except TypeError as e:
        raise e
    except Exception as e:
        logger.error(f'Error on getting tag: {str(e)}')
        raise e
    logger.debug(f'Completed setting tag values')

    try:
        details = dict()
        details['key_name'] = instance_resource.key_name
        details['address'] = address
        details['platform'] = instance_resource.platform
        details['image_description'] = image_description
        details['aws_account_id'] = event_account_id
        details['AOBSafe'] = AOBSafe
        details['AOBUsername'] = AOBUsername
        details['AOBPlatform'] = AOBPlatform
        logger.trace(details, caller_name='get_ec2_details')
        return details
    except Exception:
        raise UnboundLocalError

# Check on DynamoDB if instance exists
# Return False when not found, or row data from table
def get_instance_data_from_dynamo_table(instance_id):
    logger.trace(instance_id, caller_name='get_instance_data_from_dynamo_table')
    logger.debug(f"Checking with DynamoDB if instance '{instance_id}' exists")
    dynamo_resource = boto3.client('dynamodb')

    try:
        dynamo_response = dynamo_resource.get_item(TableName='Instances', Key={"InstanceId": {"S": instance_id}})
    except Exception as e:
        logger.error(f"Error occurred when trying to call DynamoDB: {e}")
        return False
    # DynamoDB "Item" response: {'Address': {'S': 'xxx.xxx.xxx.xxx'}, 'instance_id': {'S': 'i-xxxxxyyyyzzz'},
    #               'Status': {'S': 'on-boarded'}, 'Error': {'S': 'Some Error'}}
    if 'Item' in dynamo_response:
        if dynamo_response["Item"]["InstanceId"]["S"] == instance_id:
            logger.debug(f"'{instance_id}' exists in DynamoDB")
            return dynamo_response["Item"]
    return False


def get_params_from_param_store():
    # Parameters that will be retrieved from parameter store
    logger.debug('Getting parameters from parameter store')
    VAULT_USER_PARAM = "AOB_Vault_User"
    PVWA_IP_PARAM = "AOB_PVWA_IP"
    AWS_KEYPAIR_SAFE = "AOB_KeyPair_Safe"
    VAULT_PASSWORD_PARAM_ = "AOB_Vault_Pass"
    PVWA_VERIFICATION_KEY = "AOB_PVWA_Verification_Key"
    AOB_MODE = "AOB_mode"
    AOB_DEBUG_LEVEL = "AOB_Debug_Level"
    AOB_USERNAME = "AOB_Username"
    AOB_SAFE = "AOB_Safe"
    AOB_PLATFORM = "AOB_Platform"

    lambda_client = boto3.client('lambda')
    lambda_request_data = dict()
    lambda_request_data["Parameters"] = [VAULT_USER_PARAM, PVWA_IP_PARAM,
                                         AWS_KEYPAIR_SAFE, VAULT_PASSWORD_PARAM_, PVWA_VERIFICATION_KEY, AOB_MODE,
                                         AOB_DEBUG_LEVEL, AOB_USERNAME, AOB_SAFE, AOB_PLATFORM]
    try:
        response = lambda_client.invoke(FunctionName='TrustMechanism',
                                        InvocationType='RequestResponse',
                                        Payload=json.dumps(lambda_request_data))
    except Exception as e:
        logger.error(f"Error retrieving parameters from parameter store:\n{str(e)}")
        raise Exception(f"Error retrieving parameters from parameter store: {str(e)}")

    json_parsed_response = json.load(response['Payload'])
    # parsing the parameters, json_parsed_response is a list of dictionaries
    logger.debug("Starting to parse results from parameter store")
    try:
        for ssm_store_item in json_parsed_response:
            if ssm_store_item['Name'] == VAULT_USER_PARAM:
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
            elif ssm_store_item['Name'] == AOB_USERNAME:
                EC2UsernameTag = ssm_store_item['Value']
            elif ssm_store_item['Name'] == AOB_SAFE:
                EC2SafeTag = ssm_store_item['Value']
            elif ssm_store_item['Name'] == AOB_PLATFORM:
                EC2PlatformTag = ssm_store_item['Value']
            else:
                continue
    except Exception as e:
        logger.error(f"Error parsing parameters from parameter parameter store:\n{str(e)}")
        raise Exception(f"Error parsing parameters from parameter parameter store: {str(e)}")

    logger.debug("Completed parsing results from parameter store")
    store_parameters_class = StoreParameters(vault_username, vault_password, pvwa_ip,
                                             key_pair_safe_name, pvwa_verification_key, 
                                             aob_mode, debug_level, EC2UsernameTag,
                                             EC2SafeTag, EC2PlatformTag)
    return store_parameters_class


def put_instance_to_dynamo_table(instance_id, ip_address, on_board_status, on_board_error="None", log_name="None"):
    logger.trace(instance_id, ip_address, on_board_status, on_board_error, log_name, caller_name='put_instance_to_dynamo_table')
    logger.debug(f"Adding  '{instance_id}' to DynamoDB")
    dynamodb_resource = boto3.resource('dynamodb')
    instances_table = dynamodb_resource.Table("Instances")
    try:
        instances_table.put_item(
            Item={
                'InstanceId': instance_id,
                'Address': ip_address,
                'Status': on_board_status,
                'Error': on_board_error,
                'LogId': log_name
            }
        )
    except Exception:
        logger.error('Exception occurred on add item to DynamoDB')
        return False

    logger.debug(f"Item '{instance_id}' added successfully to DynamoDB")
    return True


def release_session_on_dynamo(session_id, session_guid, sessions_table_lock_client=False):
    logger.trace(session_id, session_guid, caller_name='release_session_on_dynamo')
    logger.debug('Releasing session lock from DynamoDB')
    try:
        if not sessions_table_lock_client:
            sessions_table_lock_client = LockerClient('Sessions')
        sessions_table_lock_client.locked = True
        sessions_table_lock_client.guid = session_guid
        sessions_table_lock_client.release(session_id)
    except Exception as e:
        logger.error(f'Failed to release session lock from DynamoDB: {str(e)}')
        return False

    return True


def remove_instance_from_dynamo_table(instance_id):
    logger.trace(instance_id, caller_name='remove_instance_from_dynamo_table')
    logger.debug(f"Removing '{instance_id}' from DynamoDB")
    dynamodb_resource = boto3.resource('dynamodb')
    instances_table = dynamodb_resource.Table("Instances")
    try:
        instances_table.delete_item(
            Key={
                'InstanceId': instance_id
            }
        )
    except Exception as e:
        logger.error(f"Exception occurred on deleting '{instance_id}' on dynamodb:\n{str(e)}")
        return False

    logger.debug(f"Item '{instance_id}' successfully deleted from DB")
    return True


def get_session_from_dynamo(sessions_table_lock_client=False):
    logger.debug("Getting available Session from DynamoDB")
    if not sessions_table_lock_client:
        sessions_table_lock_client = LockerClient('Sessions')

    timeout = 20000  # Setting the timeout to 20 seconds on a row lock
    random_session_number = str(random.randint(1, 100))  # A number between 1 and 100

    try:
        for i in range(0, 20):

            lock_response = sessions_table_lock_client.acquire(random_session_number, timeout)
            if lock_response:  # no lock on connection number, return it
                logger.debug("Successfully retrieved session from DynamoDB")
                return random_session_number, sessions_table_lock_client.guid
            else:  # connection number is locked, retry in 5 seconds
                time.sleep(5)
                continue
        #  if reached here, 20 retries with 5 seconds between retry - ended
        logger.debug("Connection limit has been reached")
        return False, ""
    except Exception as e:
        logger.error(f"Failed to retrieve session from DynamoDB: {str(e)}")
        raise Exception(f"Exception on get_session_from_dynamo:{str(e)}")


def update_instances_table_status(instance_id, status, error="None"):
    logger.trace(instance_id, status, error, caller_name='update_instances_table_status')
    logger.debug(f"Updating DynamoDB with '{instance_id}' onboarding status. \nStatus: {status}")
    try:
        dynamodb_resource = boto3.resource('dynamodb')
        instances_table = dynamodb_resource.Table("Instances")
        instances_table.update_item(
            Key={
                'InstanceId': instance_id
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
    except Exception as e:
        logger.error(f'Exception occurred on updating session on DynamoDB {e}')
        return False
    logger.debug("Instance data updated successfully")
    return True


class StoreParameters:

    vault_username = ""
    vault_password = ""
    pvwa_url = "https://{0}/PasswordVault"
    key_pair_safe_name = ""
    pvwa_verification_key = ""
    aob_mode = ""


    def __init__(self, username, password, ip, key_pair_safe, pvwa_verification_key, mode,
                 debug, EC2UsernameTag, EC2SafeTag, EC2PlatformTag):
        self.vault_username = username
        self.vault_password = password
        self.pvwa_url = f"https://{ip}/PasswordVault"
        self.key_pair_safe_name = key_pair_safe
        self.pvwa_verification_key = pvwa_verification_key
        self.aob_mode = mode
        self.debug_level = debug
        self.EC2UsernameTag = EC2UsernameTag
        self.EC2SafeTag = EC2SafeTag
        self.EC2PlatformTag = EC2PlatformTag
