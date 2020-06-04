import requests
import aws_services

DEFAULT_HEADER = {"content-type": "application/json"}
# RestApiCalls:
class pvwa_integration:
    def __init__(self, is_safe_handler=False,safe_handler_environment=None):
        self.is_safe_handler = is_safe_handler
        self.safe_handler_environment = safe_handler_environment
        try:
            if not self.is_safe_handler:
                parameters = aws_services.get_params_from_param_store()
                if parameters.AOB_mode == 'Production':
                    print ("Production Environment Detected")
                    self.certificate = "/tmp/server.crt"
                else:
                    self.certificate = False
                    print ("POC Environment Detected")
            else:
                if self.safe_handler_environment == "Production":
                    print ("Production Environment Detected")
                    self.certificate = "/tmp/server.crt"
                else:
                    print ("POC Environment Detected")
                    self.certificate = False
        except Exception as e:
            print("Error on retrieving AOB_mode parameter :{0}".format(e))
            raise Exception("Error occurred while retrieving AOB_mode parameter")
    
    def call_rest_api_get(self, url, header):
        self.url = url
        self.header = header
        try:
            restResponse = requests.get(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            print("Error occurred on calling PVWA REST service")
            return None
        return restResponse
    
    
    def call_rest_api_delete(self, url, header):
        self.url = url
        self.header = header
        try:
            response = requests.delete(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            print(e)
            return None
        return response
    
    
    def call_rest_api_post(self, url, request, header):
        self.url = url
        self.request = request
        self.header = header
        try:
            restResponse = requests.post(self.url, data=self.request, timeout=30, verify=self.certificate, headers=self.header, stream=True)
        except Exception as e:
            print("Error occurred during POST request to PVWA" + e)
            return None
        return restResponse
    
    
    # PvwaIntegration:
    # performs logon to PVWA and return the session token
    def logon_pvwa(self, username, password, pvwaUrl, connectionSessionId):
        self.username = username
        self.password = password
        self.pvwaUrl = pvwaUrl
        self.connectionSessionId = connectionSessionId
        print('Start Logon to PVWA REST API')
        logonUrl = '{0}/WebServices/auth/Cyberark/CyberArkAuthenticationService.svc/Logon'.format(self.pvwaUrl)
        restLogonData = """{{
            "username": "{0}",
            "password": "{1}",
            "connectionNumber": "{2}"
            }}""".format(self.username, self.password, self.connectionSessionId)
        try:
            restResponse = self.call_rest_api_post(logonUrl, restLogonData, DEFAULT_HEADER)
        except Exception as e:
            raise Exception("Error occurred on Logon to PVWA: " + e)
    
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
    
    
    def logoff_pvwa(self, pvwaUrl, connectionSessionToken):
        self.pvwaUrl = pvwaUrl
        self.connectionSessionToken = connectionSessionToken
        print('Start Logoff to PVWA REST API')
        header = DEFAULT_HEADER
        header.update({"Authorization": self.connectionSessionToken})
        logoffUrl = '{0}/WebServices/auth/Cyberark/CyberArkAuthenticationService.svc/Logoff'.format(self.pvwaUrl)
        restLogoffData = ""
        try:
            restResponse = self.call_rest_api_post(logoffUrl, restLogoffData, header)
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
