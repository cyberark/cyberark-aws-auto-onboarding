import boto3
import json
import time
import random
from log_mechanism import log_mechanism
from dynamo_lock import LockerClient

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = log_mechanism()

# return ec2 instance relevant data:
# keyPair_name, instance_address, platform
def get_ec2_details(instanceId, solutionAccountId, eventRegion, eventAccountId):
    logger.trace(instanceId, solutionAccountId, eventRegion, eventAccountId, caller_name='get_ec2_details')
    logger.info('Gathering details about EC2 - ' + instanceId )
    if eventAccountId == solutionAccountId:
        try:
            ec2Resource = boto3.resource('ec2', eventRegion)
        except Exception as e:
            logger.error('Error on creating boto3 session: {0}'.format(str(e)))
    else:
        try:
            logger.info('Assuming Role')
            sts_connection = boto3.client('sts')
            acct_b = sts_connection.assume_role(
                RoleArn="arn:aws:iam::{0}:role/CyberArk-AOB-AssumeRoleForElasticityLambda".format(eventAccountId),
                RoleSessionName="cross_acct_lambda"
            )

            ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
            SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
            SESSION_TOKEN = acct_b['Credentials']['SessionToken']

            # create service client using the assumed role credentials, e.g. S3
            ec2Resource = boto3.resource(
                'ec2',
                region_name=eventRegion,
                aws_access_key_id=ACCESS_KEY,
                aws_secret_access_key=SECRET_KEY,
                aws_session_token=SESSION_TOKEN,
            )
        except Exception as e:
            logger.error('Error on getting token from account: {0}'.format(eventAccountId))


    try:
        instanceResource = ec2Resource.Instance(instanceId)
        instanceImage = ec2Resource.Image(instanceResource.image_id)
        logger.info('Image Detected: ' + str(instanceImage))
        imageDescription = instanceImage.description
    except Exception as e:
        logger.error('Error on getting instance details: {0}'.format(str(e)))
        raise e

    #  We take the instance address in the order of: public dns -> public ip -> private ip ##
    if instanceResource.private_ip_address:
        address = instanceResource.private_ip_address
    else:  # unable to retrieve address from aws
        address = None



    if not imageDescription:
        raise Exception("Determining OS type failed")

    details = dict()
    details['key_name'] = instanceResource.key_name
    details['address'] = address
    details['platform'] = instanceResource.platform
    details['image_description'] = imageDescription
    details['aws_account_id'] = eventAccountId
    return details


# Check on DynamoDB if instance exists
# Return False when not found, or row data from table
def get_instance_data_from_dynamo_table(instanceId):
    logger.trace(instanceId, caller_name='get_instance_data_from_dynamo_table')
    logger.info('Check with DynamoDB if instance {0} exists'.format(instanceId))
    dynamoResource = boto3.client('dynamodb')

    try:
        dynamoResponse = dynamoResource.get_item(TableName='Instances', Key={"InstanceId": {"S": instanceId}})
    except Exception:
        logger.error("Error occurred when trying to call dynamoDB")
        return False
    # DynamoDB "Item" response: {'Address': {'S': 'xxx.xxx.xxx.xxx'}, 'InstanceId': {'S': 'i-xxxxxyyyyzzz'},
    #               'Status': {'S': 'on-boarded'}, 'Error': {'S': 'Some Error'}}
    if 'Item' in dynamoResponse:
        if dynamoResponse["Item"]["InstanceId"]["S"] == instanceId:
            logger.info(instanceId + ' exists in DynamoDB')
            return dynamoResponse["Item"]
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
    AOB_MODE="AOB_mode"
    AOB_DEBUG_LEVEL = "AOB_Debug_Level"
    lambdaClient = boto3.client('lambda')

    lambdaRequestData = dict()
    lambdaRequestData["Parameters"] = [UNIX_SAFE_NAME_PARAM, WINDOWS_SAFE_NAME_PARAM, VAULT_USER_PARAM, PVWA_IP_PARAM,
                                       AWS_KEYPAIR_SAFE, VAULT_PASSWORD_PARAM_, PVWA_VERIFICATION_KEY, AOB_MODE, AOB_DEBUG_LEVEL]
    try:
        response = lambdaClient.invoke(FunctionName='TrustMechanism',
                                       InvocationType='RequestResponse',
                                       Payload=json.dumps(lambdaRequestData))
    except Exception as e:
        logger.error("Error retrieving parameters from parameter parameter store:{0}".format(str(e)))
        raise Exception("Error retrieving parameters from parameter parameter store:{0}".format(str(e))) 

    jsonParsedResponse = json.load(response['Payload'])
    # parsing the parameters, jsonParsedResponse is a list of dictionaries
    for ssmStoreItem in jsonParsedResponse:
        if ssmStoreItem['Name'] == UNIX_SAFE_NAME_PARAM:
            unixSafeName = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == WINDOWS_SAFE_NAME_PARAM:
            windowsSafeName = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == VAULT_USER_PARAM:
            vaultUsername = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == PVWA_IP_PARAM:
            pvwaIP = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == AWS_KEYPAIR_SAFE:
            keyPairSafeName = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == VAULT_PASSWORD_PARAM_:
            vaultPassword = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == PVWA_VERIFICATION_KEY:
            pvwaVerificationKey = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == AOB_DEBUG_LEVEL:
            debugLevel = ssmStoreItem['Value']
        elif ssmStoreItem['Name'] == AOB_MODE:
            AOB_mode = ssmStoreItem['Value']
            if AOB_mode == 'POC':
                pvwaVerificationKey = ''
        else:
            continue
    storeParametersClass = StoreParameters(unixSafeName, windowsSafeName, vaultUsername, vaultPassword, pvwaIP,
                                           keyPairSafeName, pvwaVerificationKey, AOB_mode, debugLevel)
    return storeParametersClass


def put_instance_to_dynamo_table(instanceId, IPAddress, onBoardStatus, onBoardError="None", logName="None"):
    logger.trace(instanceId, IPAddress, onBoardStatus, onBoardError, logName, caller_name='put_instance_to_dynamo_table')
    logger.info('Adding  {instanceId} to DynamoDB'.format(instanceId=instanceId))
    dynamodbResource = boto3.resource('dynamodb')
    instancesTable = dynamodbResource.Table("Instances")
    try:
        instancesTable.put_item(
            Item={
                'InstanceId': instanceId,
                'Address': IPAddress,
                'Status': onBoardStatus,
                'Error': onBoardError,
                'LogId': logName
            }
        )
    except Exception:
        logger.error('Exception occurred on add item to DynamoDB')
        return None

    logger.info('Item {0} added successfully to DynamoDB'.format(instanceId))
    return


def release_session_on_dynamo(sessionId, sessionGuid):
    logger.trace(sessionId, sessionGuid, caller_name='release_session_on_dynamo')
    logger.info('Releasing session lock from DynamoDB')
    try:
        sessionsTableLockClient = LockerClient('Sessions')
        sessionsTableLockClient.locked = True
        sessionsTableLockClient.guid = sessionGuid
        sessionsTableLockClient.release(sessionId)
    except Exception as e:
        logger.error('Failed to release session lock from DynamoDB:\n{error}'.format(error=str(e)))
        return False

    return True


def remove_instance_from_dynamo_table(instanceId):
    logger.trace(instanceId, caller_name='remove_instance_from_dynamo_table')
    logger.info('Removing ' + instanceId +' from DynamoDB')
    dynamodbResource = boto3.resource('dynamodb')
    instancesTable = dynamodbResource.Table("Instances")
    try:
        instancesTable.delete_item(
            Key={
                'InstanceId': instanceId
            }
        )
    except Exception as e:
        logger.error('Exception occurred on deleting {instanceId} on dynamodb:\n{error}'.format(instanceId=instanceId, error=str(e)))
        return None

    logger.info('Item {0} successfully deleted from DB'.format(instanceId))
    return


def get_available_session_from_dynamo():
    logger.info("Getting available Session from DynamoDB")
    sessionsTableLockClient = LockerClient('Sessions')
    timeout = 20000  # Setting the timeout to 20 seconds on a row lock
    randomSessionNumber = str(random.randint(1, 100))  # A number between 1 and 100

    try:
        for i in range(0, 20):

            lockResponse = sessionsTableLockClient.acquire(randomSessionNumber, timeout)
            if lockResponse:  # no lock on connection number, return it
                logger.info("Successfully retrieved session from DynamoDB")
                return randomSessionNumber, sessionsTableLockClient.guid
            else:  # connection number is locked, retry in 5 seconds
                time.sleep(5)
                continue
        #  if reached here, 20 retries with 5 seconds between retry - ended
        logger.info("Connection limit has been reached")
        return False, ""
    except Exception as e:
        print("Failed to retrieve session from DynamoDB:{0}".format(str(e)))
        raise Exception("Exception on get_available_session_from_dynamo:{0}".format(str(e)))


def update_instances_table_status(instanceId, status, error="None"):
    logger.trace(instanceId, status, error, caller_name='update_instances_table_status')
    logger.info('Updating DynamoDB with {instanceId} onboarding status. \nStatus: {status}'.format(status=status,instanceId=instanceId))
    dynamodbResource = boto3.resource('dynamodb')
    instancesTable = dynamodbResource.Table("Instances")
    try:
        instancesTable.update_item(
            Key={
                'InstanceId': instanceId
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
    unixSafeName = ""
    windowsSafeName = ""
    vaultUsername = ""
    vaultPassword = ""
    pvwaURL = "https://{0}/PasswordVault"
    keyPairSafeName = ""
    pvwaVerificationKey = ""
    AOB_mode = ""

    def __init__(self, unixSafeName, windowsSafeName, username, password, ip, keyPairSafe, pvwaVerificationKey, mode, debug):
        self.unixSafeName = unixSafeName
        self.windowsSafeName = windowsSafeName
        self.vaultUsername = username
        self.vaultPassword = password
        self.pvwaURL = self.pvwaURL.format(ip)
        self.keyPairSafeName = keyPairSafe
        self.pvwaVerificationKey = pvwaVerificationKey
        self.AOB_mode = mode
        self.debugLevel = debug