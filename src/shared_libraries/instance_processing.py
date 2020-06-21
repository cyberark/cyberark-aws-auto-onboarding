import pvwa_api_calls
import aws_services
import kp_processing
from pvwa_integration import pvwa_integration
import boto3
from log_mechanism import log_mechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
UNIX_PLATFORM = "UnixSSHKeys"
WINDOWS_PLATFORM = "WinServerLocal"
ADMINISTRATOR = "Administrator"
pvwa_integration_class = pvwa_integration()
logger = log_mechanism()

def delete_instance(instanceId, session, storeParametersClass, instanceData, instanceDetails):
    logger.trace(instanceId, session, storeParametersClass, instanceData, instanceDetails, caller_name='delete_instance')
    logger.info('Removing ' + instanceId + ' From AOB')
    instanceIpAddress = instanceData["Address"]["S"]
    if instanceDetails['platform'] == "windows":
        safeName = storeParametersClass.windowsSafeName
        instanceUsername = ADMINISTRATOR
    else:
        safeName = storeParametersClass.unixSafeName
        instanceUsername = get_OS_distribution_user(instanceDetails['image_description'])
    searchPattern = "{0},{1}".format(instanceIpAddress, instanceUsername)

    instanceAccountId = pvwa_api_calls.retrieve_accountId_from_account_name(session, searchPattern,
                                                                            safeName, instanceId,
                                                                            storeParametersClass.pvwaURL)
    if not instanceAccountId:
        logger.info(instanceId + " does not exist in safe")
        return

    pvwa_api_calls.delete_account_from_vault(session, instanceAccountId, instanceId, storeParametersClass.pvwaURL)

    aws_services.remove_instance_from_dynamo_table(instanceId)
    return


def get_instance_password_data(instanceId,solutionAccountId,eventRegion,eventAccountId):
    logger.trace(instanceId,solutionAccountId,eventRegion,eventAccountId, caller_name='get_instance_password_data')
    logger.info('Getting ' + instanceId + ' password')
    if eventAccountId == solutionAccountId:
        try:
            ec2Resource = boto3.client('ec2', eventRegion)
        except Exception as e:
            logger.error('Error on creating boto3 session: {0}'.format(e))
    else:
        try:
            logger.info('Assuming role')
            sts_connection = boto3.client('sts')
            acct_b = sts_connection.assume_role(
            	RoleArn="arn:aws:iam::{0}:role/CyberArk-AOB-AssumeRoleForElasticityLambda".format(eventAccountId),
            	RoleSessionName="cross_acct_lambda"
            )
            ACCESS_KEY = acct_b['Credentials']['AccessKeyId']
            SECRET_KEY = acct_b['Credentials']['SecretAccessKey']
            SESSION_TOKEN = acct_b['Credentials']['SessionToken']
            
            ec2Resource = boto3.client(
            	'ec2',
            	region_name=eventRegion,
            	aws_access_key_id=ACCESS_KEY,
            	aws_secret_access_key=SECRET_KEY,
            	aws_session_token=SESSION_TOKEN,
            )
        except Exception as e:
        	logger.error('Error on getting token from account: {0}'.format(eventAccountId))

    try:
    	# wait until password data available when Windows instance is up
    	logger.info("Waiting for instance - {0} to become available: ".format(instanceId))
    	waiter = ec2Resource.get_waiter('password_data_available')
    	waiter.wait(InstanceId=instanceId)
    	instancePasswordData = ec2Resource.get_password_data(InstanceId=instanceId)
    	return instancePasswordData['PasswordData']
    except Exception as e:
    	logger.error('Error on waiting for instance password: {0}'.format(e))


def create_instance(instanceId, instanceDetails, storeParametersClass, logName, solutionAccountId, eventRegion, eventAccountId, instanceAccountPassword):
    logger.trace(instanceId, instanceDetails, storeParametersClass, logName, solutionAccountId, eventRegion, eventAccountId, caller_name='create_instance')
    logger.info('Adding ' + instanceId + ' to AOB')
    if instanceDetails['platform'] == "windows":  # Windows machine return 'windows' all other return 'None'
        logger.info('Windows platform detected')
        kp_processing.save_key_pair(instanceAccountPassword)
        instancePasswordData = get_instance_password_data(instanceId, solutionAccountId, eventRegion, eventAccountId)
        # decryptedPassword = convert_pem_to_password(instanceAccountPassword, instancePasswordData)
        rc, decryptedPassword = kp_processing.run_command_on_container(
            ["echo", str.strip(instancePasswordData), "|", "base64", "--decode", "|", "openssl", "rsautl", "-decrypt",
             "-inkey", "/tmp/pemValue.pem"], True)
        AWSAccountName = 'AWS.{0}.Windows'.format(instanceId)
        instanceKey = decryptedPassword
        platform = WINDOWS_PLATFORM
        instanceUsername = ADMINISTRATOR
        safeName = storeParametersClass.windowsSafeName
    else:
        ppkKey = kp_processing.convert_pem_to_ppk(instanceAccountPassword)
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


    pvwaConnectionnumber, sessionGuid = aws_services.get_available_session_from_dynamo()
    if not pvwaConnectionnumber:
        return
    sessionToken = pvwa_integration_class.logon_pvwa(storeParametersClass.vaultUsername,
                                               storeParametersClass.vaultPassword,
                                               storeParametersClass.pvwaURL, pvwaConnectionnumber)

    if not sessionToken:
        return

    searchAccountPattern = "{0},{1}".format(instanceDetails["address"], instanceUsername)
    existingInstanceAccountId = pvwa_api_calls.retrieve_accountId_from_account_name(sessionToken, searchAccountPattern,
                                                                                    safeName,
                                                                                    instanceId,
                                                                                    storeParametersClass.pvwaURL)
    if existingInstanceAccountId:  # account already exist and managed on vault, no need to create it again
        logger.info("Account already exists in vault")
        aws_services.put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded, "None", logName)
        return
    else:
        accountCreated, errorMessage = pvwa_api_calls.create_account_on_vault(sessionToken, AWSAccountName, instanceKey,
                                                                              storeParametersClass,
                                                                              platform, instanceDetails['address'],
                                                                              instanceId, instanceUsername, safeName)

        if accountCreated:
            # if account created, rotate the key immediately
            instanceAccountId = pvwa_api_calls.retrieve_accountId_from_account_name(sessionToken, searchAccountPattern,
                                                                                    safeName,
                                                                                    instanceId,
                                                                                    storeParametersClass.pvwaURL)

            pvwa_api_calls.rotate_credentials_immediately(sessionToken, storeParametersClass.pvwaURL, instanceAccountId,
                                                          instanceId)
            aws_services.put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded, "None",
                                         logName)
        else:  # on board failed, add the error to the table
            aws_services.put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded_Failed,
                                         errorMessage, logName)
    pvwa_integration_class.logoff_pvwa(storeParametersClass.pvwaURL, sessionToken)
    aws_services.release_session_on_dynamo(pvwaConnectionnumber, sessionGuid)


def get_OS_distribution_user(imageDescription):
    logger.trace(imageDescription, caller_name='get_OS_distribution_user')
    if "centos" in (imageDescription.lower()):
        linuxUsername = "centos"
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



class OnBoardStatus:
    OnBoarded = "on boarded"
    OnBoarded_Failed = "on board failed"
    Delete_Failed = "delete failed"