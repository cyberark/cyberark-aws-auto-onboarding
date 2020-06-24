import requests
from pvwa_integration import PvwaIntegration
from log_mechanism import LogMechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
DEFAULT_HEADER = {"content-type": "application/json"}
pvwa_integration_class = PvwaIntegration()
logger = LogMechanism()


def create_account_on_vault(session, account_name, account_password, store_parameters_class, platform_id, address,
                            instance_id, username, safe_name):
    logger.trace(session, account_name, account_password, store_parameters_class, platform_id, address,
                 instance_id, username, safe_name, caller_name='create_account_on_vault')
    logger.info('Creating account in vault for ' + instance_id)
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    url = "{0}/WebServices/PIMServices.svc/Account".format(store_parameters_class.pvwa_url)
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
    }}""".format(safe_name, platform_id, account_name, account_password, username, address)
    rest_response = pvwa_integration_class.call_rest_api_post(url, data, header)
    if rest_response.status_code == requests.codes.created:
        logger.info("Account for {0} was successfully created".format(instance_id))
        return True, ""
    else:
        logger.error('Failed to create the account for {0} from the vault. status code:{1}'.format(instance_id,
                                                                                            rest_response.status_code))
        return False, "Error Creating Account, Status Code:{0}".format(rest_response.status_code)


def rotate_credentials_immediately(session, pvwa_url, account_id, instance_id):
    logger.trace(session, pvwa_url, account_id, instance_id, caller_name='rotate_credentials_immediately')
    logger.info('Rotating ' + instance_id + ' credentials')
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    url = "{0}/API/Accounts/{1}/Change".format(pvwa_url, account_id)
    data = ""
    rest_response = pvwa_integration_class.call_rest_api_post(url, data, header)
    if rest_response.status_code == requests.codes.ok:
        logger.info("Call for immediate key change for {0} performed successfully".format(instance_id))
        return True
    else:
        logger.error('Failed to call key change for {0}. an error occurred'.format(instance_id))
        return False


def get_account_value(session, account, instance_id, rest_url):
    logger.trace(session, account, instance_id, rest_url, caller_name='get_account_value')
    logger.info('Getting ' + instance_id + ' account from vault')
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    pvwa_url = "{0}/api/Accounts/{1}/Password/Retrieve".format(rest_url, account)
    rest_logon_data = """{ "reason":"AWS Auto On-Boarding Solution" }"""
    rest_response = pvwa_integration_class.call_rest_api_post(pvwa_url, rest_logon_data, header)
    if rest_response.status_code == requests.codes.ok:
        return rest_response.text
    elif rest_response.status_code == requests.codes.not_found:
        logger.info("Account {0} for instance {1}, not found on vault".format(account, instance_id))
        return False
    else:
        logger.error("Unexpected result from rest service - get account value, status code: {0}".format(
            rest_response.status_code))
        return False


def delete_account_from_vault(session, account_id, instance_id, pvwa_url):
    logger.trace(session, account_id, instance_id, pvwa_url, caller_name='delete_account_from_vault')
    logger.info('Deleting ' + instance_id + ' from vault')
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    rest_url = "{0}/WebServices/PIMServices.svc/Accounts/{1}".format(pvwa_url, account_id)
    rest_response = pvwa_integration_class.call_rest_api_delete(rest_url, header)

    if rest_response.status_code != requests.codes.ok:
        if rest_response.status_code != requests.codes.not_found:
            logger.error("Failed to delete the account for {0} from the vault. The account does not exists".format(
                instance_id))
            raise Exception("Failed to delete the account for {0} from the vault. The account does not exists".format(instance_id))

        else:
            logger.error("Failed to delete the account for {0} from the vault. an error occurred".format(instance_id))
            raise Exception("Unknown status code received {0}".format(rest_response.status_code))

    logger.info("The account for {0} was successfully deleted".format(instance_id))
    return True


def check_if_kp_exists(session, account_name, safe_name, instance_id, rest_url):
    logger.trace(session, account_name, safe_name, instance_id, rest_url, caller_name='check_if_kp_exists')
    logger.info('Checking if key pair is onboarded')
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    # 2 options of search - if safe name not empty, add it to query, if not - search without it

    if safe_name:  # has value
        pvwa_url = "{0}/api/accounts?search={1}&filter=safe_name eq {2}".format(rest_url, account_name, safe_name)
    else:  # has no value
        pvwa_url = "{0}/api/accounts?search={1}".format(rest_url, account_name)
    try:
        rest_response = pvwa_integration_class.call_rest_api_get(pvwa_url, header)
        if not rest_response:
            raise Exception("Unknown Error when calling rest service - retrieve account_id")
    except Exception as e:
        logger.error('An error occurred:\n' + str(e))
        raise Exception(e)
    if rest_response.status_code == requests.codes.ok:
        # if response received, check account is not empty {"Count": 0,"accounts": []}
        if 'value' in rest_response.json() and rest_response.json()["value"]:
            parsed_json_response = rest_response.json()['value']
            return parsed_json_response[0]['id']
        else:
            return False
    else:
        logger.error("Status code {0}, received from REST service".format(rest_response.status_code))
        raise Exception("Status code {0}, received from REST service".format(rest_response.status_code))


def retrieve_account_id_from_account_name(session, account_name, safe_name, instance_id, rest_url):
    logger.trace(session, account_name, safe_name, instance_id, rest_url, caller_name='retrieve_account_id_from_account_name')
    logger.info('Retrieving account_id from account_name')
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    # 2 options of search - if safe name not empty, add it to query, if not - search without it

    if safe_name:  # has value
        pvwa_url = "{0}/api/accounts?search={1}&filter=safe_name eq {2}".format(rest_url, account_name, safe_name)
    else:  # has no value
        pvwa_url = "{0}/api/accounts?search={1}".format(rest_url, account_name)
    try:
        rest_response = pvwa_integration_class.call_rest_api_get(pvwa_url, header)
        if not rest_response:
            raise Exception("Unknown Error when calling rest service - retrieve account_id")
    except Exception as e:
        logger.error('An error occurred:\n' + str(e))
        raise Exception(e)
    if rest_response.status_code == requests.codes.ok:
        # if response received, check account is not empty {"Count": 0,"accounts": []}
        if 'value' in rest_response.json() and rest_response.json()["value"]:
            parsed_json_response = rest_response.json()['value']
            return filter_get_accounts_result(parsed_json_response, instance_id)
        else:
            logger.info('No match for account: ' + account_name)
            return False
    else:
        logger.error("Status code {0}, received from REST service".format(rest_response.status_code))
        raise Exception("Status code {0}, received from REST service".format(rest_response.status_code))


def filter_get_accounts_result(parsed_json_response, instance_id):
    logger.trace(parsed_json_response, instance_id, caller_name='filter_get_accounts_result')
    for element in parsed_json_response:
        if instance_id in element['name']:
            return element['id']
    return False
