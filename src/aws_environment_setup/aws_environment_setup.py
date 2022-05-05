import uuid
import time
import requests
import urllib3
import boto3
import cfnresponse
from log_mechanism import LogMechanism
from pvwa_integration import PvwaIntegration
from dynamo_lock import LockerClient

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
DEFAULT_HEADER = {"content-type": "application/json"}
IS_SAFE_HANDLER = True
logger = LogMechanism()


def lambda_handler(event, context):
    logger.trace(event, context, caller_name='lambda_handler')
    try:
        physical_resource_id = str(uuid.uuid4())
        if 'PhysicalResourceId' in event:
            physical_resource_id = event['PhysicalResourceId']
        # only deleting the vault_pass from parameter store
        if event['RequestType'] == 'Delete':
            aob_mode = get_aob_mode()
            logger.info('Delete request received')
            delete_params = delete_password_from_param_store(aob_mode)
            if not delete_params:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to delete 'AOB_Vault_Pass' from parameter store, see detailed error in logs", {},
                                        physical_resource_id)
            delete_sessions_table()
            return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physical_resource_id)

        if event['RequestType'] == 'Create':
            logger.info('Create request received')
            request_username = event['ResourceProperties']['Username']
            request_pvwa_ip = event['ResourceProperties']['PVWAIP']
            request_password = event['ResourceProperties']['Password']
            request_key_pair_safe = event['ResourceProperties']['KeyPairSafe']
            request_key_pair_name = event['ResourceProperties']['KeyPairName']
            request_aws_region_name = event['ResourceProperties']['AWSRegionName']
            request_aws_account_id = event['ResourceProperties']['AWSAccountId']
            request_s3_bucket_name = event['ResourceProperties']['S3BucketName']
            request_verification_key_name = event['ResourceProperties']['PVWAVerificationKeyFileName']
            aob_mode = event['ResourceProperties']['Environment']


            logger.info('Adding AOB_Vault_Pass to parameter store', DEBUG_LEVEL_DEBUG)
            is_password_saved = add_param_to_parameter_store(request_password, "AOB_Vault_Pass", "Vault Password")
            if not is_password_saved:  # if password failed to be saved
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create Vault user's password in Parameter Store", {}, physical_resource_id)
            if request_s3_bucket_name == '' and request_verification_key_name != '':
                raise Exception('Verification Key cannot be empty if S3 Bucket is provided')
            elif request_s3_bucket_name != '' and request_verification_key_name == '':
                raise Exception('S3 Bucket cannot be empty if Verification Key is provided')
            else:
                logger.info('Adding AOB_mode to parameter store', DEBUG_LEVEL_DEBUG)
                is_aob_mode_saved = add_param_to_parameter_store(aob_mode, 'AOB_mode',
                                                                 'Dictates if the solution will work in POC(no SSL) or ' \
                                                                 'Production(with SSL) mode')
                if not is_aob_mode_saved:  # if password failed to be saved
                    return cfnresponse.send(event, context, cfnresponse.FAILED,
                                            "Failed to create AOB_mode parameter in Parameter Store", {}, physical_resource_id)
                if aob_mode == 'Production':
                    logger.info('Adding verification key to Parameter Store', DEBUG_LEVEL_DEBUG)
                    is_verification_key_saved = save_verification_key_to_param_store(request_s3_bucket_name,
                                                                                     request_verification_key_name)
                    if not is_verification_key_saved:  # if password failed to be saved
                        return cfnresponse.send(event, context, cfnresponse.FAILED,
                                                "Failed to create PVWA Verification Key in Parameter Store",
                                                {}, physical_resource_id)

            pvwa_integration_class = PvwaIntegration(IS_SAFE_HANDLER, aob_mode)
            pvwa_url = f"https://{request_pvwa_ip}/PasswordVault"
            pvwa_session_id = pvwa_integration_class.logon_pvwa(request_username, request_password, pvwa_url, "1")
            if not pvwa_session_id:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to connect to PVWA, see detailed error in logs", {}, physical_resource_id)

            if not create_session_table():
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        "Failed to create 'Sessions' table in DynamoDB, see detailed error in logs",
                                        {}, physical_resource_id)

            #  Creating KeyPair Safe
            is_safe_created = create_safe(pvwa_integration_class, request_key_pair_safe, "", request_pvwa_ip, pvwa_session_id)
            if not is_safe_created:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        f"Failed to create the Key Pairs safe: {request_key_pair_safe}, " \
                                        "see detailed error in logs",
                                        {}, physical_resource_id)

            #  key pair is optional parameter
            if not request_key_pair_name:
                logger.info("Key Pair name parameter is empty, the solution will not create a new Key Pair")
                return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physical_resource_id)
            aws_key_pair = create_new_key_pair_on_aws(request_key_pair_name)

            if aws_key_pair is False:
                # Account already exist, no need to create it, can't insert it to the vault
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        f"Failed to create Key Pair {request_key_pair_name} in AWS",
                                        {}, physical_resource_id)
            if aws_key_pair is True:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        f"Key Pair {request_key_pair_name} already exists in AWS",
                                        {}, physical_resource_id)
            # Create the key pair account on KeyPairs vault
            is_aws_account_created = create_key_pair_in_vault(pvwa_integration_class, pvwa_session_id, request_key_pair_name,
                                                              aws_key_pair, request_pvwa_ip, request_key_pair_safe,
                                                              request_aws_account_id, request_aws_region_name)
            if not is_aws_account_created:
                return cfnresponse.send(event, context, cfnresponse.FAILED,
                                        f"Failed to create Key Pair {request_key_pair_name} in safe " \
                                        f"{request_key_pair_safe}. see detailed error in logs", {}, physical_resource_id)

            return cfnresponse.send(event, context, cfnresponse.SUCCESS, None, {}, physical_resource_id)
    except Exception as e:
        logger.error(f"Exception occurred:{str(e)}:")
        return cfnresponse.send(event, context, cfnresponse.FAILED, f"Exception occurred: {str(e)}", {})

    finally:
        if 'pvwa_session_id' in locals():  # pvwa_session_id has been declared
            if pvwa_session_id:  # Logging off the session in case of successful logon
                pvwa_integration_class.logoff_pvwa(pvwa_url, pvwa_session_id)


# Creating a safe, if a failure occur, retry 3 time, wait 10 sec. between retries
def create_safe(pvwa_integration_class, safe_name, cpm_name, pvwa_ip, session_id, number_of_days_retention=7):
    logger.trace(pvwa_integration_class, safe_name, cpm_name, pvwa_ip, session_id, number_of_days_retention,
                 caller_name='create_safe')
    header = DEFAULT_HEADER
    header.update({"Authorization": session_id})
    create_safe_url = f"https://{pvwa_ip}/PasswordVault/API/Safes/"
    # Create new safe, default number of days retention is 7, unless specified otherwise
    data = f"""
            {{
                "SafeName":"{safe_name}",
                "Description":"",
                "OLACEnabled":false,
                "ManagingCPM":"{cpm_name}",
                "NumberOfDaysRetention":"{number_of_days_retention}"
            }}
            """
    logger.trace(data,caller_name='create_safe')
    for i in range(0, 3):
        create_safe_rest_response = pvwa_integration_class.call_rest_api_post(create_safe_url, data, header)

        if create_safe_rest_response.status_code == requests.codes.conflict:
            logger.info(f"The Safe {safe_name} already exists")
            return True
        elif create_safe_rest_response.status_code == requests.codes.bad_request:
            logger.error(f"Failed to create Safe {safe_name}, error 400: bad request")
            return False
        elif create_safe_rest_response.status_code == requests.codes.created:  # safe created
            logger.info(f"Safe {safe_name} was successfully created")
            return True
        else:  # Error creating safe, retry for 3 times, with 10 seconds between retries
            logger.error(f"Error creating Safe, status code:{create_safe_rest_response.status_code}, will retry in 10 seconds")
            if i == 3:
                logger.error(f"Failed to create safe after several retries, status code:{create_safe_rest_response.status_code}")
                return False
        time.sleep(10)


# Search if Key pair exist, if not - create it, return the pem key, False for error
def create_new_key_pair_on_aws(key_pair_name):
    logger.trace(key_pair_name, caller_name='create_new_key_pair_on_aws')
    ec2_client = boto3.client('ec2')

    # throws exception if key not found, if exception is InvalidKeyPair.Duplicate return True
    try:
        logger.info('Creating key pair')
        key_pair_response = ec2_client.create_key_pair(
            KeyName=key_pair_name,
            DryRun=False
        )
    except Exception as e:
        if e.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            logger.error(f"Key Pair {key_pair_name} already exists")
            return True
        logger.error(f'Creating new key pair failed. error code:\n {e.response["Error"]["Code"]}')
        return False

    return key_pair_response["KeyMaterial"]


def create_key_pair_in_vault(pvwa_integration_class, session, aws_key_name, private_key_value, pvwa_ip, safe_name,
                             aws_account_id, aws_region_name):
    logger.trace(pvwa_integration_class, session, aws_key_name, pvwa_ip, safe_name, aws_account_id,
                 aws_region_name, caller_name='create_key_pair_in_vault')
    header = DEFAULT_HEADER
    header.update({"Authorization": session})

    trimmed_pem_key = str(private_key_value).replace("\n", "\\n")
    trimmed_pem_key = trimmed_pem_key.replace("\r", "\\r")

    # AWS.<AWS Account>.<Region name>.<key pair name>
    unique_user_name = f"AWS.{aws_account_id}.{aws_region_name}.{aws_key_name}"
    logger.info(f"Creating account with username:{unique_user_name}")

    url = f"https://{pvwa_ip}/PasswordVault/api/Accounts"
    data = f"""
            {{
                  "safeName":"{safe_name}",
                  "platformID":"UnixSSHKeys",
                  "address":"1.1.1.1",
                  "secretType": "key",
                  "secret":"{trimmed_pem_key}",
                  "username":"{unique_user_name}",
                  "name":" "{unique_user_name}",
                  "secretManagement": {{
                    "automaticManagementEnabled": false,
                    "manualManagementReason": "AWS Key Pair"
                   }}
            }}
        """
    rest_response = pvwa_integration_class.call_rest_api_post(url, data, header)

    if rest_response.status_code == requests.codes.created:
        logger.info(f"Key Pair created successfully in safe '{safe_name}'")
        return True
    elif rest_response.status_code == requests.codes.conflict:
        logger.info(f"Key Pair created already exists in safe {safe_name}")
        return True
    logger.error(f"Failed to create Key Pair in safe {safe_name}, status code:{rest_response.status_code}")
    return False


def create_session_table():
    logger.trace(caller_name='create_session_table')
    try:
        logger.info('Locking Dynamo Table')
        sessions_table_lock = LockerClient('Sessions')
        sessions_table_lock.create_lock_table()
    except Exception as e:
        logger.error(f"Failed to create 'Sessions' table in DynamoDB. Exception: {str(e)}")
        return None

    logger.info("Table 'Sessions' created successfully")
    return True


def save_verification_key_to_param_store(s3_bucket_name, verification_key_name):
    logger.trace(s3_bucket_name, verification_key_name, caller_name='save_verification_key_to_param_store')
    try:
        logger.info('Downloading verification key from s3')
        s3_resource = boto3.resource('s3')
        s3_resource.Bucket(s3_bucket_name).download_file(verification_key_name, '/tmp/server.crt')
        add_param_to_parameter_store(open('/tmp/server.crt').read(), "AOB_PVWA_Verification_Key", "PVWA Verification Key")
    except Exception as e:
        logger.error(f"An error occurred while downloading Verification Key from S3 Bucket - {s3_bucket_name}. Exception: {e}")
        return False
    return True


def add_param_to_parameter_store(value, parameter_name, parameter_description):
    logger.trace(parameter_name, parameter_description, caller_name='add_param_to_parameter_store')
    try:
        logger.info(f'Adding parameter {parameter_name} to parameter store')
        ssm_client = boto3.client('ssm')
        ssm_client.put_parameter(
            Name=parameter_name,
            Description=parameter_description,
            Value=value,
            Type="SecureString"
        )
    except Exception as e:
        logger.error(f"Unable to create parameter {parameter_name} in Parameter Store. Exception: {e}")
        return False
    return True


def delete_password_from_param_store(aob_mode):
    logger.trace(aob_mode, caller_name='delete_password_from_param_store')
    try:
        logger.info('Deleting parameters from parameter store')
        ssm_client = boto3.client('ssm')
        ssm_client.delete_parameter(
            Name='AOB_Vault_Pass'
        )
        logger.info("Parameter 'AOB_Vault_Pass' deleted successfully from Parameter Store")
        ssm_client.delete_parameter(
            Name='AOB_mode'
        )
        logger.info("Parameter 'AOB_mode' deleted successfully from Parameter Store")
        if aob_mode == 'Production':
            ssm_client.delete_parameter(
                Name='AOB_PVWA_Verification_Key'
            )
            logger.info("Parameter 'AOB_PVWA_Verification_Key' deleted successfully from Parameter Store")
        return True
    except Exception as e:
        if e.response["Error"]["Code"] == "ParameterNotFound":
            return True
        logger.error(f'Failed to delete parameter "Vault_Pass" from Parameter Store. Error code: {e.response["Error"]["Code"]}')
        return False


def delete_sessions_table():
    logger.trace(caller_name='delete_sessions_table')
    try:
        logger.info('Deleting Dynamo session table')
        dynamodb = boto3.resource('dynamodb')
        sessions_table = dynamodb.Table('Sessions')
        sessions_table.delete()
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
