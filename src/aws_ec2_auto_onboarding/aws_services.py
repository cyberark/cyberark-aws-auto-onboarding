import boto3
import json
import time
import random
from dynamo_lock import LockerClient


# return ec2 instance relevant data:
# keyPair_name, instance_address, platform
def get_ec2_details(instanceId, solutionAccountId, eventRegion, eventAccountId):

    if eventAccountId == solutionAccountId:
        try:
            ec2Resource = boto3.resource('ec2', eventRegion)
        except Exception as e:
            print('Error on creating boto3 session: {0}'.format(e))
    else:
        try:
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
            print('Error on getting token from account: {0}'.format(eventAccountId))


    try:
        instanceResource = ec2Resource.Instance(instanceId)
        instanceImage = ec2Resource.Image(instanceResource.image_id)
        imageDescription = instanceImage.description
    except Exception as e:
        print('Error on getting instance details: {0}'.format(e))
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
    print('check with DynamoDB if instance {0} exists'.format(instanceId))
    dynamoResource = boto3.client('dynamodb')

    try:
        dynamoResponse = dynamoResource.get_item(TableName='Instances', Key={"InstanceId": {"S": instanceId}})
    except Exception:
        print("Error occurred when trying to call dynamoDB")
        return False
    # DynamoDB "Item" response: {'Address': {'S': 'xxx.xxx.xxx.xxx'}, 'InstanceId': {'S': 'i-xxxxxyyyyzzz'},
    #               'Status': {'S': 'on-boarded'}, 'Error': {'S': 'Some Error'}}
    if 'Item' in dynamoResponse:
        if dynamoResponse["Item"]["InstanceId"]["S"] == instanceId:
            return dynamoResponse["Item"]
        else:
            return False
    else:
        return False


def get_params_from_param_store():
    # Parameters that will be retrieved from parameter store
    UNIX_SAFE_NAME_PARAM = "Unix_Safe_Name"
    WINDOWS_SAFE_NAME_PARAM = "Windows_Safe_Name"
    VAULT_USER_PARAM = "Vault_User"
    PVWA_IP_PARAM = "PVWA_IP"
    AWS_KEYPAIR_SAFE = "KeyPair_Safe"
    VAULT_PASSWORD_PARAM_ = "Vault_Pass"
    PVWA_VERIFICATION_KEY = "PVWA_Verification_Key"
    lambdaClient = boto3.client('lambda')

    lambdaRequestData = dict()
    lambdaRequestData["Parameters"] = [UNIX_SAFE_NAME_PARAM, WINDOWS_SAFE_NAME_PARAM, VAULT_USER_PARAM, PVWA_IP_PARAM,
                                       AWS_KEYPAIR_SAFE, VAULT_PASSWORD_PARAM_, PVWA_VERIFICATION_KEY]
    try:
        response = lambdaClient.invoke(FunctionName='TrustMechanism',
                                       InvocationType='RequestResponse',
                                       Payload=json.dumps(lambdaRequestData))
    except Exception as e:
        print("Error on retrieving store parameters:{0}".format(e))
        raise Exception("Error occurred while retrieving store parameters")

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
        else:
            continue
    storeParametersClass = StoreParameters(unixSafeName, windowsSafeName, vaultUsername, vaultPassword, pvwaIP,
                                           keyPairSafeName, pvwaVerificationKey)

    return storeParametersClass


def put_instance_to_dynamo_table(instanceId, IPAddress, onBoardStatus, onBoardError="None", logName="None"):
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
        print('Exception occurred on add item to dynamodb')
        return None

    print('Item {0} added successfully to DB'.format(instanceId))
    return


def release_session_on_dynamo(sessionId, sessionGuid):
    try:
        sessionsTableLockClient = LockerClient('Sessions')
        sessionsTableLockClient.locked = True
        sessionsTableLockClient.guid = sessionGuid
        sessionsTableLockClient.release(sessionId)
    except Exception:
        return False

    return True


def remove_instance_from_dynamo_table(instanceId):
    dynamodbResource = boto3.resource('dynamodb')
    instancesTable = dynamodbResource.Table("Instances")
    try:
        instancesTable.delete_item(
            Key={
                'InstanceId': instanceId
            }
        )
    except Exception:
        print('Exception occurred on deleting item on dynamodb')
        return None

    print('Item {0} successfully deleted from DB'.format(instanceId))
    return


def get_available_session_from_dynamo():
    sessionsTableLockClient = LockerClient('Sessions')
    timeout = 20000  # Setting the timeout to 20 seconds on a row lock
    randomSessionNumber = str(random.randint(1, 100))  # A number between 1 and 100

    try:
        for i in range(0, 20):

            lockResponse = sessionsTableLockClient.acquire(randomSessionNumber, timeout)
            if lockResponse:  # no lock on connection number, return it
                return randomSessionNumber, sessionsTableLockClient.guid
            else:  # connection number is locked, retry in 5 seconds
                time.sleep(5)
                continue
        #  if reached here, 20 retries with 5 seconds between retry - ended
        print("No available connection after many retries")
        return False, ""
    except Exception as e:
        print("Exception on get_available_session_from_dynamo:{0}".foramt(e))
        raise Exception("Exception on get_available_session_from_dynamo:{0}".foramt(e))


def update_instances_table_status(instanceId, status, error="None"):
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
        print('Exception occurred on updating session on dynamoDB')
        return None
    print("Instance data updated successfully")
    return


class StoreParameters:
    unixSafeName = ""
    windowsSafeName = ""
    vaultUsername = ""
    vaultPassword = ""
    pvwaURL = "https://{0}/PasswordVault"
    keyPairSafeName = ""
    pvwaVerificationKey = ""

    def __init__(self, unixSafeName, windowsSafeName, username, password, ip, keyPairSafe, pvwaVerificationKey):
        self.unixSafeName = unixSafeName
        self.windowsSafeName = windowsSafeName
        self.vaultUsername = username
        self.vaultPassword = password
        self.pvwaURL = self.pvwaURL.format(ip)
        self.keyPairSafeName = keyPairSafe
        self.pvwaVerificationKey = pvwaVerificationKey