import requests
import urllib3
import uuid
import cfnresponse
import botocore
import time
import boto3
import json
from log_mechanism import log_mechanism
import aws_services
from pvwa_integration import pvwa_integration
from dynamo_lock import LockerClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
DEFAULT_HEADER = {"content-type": "application/json"}
IS_SAFE_HANDLER = True
logger = log_mechanism()

def lambda_handler(event, context):
    print(f'[PRINT] LambdaHandler:\n{event},{context}')
    logger.trace(event, context, caller_name='lambda_handler')
    try:
        physicalResourceId = str(uuid.uuid4())
        if 'PhysicalResourceId' in event:
            physicalResourceId = event['PhysicalResourceId']
        # only deleting the vault_pass from parameter store
        if event['RequestType'] == 'Delete':
            aob_mode = get_aob_mode()
            logger.info('Delete request received')
            if not delete_password_from_param_store(aob_mode):
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to delete 'AOB_Vault_Pass' from parameter store, see detailed error in logs", {}, physicalResourceId)
            delete_sessions_table()
            return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physicalResourceId)

        if event['RequestType'] == 'Create':
            logger.info('Create request received')
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
            AOB_mode = event['ResourceProperties']['Environment']
        
                
            logger.info('Adding AOB_Vault_Pass to parameter store',DEBUG_LEVEL_DEBUG)
            isPasswordSaved = add_param_to_parameter_store(requestPassword, "AOB_Vault_Pass", "Vault Password")
            if not isPasswordSaved:  # if password failed to be saved
                return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to create Vault user's password in Parameter Store",
                                        {}, physicalResourceId)
            if requestS3BucketName == '' and requestVerificationKeyName != '':
                raise Exception('Verification Key cannot be empty if S3 Bucket is provided')    
            elif requestS3BucketName != '' and requestVerificationKeyName == '':
                raise Exception('S3 Bucket cannot be empty if Verification Key is provided')
            else:
                logger.info('Adding AOB_mode to parameter store',DEBUG_LEVEL_DEBUG)
                isAOBModeSaved = add_param_to_parameter_store(AOB_mode,'AOB_mode',
                                                                'Dictates if the solution will work in POC(no SSL) or Production(with SSL) mode')
                if not isAOBModeSaved:  # if password failed to be saved
                    return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to create AOB_mode parameter in Parameter Store",
                                            {}, physicalResourceId)                                    
                if AOB_mode == 'Production':
                    logger.info('Adding verification key to Parameter Store',DEBUG_LEVEL_DEBUG)
                    isVerificationKeySaved = save_verification_key_to_param_store(requestS3BucketName, requestVerificationKeyName)
                    if not isVerificationKeySaved:  # if password failed to be saved
                        return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to create PVWA Verification Key in Parameter Store",
                                                {}, physicalResourceId)
            
            pvwa_integration_class = pvwa_integration(IS_SAFE_HANDLER, AOB_mode)
            pvwa_url = 'https://{0}/PasswordVault'.format(requestPvwaIp)
            pvwaSessionId = pvwa_integration_class.logon_pvwa(requestUsername, requestPassword, pvwa_url,"1")
            if not pvwaSessionId:
                return cfnresponse.send(event, context, cfnresponse.FAILED, "Failed to connect to PVWA, see detailed error in logs",
                                        {}, physicalResourceId)

            isSafeCreated = create_safe(pvwa_integration_class, requestUnixSafeName, requestUnixCPMName, requestPvwaIp, pvwaSessionId, 1)

            if not isSafeCreated:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create the Safe '{0}', see detailed error in logs".format(requestUnixSafeName),
                                        {}, physicalResourceId)

            isSafeCreated = create_safe(pvwa_integration_class, requestWindowsSafeName, requestWindowsCPMName, requestPvwaIp, pvwaSessionId, 1)

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
            isSafeCreated = create_safe(pvwa_integration_class, requestKeyPairSafe, "", requestPvwaIp, pvwaSessionId)
            if not isSafeCreated:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create the Key Pairs safe: {0}, see detailed error in logs".format(requestKeyPairSafe),
                                        {}, physicalResourceId)

            #  key pair is optional parameter
            if not requestKeyPairName:
                logger.info("Key Pair name parameter is empty, the solution will not create a new Key Pair")
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
                isAwsAccountCreated = create_key_pair_in_vault(pvwa_integration_class, pvwaSessionId, requestKeyPairName, awsKeypair, requestPvwaIp,
                                                              requestKeyPairSafe, requestAWSAccountId, requestAWSRegionName)
                if not isAwsAccountCreated:
                    return cfnresponse.send(event, context, cfnresponse.FAILED,
                                            "Failed to create Key Pair {0} in safe {1}. see detailed error in logs".format(requestKeyPairName, requestKeyPairSafe),
                                            {}, physicalResourceId)

                return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physicalResourceId)

    except Exception as e:
        logger.error("Exception occurred:{0}:".format(str(e)))
        return cfnresponse.send(event, context, cfnresponse.FAILED, "Exception occurred: {0}".format(str(e)), {})

    finally:
        if 'pvwaSessionId' in locals():  # pvwaSessionId has been declared
            if pvwaSessionId:  # Logging off the session in case of successful logon
                pvwa_integration_class.logoff_pvwa(requestPvwaIp, pvwaSessionId)


# Creating a safe, if a failure occur, retry 3 time, wait 10 sec. between retries
def create_safe(pvwa_integration_class, safeName, cpmName, pvwaIP, sessionId, numberOfDaysRetention=7):
    logger.trace(pvwa_integration_class, safeName, cpmName, pvwaIP, sessionId, numberOfDaysRetention, caller_name='create_safe')
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
        createSafeRestResponse = pvwa_integration_class.call_rest_api_post(createSafeUrl, data, header)

        if createSafeRestResponse.status_code == requests.codes.conflict:
            logger.info("The Safe '{0}' already exists".format(safeName))
            return True
        elif createSafeRestResponse.status_code == requests.codes.bad_request:
            logger.error("Failed to create Safe '{0}', error 400: bad request".format(safeName))
            return False
        elif createSafeRestResponse.status_code == requests.codes.created:  # safe created
            logger.info("Safe '{0}' was successfully created".format(safeName))
            return True
        else:  # Error creating safe, retry for 3 times, with 10 seconds between retries
            logger.error("Error creating Safe, status code:{0}, will retry in 10 seconds".format(createSafeRestResponse.status_code))
            if i == 3:
                logger.error("Failed to create safe after several retries, status code:{0}"
                      .format(createSafeRestResponse.status_code))
                return False
        time.sleep(10)


# Search if Key pair exist, if not - create it, return the pem key, False for error
def create_new_key_pair_on_AWS(keyPairName):
    logger.trace(keyPairName, caller_name='create_new_key_pair_on_AWS')
    ec2Client = boto3.client('ec2')

    # throws exception if key not found, if exception is InvalidKeyPair.Duplicate return True
    try:
        logger.info('Creating key pair')
        keyPairResponse = ec2Client.create_key_pair(
            KeyName=keyPairName,
            DryRun=False
        )
    except Exception as e:
        if e.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            logger.error("Key Pair '{0}' already exists".format(keyPairName))
            return True
        else:
            logger.error("Creating new key pair failed. error code:\n {0}".format(e.response["Error"]["Code"]))
            return False

    return keyPairResponse["KeyMaterial"]


def create_key_pair_in_vault(pvwa_integration_class, session, awsKeyName, privateKeyValue, pvwaIP, safeName, awsAccountId, awsRegionName):
    logger.trace(pvwa_integration_class, session, awsKeyName, privateKeyValue, pvwaIP, safeName, awsAccountId, awsRegionName,
                 caller_name='create_key_pair_in_vault')
    header = DEFAULT_HEADER
    header.update({"Authorization": session})

    trimmedPEMKey = str(privateKeyValue).replace("\n", "\\n")
    trimmedPEMKey = trimmedPEMKey.replace("\r", "\\r")

    # AWS.<AWS Account>.<Region name>.<key pair name>
    uniqueUsername = "AWS.{0}.{1}.{2}".format(awsAccountId, awsRegionName, awsKeyName)
    logger.info("Creating account with username:{0}".format(uniqueUsername))

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
    restResponse = pvwa_integration_class.call_rest_api_post(url, data, header)

    if restResponse.status_code == requests.codes.created:
        logger.info("Key Pair created successfully in safe '{0}'".format(safeName))
        return True
    elif restResponse.status_code == requests.codes.conflict:
        logger.info("Key Pair created already exists in safe {0}".format(safeName))
        return True
    else:
        logger.error("Failed to create Key Pair in safe '{0}', status code:{1}".format(safeName, restResponse.status_code))
        return False

def create_session_table():
    logger.trace(caller_name='create_session_table')
    try:
        logger.info('Locking Dynamo Table')
        sessionsTableLock = LockerClient('Sessions')
        sessionsTableLock.create_lock_table()
    except Exception as e:
        print("Failed to create 'Sessions' table in DynamoDB. Exception: {0}".format(str(e)))
        return None

    print("Table 'Sessions' created successfully")
    return True

def save_verification_key_to_param_store(S3BucketName, VerificationKeyName):
    logger.trace(S3BucketName, VerificationKeyName, caller_name='save_verification_key_to_param_store')
    try:
        logger.info('Downloading verification key from s3')
        s3Resource = boto3.resource('s3')
        s3Resource.Bucket(S3BucketName).download_file(VerificationKeyName, '/tmp/server.crt')
        add_param_to_parameter_store(open('/tmp/server.crt').read(),"AOB_PVWA_Verification_Key","PVWA Verification Key")
    except Exception as e:
        logger.error("An error occurred while downloading Verification Key from S3 Bucket - {0}. Exception: {1}".format(S3BucketName, e))
        return False
    return True



def add_param_to_parameter_store(value, parameterName, parameterDescription):
    logger.trace(value, parameterName, parameterDescription, caller_name='add_param_to_parameter_store')
    try:
        logger.info('Adding parameter ' + parameterName + ' to parameter store')
        ssmClient = boto3.client('ssm')
        ssmClient.put_parameter(
            Name=parameterName,
            Description=parameterDescription,
            Value=value,
            Type="SecureString"
        )
    except Exception as e:
        logger.error("Unable to create parameter '{0}' in Parameter Store. Exception: {1}".format(parameterName, e))
        return False
    return True


def delete_password_from_param_store(aob_mode):
    logger.trace(aob_mode, caller_name='delete_password_from_param_store')
    try:
        logger.info('Deleting parameters from parameter store')
        ssmClient = boto3.client('ssm')
        ssmClient.delete_parameter(
            Name='AOB_Vault_Pass'
        )
        print("Parameter 'AOB_Vault_Pass' deleted successfully from Parameter Store")
        ssmClient.delete_parameter(
            Name='AOB_mode'
        )
        print("Parameter 'AOB_mode' deleted successfully from Parameter Store")
        if aob_mode == 'Production':
            ssmClient.delete_parameter(
                Name='AOB_PVWA_Verification_Key'
            )
            print("Parameter 'AOB_PVWA_Verification_Key' deleted successfully from Parameter Store")
        return True
    except Exception as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return True
        else:
            logger.error("Failed to delete parameter 'Vault_Pass' from Parameter Store. Error code: {0}".format(e.response["Error"]["Code"]))
            return False


def delete_sessions_table():
    logger.trace(caller_name='delete_sessions_table')
    try:
        logger.info('Deleting Dynamo session table')
        dynamodb = boto3.resource('dynamodb')
        sessionsTable = dynamodb.Table('Sessions')
        sessionsTable.delete()
        return
    except Exception:
        logger.error("Failed to delete 'Sessions' table from DynamoDB")
        return

def get_aob_mode():
    ssm = boto3.client('ssm')
    ssm_parameter = ssm.get_parameter(
        Name='AOB_mode'
    )
    aob_mode = ssm_parameter['Parameter']['Value']
    return aob_mode