import boto3
import json
import requests
import urllib3
import subprocess
import time
import random
from dynamo_lock import LockerClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


DEFAULT_HEADER = {"content-type": "application/json"}
UNIX_PLATFORM = "UnixSSHKeys"
WINDOWS_PLATFORM = "WinServerLocal"
ADMINISTRATOR = "Administrator"

# return ec2 instance relevant data:
# keyPair_name, instance_address, platform
def get_ec2_details(instanceId, context):
    try:
        ec2Resource = boto3.resource('ec2')
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

    try:
        awsAccountId = context.invoked_function_arn.split(':')[4]
    except Exception:
        print("AWS account Id wasn't found")
        awsAccountId = ""

    if not imageDescription:
        raise Exception("Determining OS type failed")

    details = dict()
    details['key_name'] = instanceResource.key_name
    details['address'] = address
    details['platform'] = instanceResource.platform
    details['image_description'] = imageDescription
    details['aws_account_id'] = awsAccountId
    return details


def call_rest_api_post(url, request, header):

    try:
        restResponse = requests.post(url, data=request, timeout=30, verify=False, headers=header, stream=True)
    except Exception:
        print("Error occurred during POST request to PVWA")
        return None
    return restResponse


# performs logon to PVWA and return the session token
def logon_pvwa(username, password, pvwaUrl, connectionSessionId):
    print('Start Logon to PVWA REST API')
    logonUrl = '{0}/WebServices/auth/Cyberark/CyberArkAuthenticationService.svc/Logon'.format(pvwaUrl)
    restLogonData = """{{
        "username": "{0}",
        "password": "{1}",
        "connectionNumber": "{2}"
        }}""".format(username, password, connectionSessionId)
    try:
        restResponse = call_rest_api_post(logonUrl, restLogonData, DEFAULT_HEADER)
    except Exception:
        raise Exception("Error occurred on Logon to PVWA")

    if not restResponse:
        print("Connection to PVWA reached timeout")
        raise Exception("Connection to PVWA reached timeout")
    if restResponse.status_code == requests.codes.ok:
        jsonParsedResponse = restResponse.json()
        print("User authenticated")
        # jsonParsedResponse['CyberArkLogonResult'] is the session token #
        return jsonParsedResponse['CyberArkLogonResult']
    else:
        print("Authentication failed to REST API")
        raise Exception("Authentication failed to REST API")


def logoff_pvwa(pvwaUrl, connectionSessionToken):
    print('Start Logoff to PVWA REST API')
    header = DEFAULT_HEADER
    header.update({"Authorization": connectionSessionToken})
    logoffUrl = '{0}/WebServices/auth/Cyberark/CyberArkAuthenticationService.svc/Logoff'.format(pvwaUrl)
    restLogoffData = ""
    try:
        restResponse = call_rest_api_post(logoffUrl, restLogoffData, DEFAULT_HEADER)
    except Exception:
        # if couldn't logoff, nothing to do, return
        return

    if(restResponse.status_code == requests.codes.ok):
        jsonParsedResponse = restResponse.json()
        print("session logged off successfully")
        return True
    else:
        print("Logoff failed")
        return False


def create_account_on_vault(session, account_name, account_password, storeParametersClass, platform_id, address, instanceId, username, safeName):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    url = "{0}/WebServices/PIMServices.svc/Account".format(storeParametersClass.pvwaURL)
    data = """{{
      "account" : {{
        "safe":"{0}",
        "platformID":"{1}",
        "address":"{5}",
        "accountName":"{2}",
        "password":"{3}",
        "username":"{4}",
        "disableAutoMgmt":"false"
      }}
    }}""".format(safeName, platform_id, account_name, account_password,  username, address)
    restResponse = call_rest_api_post(url, data, header)
    if restResponse.status_code == requests.codes.created:
        print("Account for {0} was successfully created".format(instanceId))
        return True, ""
    else:
        print('Failed to create the account for {0} from the vault. status code:{1}'.format(instanceId, restResponse.status_code))
        return False, "Error Creating Account, Status Code:{0}".format(restResponse.status_code)


def rotate_credentials_immediately(session, pvwaUrl, accountId, instanceId):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    url = "{0}/API/Accounts/{1}/Change".format(pvwaUrl, accountId)
    data = ""
    restResponse = call_rest_api_post(url, data, header)
    if restResponse.status_code == requests.codes.ok:
        print("Call for immediate key change for {0} performed successfully".format(instanceId))
        return True
    else:
        print('Failed to call key change for {0}. an error occurred'.format(instanceId))
        return False


def get_account_value(session, account, instanceId, restURL):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    pvwaUrl = "{0}/API/Accounts/{1}/Content?Reason={2}".format(restURL, account, "Auto Retrieve account for AWS")
    restResponse = call_rest_api_get(pvwaUrl, header)
    if restResponse.status_code == requests.codes.ok:
        return restResponse.text
    elif restResponse.status_code == requests.codes.not_found:
        print("Account {0} for instance {1}, not found on vault".format(account, instanceId))
        return False
    else:
        print("Unexpected result from rest service - get account value, status code: {0}".format(restResponse.status_code))
        return False


def delete_account_from_vault(session, accountId, instanceId, pvwaUrl):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    restUrl = "{0}/WebServices/PIMServices.svc/Accounts/{1}".format(pvwaUrl, accountId)
    restResponse = call_rest_api_delete(restUrl, header)

    if restResponse.status_code != requests.codes.ok:
        if restResponse.status_code != requests.codes.not_found:
            print("Failed to delete the account for {0} from the vault. The account does not exists".format(instanceId))
            raise Exception("Failed to delete the account for {0} from the vault. The account does not exists".format(instanceId))

        else:
            print("Failed to delete the account for {0} from the vault. an error occurred".format(instanceId))
            raise Exception("Unknown status code received {0}".format(restResponse.status_code))

    print("The account for {0} was successfully deleted".format(instanceId))
    return True


def call_rest_api_delete(url, header):
    try:
        response = requests.delete(url, timeout=30, verify=False, headers=header)
    except Exception as e:
        print(e)
        return None
    return response


def call_rest_api_get(url, header):
    try:
        restResponse = requests.get(url, timeout=30, verify=False, headers=header)
    except Exception as e:
        print("Error occurred on calling PVWA REST service")
        return None
    return restResponse


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

def save_key_pair(pemKey):
    # Save pem to file
    savePemToFileCommand = 'echo {0} > /tmp/pemValue.pem'.format(pemKey)
    subprocess.call([savePemToFileCommand], shell=True)
    subprocess.call(["chmod 777 /tmp/pemValue.pem"], shell=True)

def convert_pem_to_ppk(pemKey):

    #  convert pem file, get ppk value
    #  Uses Puttygen sent to the lambda
    save_key_pair(pemKey=pemKey)
    subprocess.call(["cp ./puttygen /tmp/puttygen"], shell=True)
    subprocess.call(["chmod 777 /tmp/puttygen "], shell=True)
    subprocess.check_output("ls /tmp -l", shell=True)
    subprocess.check_output("cat /tmp/pemValue.pem", shell=True)
    conversionResult = subprocess.call(["/tmp/puttygen /tmp/pemValue.pem -O private -o /tmp/ppkValue.ppk"], shell=True)
    if conversionResult == 0:
        ppkKey = subprocess.check_output("cat /tmp/ppkValue.ppk", shell=True).decode("utf-8")
        print("Pem key successfully converted")
    else:
        print("Failed to convert pem key to ppk")
        return False

    return ppkKey

# def convert_pem_to_password(pemKey, passwordData):
#     save_key_pair(pemKey)
#     subprocess.call("")
# # rc, decryptedPassword = run_command_on_container(["echo", str.strip(instancePasswordData), "|", "base64", "--decode", "|", "openssl", "rsautl", "-decrypt", "-inkey", "/tmp/pemValue.pem"], True)

def get_params_from_param_store():
    # Parameters that will be retrieved from parameter store
    UNIX_SAFE_NAME_PARAM = "Unix_Safe_Name"
    WINDOWS_SAFE_NAME_PARAM = "Windows_Safe_Name"
    VAULT_USER_PARAM = "Vault_User"
    PVWA_IP_PARAM = "PVWA_IP"
    AWS_KEYPAIR_SAFE = "KeyPair_Safe"
    VAULT_PASSWORD_PARAM_ = "Vault_Pass"
    lambdaClient = boto3.client('lambda')

    lambdaRequestData = dict()
    lambdaRequestData["Parameters"] = [UNIX_SAFE_NAME_PARAM, WINDOWS_SAFE_NAME_PARAM, VAULT_USER_PARAM,  PVWA_IP_PARAM, AWS_KEYPAIR_SAFE, VAULT_PASSWORD_PARAM_]
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
        else:
            continue
    storeParametersClass = StoreParameters(unixSafeName, windowsSafeName, vaultUsername, vaultPassword, pvwaIP, keyPairSafeName)

    return storeParametersClass


def retrieve_accountId_from_account_name(session, accountName, safeName, instanceId, restURL):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})

    # 2 options of search - if safe name not empty, add it to query, if not - search without it
    if safeName:  # has value
        pvwaUrl = "{0}/WebServices/PIMServices.svc/Accounts?Keywords={1}&Safe={2}".format(restURL, accountName, safeName)
    else:  # has no value
        pvwaUrl = "{0}/WebServices/PIMServices.svc/Accounts?Keywords={1}".format(restURL, accountName)

    restResponse = call_rest_api_get(pvwaUrl, header)
    if not restResponse:
        raise Exception("Unknown Error when calling rest service - retrieve accountId")

    if restResponse.status_code == requests.codes.ok:
        # if response received, check account is not empty {"Count": 0,"accounts": []}
        if 'accounts' in restResponse.json() and restResponse.json()["accounts"]:
            parsedJsonResponse = restResponse.json()['accounts']
            return parsedJsonResponse[0]['AccountID']
        else:
            return False
    else:
        raise Exception("Status code {0}, received from REST service".format(restResponse.status_code))


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


def delete_instance(instanceId, session, storeParametersClass, instanceData, instanceDetails):
    instanceIpAddress = instanceData["Address"]["S"]
    if instanceDetails['platform'] == "windows":
        safeName = storeParametersClass.windowsSafeName
        instanceUsername = ADMINISTRATOR
    else:
        safeName = storeParametersClass.unixSafeName
        instanceUsername = get_OS_distribution_user(instanceDetails['image_description'])
    searchPattern = "{0},{1}".format(instanceIpAddress, instanceUsername)
    instanceAccountId = retrieve_accountId_from_account_name(session, searchPattern,
                                                safeName, instanceId,
                                                storeParametersClass.pvwaURL)
    if not instanceAccountId:
        print("Instance AccountId not found on safe")
        return
    delete_account_from_vault(session, instanceAccountId, instanceId, storeParametersClass.pvwaURL)

    remove_instance_from_dynamo_table(instanceId)
    return

def print_process_outputs_on_end(p):
    out = p.communicate()[0].decode('utf-8')
    # out = filter(None, map(str.strip, out.decode('utf-8').split('\n')))
    return out

def run_command_on_container(command, print_output):
    decryptedPassword= ""
    with subprocess.Popen(' '.join(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True) as p:
        if print_output:
            decryptedPassword = print_process_outputs_on_end(p)
        else:
            p.wait()
    return [p.returncode, decryptedPassword]

def get_instance_password_data(instanceId):
    # wait until password data available when Windows instance is up
    ec2 = boto3.client('ec2')
    print("Waiting for instance - {0} to become available: ".format(instanceId))
    waiter = ec2.get_waiter('password_data_available')
    waiter.wait(InstanceId=instanceId)
    instancePasswordData = ec2.get_password_data(InstanceId=instanceId)
    return instancePasswordData['PasswordData']

def create_instance(instanceId, session, instanceDetails, storeParametersClass, logName):
    # get key pair

    # Retrieving the account id of the account where the instance keyPair is stored
    try:
        currentSession = boto3.session.Session()
        awsRegionName = currentSession.region_name
    except Exception:
        print("AWS region name could not be retrieved")
        raise Exception("AWS region name could not be retrieved")
    # AWS.<AWS Account>.<Region name>.<key pair name>
    keyPairValueOnSafe = "AWS.{0}.{1}.{2}".format(instanceDetails["aws_account_id"], awsRegionName, instanceDetails["key_name"])
    keyPairAccountId = retrieve_accountId_from_account_name(session, keyPairValueOnSafe,
                                                            storeParametersClass.keyPairSafeName, instanceId,
                                                            storeParametersClass.pvwaURL)
    if not keyPairAccountId:
        print("Key Pair '{0}' does not exist in safe '{1}'".format(keyPairValueOnSafe, storeParametersClass.keyPairSafeName))
        return

    instanceAccountPassword = get_account_value(session, keyPairAccountId, instanceId, storeParametersClass.pvwaURL)
    if instanceAccountPassword is False:
        return

    if instanceDetails['platform'] == "windows":  # Windows machine return 'windows' all other return 'None'
        save_key_pair(instanceAccountPassword)
        instancePasswordData = get_instance_password_data(instanceId)
        # decryptedPassword = convert_pem_to_password(instanceAccountPassword, instancePasswordData)
        rc, decryptedPassword = run_command_on_container(["echo", str.strip(instancePasswordData), "|", "base64", "--decode", "|", "openssl", "rsautl", "-decrypt", "-inkey", "/tmp/pemValue.pem"], True)
        AWSAccountName = 'AWS.{0}.Windows'.format(instanceId)
        instanceKey = decryptedPassword
        platform = WINDOWS_PLATFORM
        instanceUsername = ADMINISTRATOR
        safeName = storeParametersClass.windowsSafeName
    else:
        ppkKey = convert_pem_to_ppk(instanceAccountPassword)
        if not ppkKey:
            raise Exception("Error on key conversion")
        # ppkKey contains \r\n on each row end, adding escape char '\'
        trimmedPPKKey = str(ppkKey).replace("\n", "\\n")
        instanceKey = trimmedPPKKey.replace("\r", "\\r")
        AWSAccountName = 'AWS.{0}.Unix'.format(instanceId)
        platform = UNIX_PLATFORM
        safeName = storeParametersClass.unixSafeName
        instanceUsername = get_OS_distribution_user(instanceDetails['image_description'])

    # Check if account already exist - in case exist - just add it to DynamoDB

    searchAccountPattern = "{0},{1}".format(instanceDetails["address"], instanceUsername)
    existingInstanceAccountId = retrieve_accountId_from_account_name(session, searchAccountPattern, safeName,
                                                                     instanceId, storeParametersClass.pvwaURL)
    if existingInstanceAccountId:  # account already exist and managed on vault, no need to create it again
        print("Account already exists in vault")
        put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded, "None", logName)
        return
    else:
        accountCreated, errorMessage = create_account_on_vault(session, AWSAccountName, instanceKey, storeParametersClass,
                                                               platform, instanceDetails['address'], instanceId, instanceUsername, safeName)

        if accountCreated:
            # if account created, rotate the key immediately
            instanceAccountId = retrieve_accountId_from_account_name(session, searchAccountPattern, safeName,
                                                                     instanceId, storeParametersClass.pvwaURL)

            rotate_credentials_immediately(session, storeParametersClass.pvwaURL, instanceAccountId, instanceId)
            put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded, "None", logName)
        else:  # on board failed, add the error to the table
            put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded_Failed, errorMessage, logName)


def lambda_handler(event, context):

    logName = context.log_stream_name if context.log_stream_name else "None"
    instanceId, actionType = event.split(";")
    try:
        instanceDetails = get_ec2_details(instanceId, context)

        instanceData = get_instance_data_from_dynamo_table(instanceId)
        if actionType == 'terminated':
            if not instanceData:
                print('Item {0} does not exists on DB'.format(instanceId))
                return None
            else:
                instanceStatus = instanceData["Status"]["S"]
                if instanceStatus == OnBoardStatus.OnBoarded_Failed:
                    print("Item {0} is in status OnBoard failed, removing from DynamoDB table".format(instanceId))
                    remove_instance_from_dynamo_table(instanceId)
                    return None
        elif actionType == 'running':
            if not instanceDetails["address"]:  # In case querying AWS return empty address
                print("Retrieving Instance address from AWS failed.")
                return None
            if instanceData:
                instanceStatus = instanceData["Status"]["S"]
                if instanceStatus == OnBoardStatus.OnBoarded:
                    print('Item: {0}, exists on DB, no need to add it to vault'.format(instanceId))
                    return None
                elif instanceStatus == OnBoardStatus.OnBoarded_Failed:
                    print("Item {0} exists with status 'OnBoard failed', adding to vault".format(instanceId))
                else:
                    print('Item {0} does not exists on DB, adding to vault'.format(instanceId))
        else:
            print('Unknown instance state')
            return

        storeParametersClass = get_params_from_param_store()
        if not storeParametersClass:
            return
        pvwaConnectionnumber, sessionGuid = get_available_session_from_dynamo()
        if not pvwaConnectionnumber:
            return
        sessionToken = logon_pvwa(storeParametersClass.vaultUsername, storeParametersClass.vaultPassword,
                                  storeParametersClass.pvwaURL, pvwaConnectionnumber)
        if not sessionToken:
            return
        if actionType == 'terminated':
            delete_instance(instanceId, sessionToken, storeParametersClass, instanceData, instanceDetails)
        elif actionType == 'running':
            create_instance(instanceId, sessionToken, instanceDetails, storeParametersClass, logName)
        else:
            print('Unknown instance state')
            return

        logoff_pvwa(storeParametersClass.pvwaURL, sessionToken)
        release_session_on_dynamo(pvwaConnectionnumber, sessionGuid)

    except Exception as e:
        print("Unknown error occurred:{0}".format(e))
        if actionType == 'terminated':
            # put_instance_to_dynamo_table(instanceId, instanceDetails["address"], OnBoardStatus.Delete_Failed, str(e), logName)
            update_instances_table_status(instanceId, OnBoardStatus.Delete_Failed, str(e))
        elif actionType == 'running':
            put_instance_to_dynamo_table(instanceId, instanceDetails["address"], OnBoardStatus.OnBoarded_Failed, str(e), logName)
        # TODO: Retry mechanism?
        release_session_on_dynamo(pvwaConnectionnumber, sessionGuid)
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


def release_session_on_dynamo(sessionId, sessionGuid):
    try:
        sessionsTableLockClient = LockerClient('Sessions')
        sessionsTableLockClient.locked = True
        sessionsTableLockClient.guid = sessionGuid
        sessionsTableLockClient.release(sessionId)
    except Exception:
        return False

    return True


def get_OS_distribution_user(imageDescription):

    if "centos" in (imageDescription.lower()):
        linuxUsername = "root"
    elif "ubuntu" in (imageDescription.lower()):
        linuxUsername = "ubuntu"
    elif "debian" in (imageDescription.lower()):
        linuxUsername = "admin"
    elif "fedora" in (imageDescription.lower()):
        linuxUsername = "fedora"
    elif "opensuse" in (imageDescription.lower()):
        linuxUsername = "root"
    else:
        linuxUsername = "ec2-user"

    return linuxUsername


class StoreParameters:
    unixSafeName = ""
    windowsSafeName = ""
    vaultUsername = ""
    vaultPassword = ""
    pvwaURL = "https://{0}/PasswordVault"
    keyPairSafeName = ""

    def __init__(self, unixSafeName, windowsSafeName, username, password, ip, keyPairSafe):
        self.unixSafeName = unixSafeName
        self.windowsSafeName = windowsSafeName
        self.vaultUsername = username
        self.vaultPassword = password
        self.pvwaURL = self.pvwaURL.format(ip)
        self.keyPairSafeName = keyPairSafe


class OnBoardStatus:
    OnBoarded = "on boarded"
    OnBoarded_Failed = "on board failed"
    Delete_Failed = "delete failed"
