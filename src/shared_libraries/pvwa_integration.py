import requests
import aws_services
from log_mechanisem import log_mechanisem

DEFAULT_HEADER = {"content-type": "application/json"}
# RestApiCalls:
class pvwa_integration:
    def __init__(self, is_safe_handler=False,safe_handler_environment=None):
        self.is_safe_handler = is_safe_handler
        self.safe_handler_environment = safe_handler_environment
        self.logger = log_mechanisem()
        try:
            self.logger.info_log_entry('Getting parameters from parameter store')
            parameters = aws_services.get_params_from_param_store()
            if parameters.AOB_mode == 'Production':
                self.logger.info_log_entry(parameters.AOB_mode + ' Environment Detected')
                self.certificate = "/tmp/server.crt"
            else:
                self.certificate = False
                if parameters.debugMode == 'True':
                    self.debugMode = 'True'
                    self.logger.info_log_entry(parameters.AOB_mode + ' Environment Detected')
        except Exception as e:
            self.logger.error_log_entry('Failed to retrieve AOB_mode parameter:\n' + e)
            raise Exception("Error occurred while retrieving AOB_mode parameter")
    
    def call_rest_api_get(self, url, header):
        self.url = url
        self.header = header
        try:
            self.logger.info_log_entry('Invoking get request \nurl:\n' + url + ' \nheader:\n' + header)
            restResponse = requests.get(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            self.logger.error_log_entry("An error occurred on calling PVWA REST service:\n" + e)
            return None
        return restResponse
    
    
    def call_rest_api_delete(self, url, header):
        self.url = url
        self.header = header
        try:
            self.logger.info_log_entry('Invoking delete request \nurl:\n' + url + ' \nheader:\n' + header)
            response = requests.delete(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            self.logger.error_log_entry('Failed to Invoke delete request : \n' + e)
            return None
        return response
    
    
    def call_rest_api_post(self, url, request, header):
        self.url = url
        self.request = request
        self.header = header
        try:
            self.logger.info_log_entry('Invoking post request \nurl:\n' + url + ' \nrequest:\n' + request + ' \nheader:\n' + header)
            restResponse = requests.post(self.url, data=self.request, timeout=30, verify=self.certificate, headers=self.header, stream=True)
        except Exception as e:
            self.logger.error_log_entry("Error occurred during POST request to PVWA:\n" + e)
            return None
        return restResponse
    
    
    # PvwaIntegration:
    # performs logon to PVWA and return the session token
    def logon_pvwa(self, username, password, pvwaUrl, connectionSessionId):
        self.username = username
        self.password = password
        self.pvwaUrl = pvwaUrl
        self.connectionSessionId = connectionSessionId
        self.logger.info_log_entry('Logging on to PVWA')
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
            self.logger.error_log_entry("Connection to PVWA reached timeout")
            raise Exception("Connection to PVWA reached timeout")
        if restResponse.status_code == requests.codes.ok:
            jsonParsedResponse = restResponse.json()
            self.logger.info_log_entry("User authenticated")
            return jsonParsedResponse['CyberArkLogonResult']
        else:
            self.logger.error_log_entry("Authentication failed with response:\n" + restResponse)
            raise Exception("PVWA authentication failed")
    
    
    def logoff_pvwa(self, pvwaUrl, connectionSessionToken):
        self.pvwaUrl = pvwaUrl
        self.connectionSessionToken = connectionSessionToken
        self.logger.info_log_entry('Logging off from PVWA')
        header = DEFAULT_HEADER
        header.update({"Authorization": self.connectionSessionToken})
        logoffUrl = '{0}/WebServices/auth/Cyberark/CyberArkAuthenticationService.svc/Logoff'.format(self.pvwaUrl)
        restLogoffData = ""
        try:
            restResponse = self.call_rest_api_post(logoffUrl, restLogoffData, header)
        except Exception:
            return
    
        if(restResponse.status_code == requests.codes.ok):
            jsonParsedResponse = restResponse.json()
            self.logger.info_log_entry("session logged off successfully")
            return True
        else:
            self.logger.error_log_entry("Logoff failed")
            return False
