import pvwa_api_calls
import aws_services
import kp_processing
import boto3

UNIX_PLATFORM = "UnixSSHKeys"
WINDOWS_PLATFORM = "WinServerLocal"
ADMINISTRATOR = "Administrator"


def delete_instance(instanceId, session, storeParametersClass, instanceData, instanceDetails):
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
        print("Instance AccountId not found on safe")
        return

    pvwa_api_calls.delete_account_from_vault(session, instanceAccountId, instanceId, storeParametersClass.pvwaURL)

    aws_services.remove_instance_from_dynamo_table(instanceId)
    return


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
    keyPairValueOnSafe = "AWS.{0}.{1}.{2}".format(instanceDetails["aws_account_id"], awsRegionName,
                                                  instanceDetails["key_name"])
    keyPairAccountId = pvwa_api_calls.retrieve_accountId_from_account_name(session, keyPairValueOnSafe,
                                                                           storeParametersClass.keyPairSafeName,
                                                                           instanceId,
                                                                           storeParametersClass.pvwaURL)
    if not keyPairAccountId:
        print("Key Pair '{0}' does not exist in safe '{1}'".format(keyPairValueOnSafe,
                                                                   storeParametersClass.keyPairSafeName))
        return
    instanceAccountPassword = pvwa_api_calls.get_account_value(session, keyPairAccountId, instanceId,
                                                               storeParametersClass.pvwaURL)
    if instanceAccountPassword is False:
        return

    if instanceDetails['platform'] == "windows":  # Windows machine return 'windows' all other return 'None'
        kp_processing.save_key_pair(instanceAccountPassword)
        instancePasswordData = get_instance_password_data(instanceId)
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

    searchAccountPattern = "{0},{1}".format(instanceDetails["address"], instanceUsername)
    existingInstanceAccountId = pvwa_api_calls.retrieve_accountId_from_account_name(session, searchAccountPattern,
                                                                                    safeName,
                                                                                    instanceId,
                                                                                    storeParametersClass.pvwaURL)
    if existingInstanceAccountId:  # account already exist and managed on vault, no need to create it again
        print("Account already exists in vault")
        aws_services.put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded, "None", logName)
        return
    else:
        accountCreated, errorMessage = pvwa_api_calls.create_account_on_vault(session, AWSAccountName, instanceKey,
                                                                              storeParametersClass,
                                                                              platform, instanceDetails['address'],
                                                                              instanceId, instanceUsername, safeName)

        if accountCreated:
            # if account created, rotate the key immediately
            instanceAccountId = pvwa_api_calls.retrieve_accountId_from_account_name(session, searchAccountPattern,
                                                                                    safeName,
                                                                                    instanceId,
                                                                                    storeParametersClass.pvwaURL)

            pvwa_api_calls.rotate_credentials_immediately(session, storeParametersClass.pvwaURL, instanceAccountId,
                                                          instanceId)
            aws_services.put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded, "None",
                                         logName)
        else:  # on board failed, add the error to the table
            aws_services.put_instance_to_dynamo_table(instanceId, instanceDetails['address'], OnBoardStatus.OnBoarded_Failed,
                                         errorMessage, logName)


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



class OnBoardStatus:
    OnBoarded = "on boarded"
    OnBoarded_Failed = "on board failed"
    Delete_Failed = "delete failed"