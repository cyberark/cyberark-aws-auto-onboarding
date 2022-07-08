import boto3
import pvwa_api_calls
import aws_services
import kp_processing
from pvwa_integration import PvwaIntegration
from log_mechanism import LogMechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
pvwa_integration_class = PvwaIntegration()
logger = LogMechanism()


def delete_instance(instance_id, session, store_parameters_class, instance_data, instance_details):
    logger.trace(instance_id, session, store_parameters_class, instance_data, instance_details, caller_name='delete_instance')
    logger.debug(f"Removing '{instance_id}' from AOB")
    instance_ip_address = instance_data["Address"]["S"]
    if instance_details['platform'] == "windows":
        safe_name = instance_details['AOBSafe']
        instance_username = instance_details['AOBUsername']
    else:
        safe_name = instance_details['AOBSafe']
        instance_username = instance_details['AOBUsername']
    search_pattern = f"{instance_ip_address} {instance_username}"

    instance_account_id = pvwa_api_calls.retrieve_account_id_from_account_name(session, search_pattern,
                                                                               safe_name, instance_id,
                                                                               store_parameters_class.pvwa_url)
    if not instance_account_id:
        logger.debug(f"'{instance_id}' does not exist in safe")
        return False
    pvwa_api_calls.delete_account_from_vault(session, instance_account_id, instance_id, store_parameters_class.pvwa_url)
    logger.debug('Removing instance from DynamoDB', DEBUG_LEVEL_DEBUG)
    aws_services.remove_instance_from_dynamo_table(instance_id)
    return True


def get_instance_password_data(instance_id, solution_account_id, event_region, event_account_id):
    logger.trace(instance_id, solution_account_id, event_region, event_account_id, caller_name='get_instance_password_data')
    logger.debug(f"Getting '{instance_id}' password")
    if event_account_id == solution_account_id:
        try:
            ec2_resource = boto3.client('ec2', event_region)
        except Exception as e:
            logger.error(f'Error on creating boto3 session: {str(e)}')
    else:
        try:
            logger.debug('Assuming role')
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
        logger.info(f"Waiting for instance '{instance_id}' password to become available")
        waiter = ec2_resource.get_waiter('password_data_available')
        waiter.wait(InstanceId=instance_id)
        logger.info(f"Password for instance ''{instance_id}'' is now available")
        instance_password_data = ec2_resource.get_password_data(InstanceId=instance_id)
        return instance_password_data['PasswordData']
    except Exception as e:
        logger.error(f'Error on waiting for instance password: {str(e)}')


def create_instance(instance_id, instance_details, store_parameters_class, log_name, solution_account_id, event_region,
                    event_account_id, instance_account_password):
    logger.trace(instance_id, instance_details, store_parameters_class, log_name, solution_account_id, event_region,
                 event_account_id, caller_name='create_instance')

    if instance_details['platform'] == "windows":  # Windows machine return 'windows' all other return 'None'
        logger.debug('Windows platform detected')
        kp_processing.save_key_pair(instance_account_password)
        instance_password_data = get_instance_password_data(instance_id, solution_account_id, event_region, event_account_id)
        decrypted_password = kp_processing.decrypt_password(instance_password_data)
        aws_account_name = f'AWS.{instance_id}.Windows'
        instance_key = decrypted_password
        secret_type = "password"
        platform = instance_details['AOBPlatform']
        safe_name = instance_details['AOBSafe']
        instance_username = instance_details['AOBUsername']

    else:
        logger.debug('Linux\\Unix platform detected')
        ppk_key = kp_processing.convert_pem_to_ppk(instance_account_password)
        if not ppk_key:
            raise Exception("Error on key conversion")
        # ppk_key contains \r\n on each row end, adding escape char '\'
        trimmed_ppk_key = str(ppk_key).replace("\n", "\\n")
        instance_key = trimmed_ppk_key.replace("\r", "\\r")
        secret_type = "key"
        aws_account_name = f'AWS.{instance_id}.Unix'
        platform = instance_details['AOBPlatform']
        safe_name = instance_details['AOBSafe']
        instance_username = instance_details['AOBUsername']


    # Check if account already exist - in case exist - just add it to DynamoDB
    session_token = pvwa_integration_class.logon_pvwa(store_parameters_class.vault_username,
                                                      store_parameters_class.vault_password,
                                                      store_parameters_class.pvwa_url)
    if not session_token:
        return False

    search_account_pattern = f"{instance_details['address']} {instance_username}"
    logger.debug("retrieve_account_id_from_account_name")
    existing_instance_account_id = pvwa_api_calls.retrieve_account_id_from_account_name(session_token, search_account_pattern,
                                                                                        safe_name,
                                                                                        instance_id,
                                                                                        store_parameters_class.pvwa_url)
    if existing_instance_account_id:  # account already exist and managed on vault, no need to create it again
        logger.debug("Account already exists in vault")
        aws_services.put_instance_to_dynamo_table(instance_id, instance_details['address'], OnBoardStatus.on_boarded, "None",
                                                  log_name)
        return False
    else:
        account_created, error_message = pvwa_api_calls.create_account_on_vault(session_token, aws_account_name, instance_key,
                                                                                secret_type, store_parameters_class,
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

    return True

class OnBoardStatus:
    on_boarded = "on boarded"
    on_boarded_failed = "on board failed"
    delete_failed = "delete failed"
