import boto3
import pvwa_api_calls
import aws_services
import kp_processing
from pvwa_integration import PvwaIntegration
from log_mechanism import LogMechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
UNIX_PLATFORM = "UnixSSHKeys"
WINDOWS_PLATFORM = "WinServerLocal"
ADMINISTRATOR = "Administrator"
pvwa_integration_class = PvwaIntegration()
logger = LogMechanism()


def delete_instance(instance_id, session, store_parameters_class, instance_data, instance_details):
    logger.trace(instance_id, session, store_parameters_class, instance_data, instance_details, caller_name='delete_instance')
    logger.info(f'Removing {instance_id} From AOB')
    instance_ip_address = instance_data["Address"]["S"]
    if instance_details['platform'] == "windows":
        safe_name = store_parameters_class.windows_safe_name
        instance_username = ADMINISTRATOR
    else:
        safe_name = store_parameters_class.unix_safe_name
        instance_username = get_os_distribution_user(instance_details['image_description'])
    search_pattern = f"{instance_ip_address},{instance_username}"

    instance_account_id = pvwa_api_calls.retrieve_account_id_from_account_name(session, search_pattern,
                                                                               safe_name, instance_id,
                                                                               store_parameters_class.pvwa_url)
    if not instance_account_id:
        logger.info(f"{instance_id} does not exist in safe")
        return False
    pvwa_api_calls.delete_account_from_vault(session, instance_account_id, instance_id, store_parameters_class.pvwa_url)
    logger.info('Removing instance from DynamoDB', DEBUG_LEVEL_DEBUG)
    aws_services.remove_instance_from_dynamo_table(instance_id)
    return True


def get_instance_password_data(instance_id, solution_account_id, event_region, event_account_id):
    logger.trace(instance_id, solution_account_id, event_region, event_account_id, caller_name='get_instance_password_data')
    logger.info(f'Getting {instance_id} password')
    if event_account_id == solution_account_id:
        try:
            ec2_resource = boto3.client('ec2', event_region)
        except Exception as e:
            logger.error(f'Error on creating boto3 session: {str(e)}')
    else:
        try:
            logger.info('Assuming role')
            sts_connection = boto3.client('sts')
            acct_b = sts_connection.assume_role(RoleArn=f"arn:aws:iam::{event_account_id}" \
                                                ":role/CyberArk-AOB-AssumeRoleForElasticityLambda",
                                                RoleSessionName="cross_acct_lambda")
            access_key = acct_b['Credentials']['AccessKeyId']
            secret_key = acct_b['Credentials']['SecretAccessKey']
            session_token = acct_b['Credentials']['session_token']

            ec2_resource = boto3.client(
                'ec2',
                region_name=event_region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                )
        except Exception as e:
            logger.error(f'Error on getting token from account {event_account_id} : {str(e)}')

    try:
    	# wait until password data available when Windows instance is up
        logger.info(f"Waiting for instance - {instance_id} to become available: ")
        waiter = ec2_resource.get_waiter('password_data_available')
        waiter.wait(InstanceId=instance_id)
        instance_password_data = ec2_resource.get_password_data(InstanceId=instance_id)
        return instance_password_data['PasswordData']
    except Exception as e:
        logger.error(f'Error on waiting for instance password: {str(e)}')


def create_instance(instance_id, instance_details, store_parameters_class, log_name, solution_account_id, event_region,
                    event_account_id, instance_account_password):
    logger.trace(instance_id, instance_details, store_parameters_class, log_name, solution_account_id, event_region,
                 event_account_id, caller_name='create_instance')
    logger.info(f'Adding {instance_id} to AOB')
    if instance_details['platform'] == "windows":  # Windows machine return 'windows' all other return 'None'
        logger.info('Windows platform detected')
        kp_processing.save_key_pair(instance_account_password)
        instance_password_data = get_instance_password_data(instance_id, solution_account_id, event_region, event_account_id)
        # decrypted_password = convert_pem_to_password(instance_account_password, instance_password_data)
        command = ["echo", str.strip(instance_password_data), "|", "base64", "--decode", "|", "openssl", "rsautl", "-decrypt",
                   "-inkey", "/tmp/pemValue.pem"]
        return_code, decrypted_password = kp_processing.run_command_on_container(command, True)
        aws_account_name = f'AWS.{instance_id}.Windows'
        instance_key = decrypted_password
        platform = WINDOWS_PLATFORM
        instance_username = ADMINISTRATOR
        safe_name = store_parameters_class.windows_safe_name
    else:
        logger.info('Linux\\Unix platform detected')
        ppk_key = kp_processing.convert_pem_to_ppk(instance_account_password)
        if not ppk_key:
            raise Exception("Error on key conversion")
        # ppk_key contains \r\n on each row end, adding escape char '\'
        trimmed_ppk_key = str(ppk_key).replace("\n", "\\n")
        instance_key = trimmed_ppk_key.replace("\r", "\\r")
        aws_account_name = f'AWS.{instance_id}.Unix'
        platform = UNIX_PLATFORM
        safe_name = store_parameters_class.unix_safe_name
        instance_username = get_os_distribution_user(instance_details['image_description'])

    # Check if account already exist - in case exist - just add it to DynamoDB
    print('pvwa_connection_number')
    pvwa_connection_number, session_guid = aws_services.get_session_from_dynamo()
    if not pvwa_connection_number:
        return False
    session_token = pvwa_integration_class.logon_pvwa(store_parameters_class.vault_username,
                                                      store_parameters_class.vault_password,
                                                      store_parameters_class.pvwa_url, pvwa_connection_number)
    print('session_token')
    if not session_token:
        return False

    search_account_pattern = f"{instance_details['address']},{instance_username}"
    print('retrieve_account_id_from_account_name')
    existing_instance_account_id = pvwa_api_calls.retrieve_account_id_from_account_name(session_token, search_account_pattern,
                                                                                        safe_name,
                                                                                        instance_id,
                                                                                        store_parameters_class.pvwa_url)
    if existing_instance_account_id:  # account already exist and managed on vault, no need to create it again
        logger.info("Account already exists in vault")
        aws_services.put_instance_to_dynamo_table(instance_id, instance_details['address'], OnBoardStatus.on_boarded, "None",
                                                  log_name)
        return False
    else:
        account_created, error_message = pvwa_api_calls.create_account_on_vault(session_token, aws_account_name, instance_key,
                                                                                store_parameters_class,
                                                                                platform, instance_details['address'],
                                                                                instance_id, instance_username, safe_name)
        if account_created:
            # if account created, rotate the key immediately
            instance_account_id = pvwa_api_calls.retrieve_account_id_from_account_name(session_token, search_account_pattern,
                                                                                       safe_name,
                                                                                       instance_id,
                                                                                       store_parameters_class.pvwa_url)
            pvwa_api_calls.rotate_credentials_immediately(session_token, store_parameters_class.pvwa_url, instance_account_id,
                                                          instance_id)
            aws_services.put_instance_to_dynamo_table(instance_id, instance_details['address'], OnBoardStatus.on_boarded, "None",
                                                      log_name)
        else:  # on board failed, add the error to the table
            aws_services.put_instance_to_dynamo_table(instance_id, instance_details['address'], OnBoardStatus.on_boarded_failed,
                                                      error_message, log_name)
    pvwa_integration_class.logoff_pvwa(store_parameters_class.pvwa_url, session_token)
    aws_services.release_session_on_dynamo(pvwa_connection_number, session_guid)
    return True


def get_os_distribution_user(image_description):
    logger.trace(image_description, caller_name='get_os_distribution_user')
    if "centos" in image_description.lower():
        linux_username = "centos"
    elif "ubuntu" in image_description.lower():
        linux_username = "ubuntu"
    elif "debian" in image_description.lower():
        linux_username = "admin"
    elif "fedora" in image_description.lower():
        linux_username = "fedora"
    elif "opensuse" in image_description.lower():
        linux_username = "root"
    else:
        linux_username = "ec2-user"

    return linux_username


class OnBoardStatus:
    on_boarded = "on boarded"
    on_boarded_failed = "on board failed"
    delete_failed = "delete failed"
