import requests
import urllib3
import uuid
import cfnresponse
import botocore
import time
import boto3
import json
import pvwa_integration
import aws_services
import pvwa_api_calls
import sys
from dynamo_lock import LockerClient

sys.path.append('../')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_HEADER = {"content-type": "application/json"}

def lambda_handler(event, context):

    try:
        physicalResourceId = str(uuid.uuid4())
        if 'PhysicalResourceId' in event:
            physicalResourceId = event['PhysicalResourceId']
        # only deleting the vault_pass from parameter store
        if event['RequestType'] == 'Delete':
            if not delete_password_from_param_store():
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to delete 'Vault_Pass' from parameter store, see detailed error in logs", {}, physicalResourceId)
            delete_sessions_table()
            return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physicalResourceId)

        if event['RequestType'] == 'Create':

            requestUnixCPMName = event['ResourceProperties']['CPMUnix']
            requestWindowsCPMName = event['ResourceProperties']['CPMWindows']
            requestUsername = event['ResourceProperties']['Username']
            requestUnixSafeName = event['ResourceProperties']['UnixSafeName']
            requestWindowsSafeName = event['ResourceProperties']['WindowsSafeName']
            requestPvwaIp = event['ResourceProperties']['PVWAIP']
            requestPassword = event['ResourceProperties']['Password']
            requestKeyPairSafe = event['ResourceProperties']['KeyPairSafe']
            requestKeyPairName = event['ResourceProperties']['KeyPairName']
            requestAWSRegionName = event['ResourceProperties']['AWSRegionName']
            requestAWSAccountId = event['ResourceProperties']['AWSAccountId']
            requestS3BucketName = event['ResourceProperties']['S3BucketName']
            requestVerificationKeyName = event['ResourceProperties']['PVWAVerificationKeyFileName']
            
            
                
            isPasswordSaved = save_password_to_param_store(requestPassword, "AOB_Vault_Pass", "Vault Password")
            if not isPasswordSaved:  # if password failed to be saved
                return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to create Vault user's password in Parameter Store",
                                        {}, physicalResourceId)
                
            if requestS3BucketName != '' and requestVerificationKeyName != '':
                AOB_mode = 'Prod'
                isAOBModeSaved = save_password_to_param_store(AOB_mode,'AOB_mode',
                                                                'Dictates wether the solution will work in POC(no SSL) or Production(with SSL) mode')
                if not isAOBModeSaved:  # if password failed to be saved
                    return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to create AOB_mode parameter in Parameter Store",
                                            {}, physicalResourceId)                                    
                isVerificationKeySaved = save_verification_key_to_param_store(requestS3BucketName, requestVerificationKeyName)
                if not isVerificationKeySaved:  # if password failed to be saved
                    return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to create PVWA Verification Key in Parameter Store",
                                            {}, physicalResourceId)
            elif requestS3BucketName == '' and requestVerificationKeyName != '':
                raise Exception('Verification Key cannot be empty if S3 Bucket is provided')    
            elif requestS3BucketName != '' and requestVerificationKeyName == '':
                raise Exception('S3 Bucket cannot be empty if Verification Key')
            else:
                AOB_mode = 'POC'
                isAOBModeSaved = save_password_to_param_store(AOB_mode,'AOB_mode',
                                                                'Dictates wether the solution will work in POC(no SSL) or Production(with SSL) mode')

            pvwaSessionId = aws_services.logon_pvwa(requestUsername, requestPassword, requestPvwaIp,"1")
            if not pvwaSessionId:
                return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to connect to PVWA, see detailed error in logs",
                                        {}, physicalResourceId)

            isSafeCreated = create_safe(requestUnixSafeName, requestUnixCPMName, requestPvwaIp, pvwaSessionId, 1)

            if not isSafeCreated:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create the Safe '{0}', see detailed error in logs".format(requestUnixSafeName),
                                        {}, physicalResourceId)

            isSafeCreated = create_safe(requestWindowsSafeName, requestWindowsCPMName, requestPvwaIp, pvwaSessionId, 1)

            if not isSafeCreated:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create the Safe '{0}', see detailed error in logs".format(
                                            requestWindowsSafeName),
                                        {}, physicalResourceId)

            if not create_session_table():
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create 'Sessions' table in DynamoDB, see detailed error in logs",
                                        {}, physicalResourceId)

            #  Creating KeyPair Safe
            isSafeCreated = create_safe(requestKeyPairSafe, "", requestPvwaIp, pvwaSessionId)
            if not isSafeCreated:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create the Key Pairs safe: {0}, see detailed error in logs".format(requestKeyPairSafe),
                                        {}, physicalResourceId)

            #  key pair is optional parameter
            if not requestKeyPairName:
                print("Key Pair name parameter is empty, the solution will not create a new Key Pair")
                return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physicalResourceId)
            else:
                awsKeypair = create_new_key_pair_on_AWS(requestKeyPairName)

                if awsKeypair is False:
                    # Account already exist, no need to create it, can't insert it to the vault
                    return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to create Key Pair '{0}' in AWS".format(requestKeyPairName),
                                            {}, physicalResourceId)
                if awsKeypair is True:
                    return cfnresponse.send(event, context, cfnresponse.FAILED, "Key Pair '{0}' already exists in AWS".format(requestKeyPairName),
                                            {}, physicalResourceId)
                # Create the key pair account on KeyPairs vault
                isAwsAccountCreated = create_key_pair_in_vault(pvwaSessionId, requestKeyPairName, awsKeypair, requestPvwaIp,
                                                              requestKeyPairSafe, requestAWSAccountId, requestAWSRegionName)
                if not isAwsAccountCreated:
                    return cfnresponse.send(event, context, cfnresponse.FAILED,
                                            "Failed to create Key Pair {0} in safe {1}. see detailed error in logs".format(requestKeyPairName, requestKeyPairSafe),
                                            {}, physicalResourceId)

                return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physicalResourceId)

    except Exception as e:
        print("Exception occurred:{0}:".format(e))
        return cfnresponse.send(event, context, cfnresponse.FAILED, "Exception occurred: {0}".format(e), {})

    finally:
        if 'pvwaSessionId' in locals():  # pvwaSessionId has been declared
            if pvwaSessionId:  # Logging off the session in case of successful logon
                pvwa_integration.logoff_pvwa(requestPvwaIp, pvwaSessionId)


# Creating a safe, if a failure occur, retry 3 time, wait 10 sec. between retries
def create_safe(safeName, cpmName, pvwaIP, sessionId, numberOfDaysRetention=7):
    header = DEFAULT_HEADER
    header.update({"Authorization": sessionId})
    createSafeUrl = "https://{0}/PasswordVault/WebServices/PIMServices.svc/Safes".format(pvwaIP)
    # Create new safe, default number of days retention is 7, unless specified otherwise
    data = """
                {{
          "safe":{{
        "SafeName":"{0}",
        "Description":"",
        "OLACEnabled":false,
        "ManagingCPM":"{1}",
        "NumberOfDaysRetention":"{2}"
          }}
        }}
    """.format(safeName, cpmName, numberOfDaysRetention)

    for i in range(0, 3):
        createSafeRestResponse = pvwa_api_calls.call_rest_api_post(createSafeUrl, data, header)

        if createSafeRestResponse.status_code == requests.codes.conflict:
            print("The Safe '{0}' already exists".format(safeName))
            return True
        elif createSafeRestResponse.status_code == requests.codes.bad_request:
            print("Failed to create safe '{0}', error 400: bad request".format(safeName))
            return False
        elif createSafeRestResponse.status_code == requests.codes.created:  # safe created
            print("The Safe '{0}' was successfully created".format(safeName))
            return True
        else:  # Error creating safe, retry for 3 times, with 10 seconds between retries
            print("Error creating safe, status code:{0}, will retry in 10 seconds".format(createSafeRestResponse.status_code))
            if i == 3:
                print("Failed to create safe after several retries, status code:{0}"
                      .format(createSafeRestResponse.status_code))
                return False
        time.sleep(10)


# Search if Key pair exist, if not - create it, return the pem key, False for error
def create_new_key_pair_on_AWS(keyPairName):
    ec2Client = boto3.client('ec2')

    # throws exception if key not found, if exception is InvalidKeyPair.Duplicate return True
    try:

        keyPairResponse = ec2Client.create_key_pair(
            KeyName=keyPairName,
            DryRun=False
        )
    except Exception as e:
        if e.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            print("Key Pair '{0}' already exists".format(keyPairName))
            return True
        else:
            print("Creating new Key Pair failed. error code: {0}".format(e.response["Error"]["Code"]))
            return False

    return keyPairResponse["KeyMaterial"]


def create_key_pair_in_vault(session, awsKeyName, privateKeyValue, pvwaIP, safeName, awsAccountId, awsRegionName):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})

    trimmedPEMKey = str(privateKeyValue).replace("\n", "\\n")
    trimmedPEMKey = trimmedPEMKey.replace("\r", "\\r")

    # AWS.<AWS Account>.<Region name>.<key pair name>
    uniqueUsername = "AWS.{0}.{1}.{2}".format(awsAccountId, awsRegionName, awsKeyName)
    print("Creating account with username:{0}".format(uniqueUsername))

    url = "https://{0}/PasswordVault/WebServices/PIMServices.svc/Account".format(pvwaIP)
    data = """{{
      "account" : {{
        "safe":"{0}",
        "platformID":"{1}",
        "address":1.1.1.1,
        "password":"{2}",
        "username":"{3}",
        "disableAutoMgmt":"true",
        "disableAutoMgmtReason":"Unmanaged account"
      }}
    }}""".format(safeName, "UnixSSHKeys", trimmedPEMKey, uniqueUsername)
    restResponse = pvwa_api_calls.call_rest_api_post(url, data, header)

    if restResponse.status_code == requests.codes.created:
        print("Key Pair created successfully in safe '{0}'".format(safeName))
        return True
    elif restResponse.status_code == requests.codes.conflict:
        print("Key Pair created already exists in safe {0}".format(safeName))
        return True
    else:
        print("Failed to create Key Pair in safe '{0}', status code:{1}".format(safeName, restResponse.status_code))
        return False

def create_session_table():
    try:
        sessionsTableLock = LockerClient('Sessions')
        sessionsTableLock.create_lock_table()
    except Exception as e:
        print("Failed to create 'Sessions' table in DynamoDB. Exception: {0}".format(e))
        return None

    print("Table 'Sessions' created successfully")
    return True

def save_verification_key_to_param_store(S3BucketName, VerificationKeyName):
    try:
        s3Resource = boto3.resource('s3')
        s3Resource.Bucket(S3BucketName).download_file(VerificationKeyName, '/tmp/server.crt')
        save_password_to_param_store(open('/tmp/server.crt').read(),"AOB_PVWA_Verification_Key","PVWA Verification Key")
    except Exception as e:
        print("An error occurred while downloading Verification Key from S3 Bucket - {0}. Exception: {1}".format(S3BucketName, e))
        return False
    return True



def save_password_to_param_store(value, parameterName, parameterDescription):
    try:
        ssmClient = boto3.client('ssm')
        ssmClient.put_parameter(
            Name=parameterName,
            Description=parameterDescription,
            Value=value,
            Type="SecureString"
        )
    except Exception as e:
        print("Unable to create parameter '{0}' in Parameter Store. Exception: {1}".format(parameterName, e))
        return False
    return True


def delete_password_from_param_store():
    try:
        ssmClient = boto3.client('ssm')
        ssmClient.delete_parameter(
            Name='AOB_Vault_Pass'
        )
        print("Parameter 'AOB_Vault_Pass' deleted successfully from Parameter Store")
        ssmClient.delete_parameter(
            Name='AOB_PVWA_Verification_Key'
        )
        print("Parameter 'AOB_PVWA_Verification_Key' deleted successfully from Parameter Store")
        return True
    except Exception as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return True
        else:
            print("Failed to delete parameter 'Vault_Pass' from Parameter Store. Error code: {0}".format(e.response["Error"]["Code"]))
            return False


def delete_sessions_table():
    try:
        dynamodb = boto3.resource('dynamodb')
        sessionsTable = dynamodb.Table('Sessions')
        sessionsTable.delete()
        return
    except Exception:
        print("Failed to delete 'Sessions' table from DynamoDB")
        return
