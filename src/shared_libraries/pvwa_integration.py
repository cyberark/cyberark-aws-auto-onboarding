import requests
import aws_services

DEFAULT_HEADER = {"content-type": "application/json"}
# RestApiCalls:
def check_certificate():
    try:
        parameters = aws_services.get_params_from_param_store()
        if mode == 'Prod':
            certificate = "/tmp/server.crt"
        else:
            certificate = False
    except Exception as e:
        print("Error on retrieving AOB_mode parameter :{0}".format(e))
        raise Exception("Error occurred while retrieving AOB_mode parameter")
    return certificate

def call_rest_api_get(url, header):
    try:
        certificate = check_certificate()
        restResponse = requests.get(url, timeout=30, verify=certificate, headers=header)
    except Exception as e:
        print("Error occurred on calling PVWA REST service")
        return None
    return restResponse


def call_rest_api_delete(url, header):
    try:
        certificate = check_certificate()
        response = requests.delete(url, timeout=30, verify=certificate, headers=header)
    except Exception as e:
        print(e)
        return None
    return response


def call_rest_api_post(url, request, header):
    try:
        certificate = check_certificate()
        restResponse = requests.post(url, data=request, timeout=30, verify=certificate, headers=header, stream=True)
    except Exception:
        print("Error occurred during POST request to PVWA")
        return None
    return restResponse


# PvwaIntegration:
# performs logon to PVWA and return the session token
def logon_pvwa(username, password, pvwaUrl, connectionSessionId):
    print('Start Logon to PVWA REST API')
    logonUrl = '{0}/WebServices/auth/Cyberark/CyberArkAuthenticationService.svc/Logon'.format(pvwaUrl)
    restLogonData = """{{
        "username": "{0}",
        "password": "{1}",
        "connectionNumber": "{2}"
        }}""".format(username, password, connectionSessionId)
    try:
        restResponse = call_rest_api_post(logonUrl, restLogonData, DEFAULT_HEADER)
    except Exception:
        raise Exception("Error occurred on Logon to PVWA")

    if not restResponse:
        print("Connection to PVWA reached timeout")
        raise Exception("Connection to PVWA reached timeout")
    if restResponse.status_code == requests.codes.ok:
        jsonParsedResponse = restResponse.json()
        print("User authenticated")
        return jsonParsedResponse['CyberArkLogonResult']
    else:
        print("Authentication failed to REST API")
        raise Exception("Authentication failed to REST API")


def logoff_pvwa(pvwaUrl, connectionSessionToken):
    print('Start Logoff to PVWA REST API')
    header = DEFAULT_HEADER
    header.update({"Authorization": connectionSessionToken})
    logoffUrl = '{0}/WebServices/auth/Cyberark/CyberArkAuthenticationService.svc/Logoff'.format(pvwaUrl)
    restLogoffData = ""
    try:
        restResponse = call_rest_api_post(logoffUrl, restLogoffData, DEFAULT_HEADER)
    except Exception:
        # if couldn't logoff, nothing to do, return
        return

    if(restResponse.status_code == requests.codes.ok):
        jsonParsedResponse = restResponse.json()
        print("session logged off successfully")
        return True
    else:
        print("Logoff failed")
        return False
