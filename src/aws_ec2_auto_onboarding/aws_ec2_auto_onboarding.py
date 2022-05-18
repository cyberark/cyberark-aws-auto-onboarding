import json
import urllib3
from pvwa_integration import PvwaIntegration
import aws_services
import instance_processing
import pvwa_api_calls
from log_mechanism import LogMechanism

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = LogMechanism()
pvwa_integration_class = PvwaIntegration()

def lambda_handler(event, context):
    logger.trace(context, caller_name='lambda_handler')
    logger.debug('Parsing event')
    try:
        message = event["Records"][0]["Sns"]["Message"]
        data = json.loads(message)
    except Exception as e:
        logger.error(f"Error on retrieving Message Data from Event Message. Error: {e}")

    try:
        instance_id = data["detail"]["instance-id"]
    except Exception as e:
        logger.error(f"Error on retrieving Instance Id from Event Message. Error: {e}")

    try:
        action_type = data["detail"]["state"]
    except Exception as e:
        logger.error(f"Error on retrieving Action Type from Event Message. Error: {e}")

    try:
        event_account_id = data["account"]
    except Exception as e:
        logger.error(f"Error on retrieving Event Account Id from Event Message. Error: {e}")

    try:
        event_region = data["region"]
        solution_account_id = context.invoked_function_arn.split(':')[4]
        log_name = context.log_stream_name if context.log_stream_name else "None"
    except Exception as e:
        logger.error(f"Error on retrieving Event Region from Event Message. Error: {e}")
    elasticity_function(instance_id, action_type, event_account_id, event_region, solution_account_id, log_name)


def elasticity_function(instance_id, action_type, event_account_id, event_region, solution_account_id, log_name):
    try:
        ec2_object = aws_services.get_account_details(solution_account_id, event_account_id, event_region)
        instance_details = aws_services.get_ec2_details(instance_id, ec2_object, event_account_id)
        instance_data = aws_services.get_instance_data_from_dynamo_table(instance_id)
        if action_type == 'terminated':
            if not instance_data:
                logger.debug(f"Item '{instance_id}' does not exist on DB")
                return None
            instance_status = instance_data["Status"]["S"]
            if instance_status == OnBoardStatus.on_boarded_failed:
                logger.error(f"Item '{instance_id}' is in status OnBoard failed, removing from DynamoDB table")
                aws_services.remove_instance_from_dynamo_table(instance_id)
                return None
        elif action_type == 'running':
            if not instance_details["address"]:  # In case querying AWS return empty address
                logger.error("Retrieving Instance Address from AWS failed.")
                return None
            if instance_data:
                instance_status = instance_data["Status"]["S"]
                if instance_status == OnBoardStatus.on_boarded:
                    logger.info(f"Item '{instance_id}' already exists in the DB, no need to add it to Vault")
                    return None
                elif instance_status == OnBoardStatus.on_boarded_failed:
                    logger.error(f"Item '{instance_id}' exists with status 'OnBoard failed', adding to Vault")
                else:
                    logger.debug(f"Item '{instance_id}' does not exist on DB, adding to Vault")
        else:
            logger.debug(f'Unknown instance state of {action_type}')
            return

        store_parameters_class = aws_services.get_params_from_param_store()
        if not store_parameters_class:
            return
        if store_parameters_class.aob_mode == 'Production':
            # Save PVWA Verification key in /tmp folder
            logger.debug('Saving verification key')
            crt = open("/tmp/server.crt", "w+")
            crt.write(store_parameters_class.pvwa_verification_key)
            crt.close()
        session_token = pvwa_integration_class.logon_pvwa(store_parameters_class.vault_username,
                                                          store_parameters_class.vault_password,
                                                          store_parameters_class.pvwa_url)
        if not session_token:
            return
        disconnect = False
        if action_type == 'terminated':
            logger.info(f"Detected termination of instance '{instance_id}'")
            removed = instance_processing.delete_instance(instance_id, session_token, store_parameters_class, instance_data,
                                                instance_details)
            if removed:                                               
                logger.info(f"The account for instance'{instance_id}' was successfully deleted or marked for deletion")
            else:
                logger.info(f"Instance '{instance_id}' not found. No action taken.")    
        elif action_type == 'running':
            # get key pair
            logger.debug('Retrieving account id where the key-pair is stored')
            # Retrieving the account id of the account where the instance keyPair is stored
            # AWS.<AWS Account>.<Event Region name>.<key pair name>
            key_pair_value_on_safe = f'AWS.{instance_details["aws_account_id"]}.{event_region}.{instance_details["key_name"]}'
            key_pair_account_id = pvwa_api_calls.check_if_kp_exists(session_token, key_pair_value_on_safe,
                                                                    store_parameters_class.key_pair_safe_name,
                                                                    instance_id,
                                                                    store_parameters_class.pvwa_url)
            if not key_pair_account_id:
                logger.error(f"Key Pair {key_pair_value_on_safe} does not exist in Safe " \
                             f"{store_parameters_class.key_pair_safe_name}")
                return
            instance_account_password = pvwa_api_calls.get_account_value(session_token, key_pair_account_id, instance_id,
                                                                         store_parameters_class.pvwa_url)
            if instance_account_password is False:
                return
            pvwa_integration_class.logoff_pvwa(store_parameters_class.pvwa_url, session_token)
            disconnect = True
            
            logger.info(f"Adding instance '{instance_id}' to the database and vault")
            instance_processing.create_instance(instance_id, instance_details, store_parameters_class, log_name,
                                                solution_account_id, event_region, event_account_id, instance_account_password)
            logger.info(f"Successfully added instance '{instance_id}' to the database and vault")
        else:
            logger.error('Unknown instance state')
            return

        if not disconnect:
            pvwa_integration_class.logoff_pvwa(store_parameters_class.pvwa_url, session_token)

    except UnboundLocalError:
        logger.error(f"Not all tags are properly set on '{instance_id}' for auto on boarding. No action taken.")

    except Exception as e:
        logger.error(f"Unknown error occurred: {e}")
        if action_type == 'terminated':
            # put_instance_to_dynamo_table(instance_id, instance_details["address"]\
            # , OnBoardStatus.delete_failed, str(e), log_name)
            aws_services.update_instances_table_status(instance_id, OnBoardStatus.delete_failed, str(e))
        elif action_type == 'running':
            aws_services.put_instance_to_dynamo_table(instance_id, instance_details["address"], OnBoardStatus.on_boarded_failed,
                                                      str(e), log_name)
# TODO: Retry mechanism?
        return


class OnBoardStatus:
    on_boarded = "on boarded"
    on_boarded_failed = "on board failed"
    delete_failed = "delete failed"
