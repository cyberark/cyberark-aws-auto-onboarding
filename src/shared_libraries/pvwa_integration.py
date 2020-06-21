import requests
import aws_services
from log_mechanism import log_mechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
DEFAULT_HEADER = {"content-type": "application/json"}
# RestApiCalls:
class pvwa_integration:
    def __init__(self, is_safe_handler=False,safe_handler_environment=None):
        self.logger = log_mechanism()
        self.logger.trace(is_safe_handler, safe_handler_environment, caller_name='__init__')
        self.is_safe_handler = is_safe_handler
        self.safe_handler_environment = safe_handler_environment
        try:
            self.logger.info('Getting parameters from parameter store')
            if not is_safe_handler:
                parameters = aws_services.get_params_from_param_store()
                environment = parameters.AOB_mode
            else:
                environment = self.safe_handler_environment
            if environment == 'Production':
                self.logger.info(parameters.AOB_mode + ' Environment Detected',DEBUG_LEVEL_DEBUG)
                self.certificate = "/tmp/server.crt"
            else:
                self.certificate = False
                if parameters.debugLevel == 'True':
                    self.debugMode = 'True'
                    self.logger.info(f'{environment} Environment Detected',DEBUG_LEVEL_DEBUG)
        except Exception as e:
            self.logger.error('Failed to retrieve AOB_mode parameter:\n' + e)
            raise Exception("Error occurred while retrieving AOB_mode parameter")
    
    def call_rest_api_get(self, url, header):
        self.logger.trace(url, header, caller_name='call_rest_api_get')
        self.url = url
        self.header = header
        try:
            self.logger.info(f'Invoking get request url:{url} header: {header}')
            restResponse = requests.get(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            self.logger.error("An error occurred on calling PVWA REST service:\n" + e)
            return None
        return restResponse
    
    
    def call_rest_api_delete(self, url, header):
        self.logger.trace(url, header, caller_name='call_rest_api_delete')
        self.url = url
        self.header = header
        try:
            self.logger.info('Invoking delete request \nurl:\n' + url + ' \nheader:\n' + header,DEBUG_LEVEL_DEBUG)
            response = requests.delete(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            self.logger.error('Failed to Invoke delete request : \n' + e)
            return None
        return response
    
    
    def call_rest_api_post(self, url, request, header):
        self.logger.trace(url, request, header, caller_name='call_rest_api_post')
        self.url = url
        self.request = request
        self.header = header
        try:
            self.logger.info('Invoking post request \nurl:\n' + url + ' \nrequest:\n' + request + ' \nheader:\n' + header,DEBUG_LEVEL_DEBUG)
            restResponse = requests.post(self.url, data=self.request, timeout=30, verify=self.certificate, headers=self.header, stream=True)
        except Exception as e:
            self.logger.error("Error occurred during POST request to PVWA:\n" + e)
            return None
        return restResponse
    
    
    # PvwaIntegration:
    # performs logon to PVWA and return the session token
    def logon_pvwa(self, username, password, pvwaUrl, connectionSessionId):
        self.logger.trace(username, password, pvwaUrl, connectionSessionId, caller_name='logon_pvwa')
        self.username = username
        self.password = password
        self.pvwaUrl = pvwaUrl
        self.connectionSessionId = connectionSessionId
        self.logger.info('Logging to PVWA')
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
            self.logger.error("Connection to PVWA reached timeout")
            raise Exception("Connection to PVWA reached timeout")
        if restResponse.status_code == requests.codes.ok:
            jsonParsedResponse = restResponse.json()
            self.logger.info("User authenticated")
            return jsonParsedResponse['CyberArkLogonResult']
        else:
            self.logger.error("Authentication failed with response:\n" + restResponse)
            raise Exception("PVWA authentication failed")
    
    
    def logoff_pvwa(self, pvwaUrl, connectionSessionToken):
        self.logger.trace(pvwaUrl, connectionSessionToken, caller_name='logoff_pvwa')
        self.pvwaUrl = pvwaUrl
        self.connectionSessionToken = connectionSessionToken
        self.logger.info('Logging off from PVWA')
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
            self.logger.info("session logged off successfully")
            return True
        else:
            self.logger.error("Logoff failed")
            return False
