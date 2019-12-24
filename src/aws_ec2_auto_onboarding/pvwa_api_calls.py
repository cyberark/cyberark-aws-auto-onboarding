import requests
import pvwa_integration
DEFAULT_HEADER = {"content-type": "application/json"}


def create_account_on_vault(session, account_name, account_password, storeParametersClass, platform_id, address,
                            instanceId, username, safeName):
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
    }}""".format(safeName, platform_id, account_name, account_password, username, address)
    restResponse = pvwa_integration.call_rest_api_post(url, data, header)
    if restResponse.status_code == requests.codes.created:
        print("Account for {0} was successfully created".format(instanceId))
        return True, ""
    else:
        print('Failed to create the account for {0} from the vault. status code:{1}'.format(instanceId,
                                                                                            restResponse.status_code))
        return False, "Error Creating Account, Status Code:{0}".format(restResponse.status_code)


def rotate_credentials_immediately(session, pvwaUrl, accountId, instanceId):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    url = "{0}/API/Accounts/{1}/Change".format(pvwaUrl, accountId)
    data = ""
    restResponse = pvwa_integration.call_rest_api_post(url, data, header)
    if restResponse.status_code == requests.codes.ok:
        print("Call for immediate key change for {0} performed successfully".format(instanceId))
        return True
    else:
        print('Failed to call key change for {0}. an error occurred'.format(instanceId))
        return False


def get_account_value(session, account, instanceId, restURL):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    pvwaUrl = "{0}/api/Accounts/{1}/Password/Retrieve".format(restURL, account)
    restLogonData = """{ "reason":"AWS Auto On-Boarding Solution" }"""
    restResponse = pvwa_integration.call_rest_api_post(pvwaUrl, restLogonData, header)
    if restResponse.status_code == requests.codes.ok:
        return restResponse.text
    elif restResponse.status_code == requests.codes.not_found:
        print("Account {0} for instance {1}, not found on vault".format(account, instanceId))
        return False
    else:
        print("Unexpected result from rest service - get account value, status code: {0}".format(
            restResponse.status_code))
        return False


def delete_account_from_vault(session, accountId, instanceId, pvwaUrl):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})
    restUrl = "{0}/WebServices/PIMServices.svc/Accounts/{1}".format(pvwaUrl, accountId)
    restResponse = pvwa_integration.call_rest_api_delete(restUrl, header)

    if restResponse.status_code != requests.codes.ok:
        if restResponse.status_code != requests.codes.not_found:
            print("Failed to delete the account for {0} from the vault. The account does not exists".format(
                instanceId))
            raise Exception(
                "Failed to delete the account for {0} from the vault. The account does not exists".format(
                    instanceId))

        else:
            print("Failed to delete the account for {0} from the vault. an error occurred".format(instanceId))
            raise Exception("Unknown status code received {0}".format(restResponse.status_code))

    print("The account for {0} was successfully deleted".format(instanceId))
    return True


def retrieve_accountId_from_account_name(session, accountName, safeName, instanceId, restURL):
    header = DEFAULT_HEADER
    header.update({"Authorization": session})

    # 2 options of search - if safe name not empty, add it to query, if not - search without it
    if safeName:  # has value
        pvwaUrl = "{0}/api/accounts?search={1}&filter=safeName eq '{2}'".format(restURL, accountName, safeName)
    else:  # has no value
        pvwaUrl = "{0}/api/accounts?search={1}".format(restURL, accountName)

    restResponse = pvwa_integration.call_rest_api_get(pvwaUrl, header)
    if not restResponse:
        raise Exception("Unknown Error when calling rest service - retrieve accountId")

    if restResponse.status_code == requests.codes.ok:
        # if response received, check account is not empty {"Count": 0,"accounts": []}
        if 'value' in restResponse.json() and restResponse.json()["value"]:
            parsedJsonResponse = restResponse.json()['value']
            return parsedJsonResponse[0]['id']
        else:
            return False
    else:
        raise Exception("Status code {0}, received from REST service".format(restResponse.status_code))

