import requests
import aws_services
from log_mechanism import LogMechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
DEFAULT_HEADER = {"content-type": "application/json"}
# RestApiCalls:


class PvwaIntegration:
    def __init__(self, is_safe_handler=False, safe_handler_environment=None):
        self.logger = LogMechanism()
        self.logger.trace(is_safe_handler, safe_handler_environment, caller_name='__init__')
        self.is_safe_handler = is_safe_handler
        self.safe_handler_environment = safe_handler_environment
        try:
            self.logger.info('Getting parameters from parameter store')
            if not is_safe_handler:
                parameters = aws_services.get_params_from_param_store()
                environment = parameters.aob_mode
            else:
                environment = self.safe_handler_environment
            if environment == 'Production':
                self.logger.info(f'{environment} Environment Detected', DEBUG_LEVEL_DEBUG)
                self.certificate = "/tmp/server.crt"
            else:
                self.certificate = False
                self.logger.info(f'{environment} Environment Detected', DEBUG_LEVEL_DEBUG)
        except Exception as e:
            self.logger.error(f'Failed to retrieve aob_mode parameter: {str(e)}')
            raise Exception("Error occurred while retrieving aob_mode parameter")


    def call_rest_api_get(self, url, header):
        self.logger.trace(url, header, caller_name='call_rest_api_get')
        self.url = url
        self.header = header
        try:
            self.logger.info(f'Invoking get request url:{url}, header: {header}', DEBUG_LEVEL_DEBUG)
            rest_response = requests.get(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            self.logger.error(f"An error occurred on calling PVWA REST service: {str(e)}")
            return None
        return rest_response


    def call_rest_api_delete(self, url, header):
        self.logger.trace(url, header, caller_name='call_rest_api_delete')
        self.url = url
        self.header = header
        try:
            self.logger.info(f'Invoking delete request url {url}, header: {header}', DEBUG_LEVEL_DEBUG)
            response = requests.delete(self.url, timeout=30, verify=self.certificate, headers=self.header)
        except Exception as e:
            self.logger.error(f'Failed to Invoke delete request: {str(e)}')
            return None
        return response


    def call_rest_api_post(self, url, request, header):
        self.logger.trace(url, header, caller_name='call_rest_api_post')
        self.url = url
        self.request = request
        self.header = header
        try:
            self.logger.info(f'Invoking post request url: {url} , header: {header}', DEBUG_LEVEL_DEBUG)
            rest_response = requests.post(self.url, data=self.request, timeout=30, verify=self.certificate, headers=self.header,
                                          stream=True)
        except Exception as e:
            self.logger.error(f"Error occurred during POST request to PVWA: {str(e)}")
            return None
        return rest_response
    
    def call_rest_api_patch(self, url, request, header):
        self.logger.trace(url, header, caller_name='call_rest_api_patch')
        self.url = url
        self.request = request
        self.header = header
        try:
            self.logger.info(f'Invoking PATCH request url: {url} , header: {header}', DEBUG_LEVEL_DEBUG)
            rest_response = requests.patch(self.url, data=self.request, timeout=30, verify=self.certificate, headers=self.header,
                                          stream=True)
        except Exception as e:
            self.logger.error(f"Error occurred during PATCH request to PVWA: {str(e)}")
            return None
        return rest_response


    # PvwaIntegration:
    # performs logon to PVWA and return the session token
    def logon_pvwa(self, username, password, pvwa_url, connection_session_id):
        self.logger.trace(pvwa_url, connection_session_id, caller_name='logon_pvwa')
        self.username = username
        self.password = password
        self.pvwa_url = pvwa_url
        self.connection_session_id = connection_session_id
        self.logger.info('Logging to PVWA')
        logon_url = f'{self.pvwa_url}/API/auth/Cyberark/Logon'
        rest_log_on_data = f"""
                            {{
                                "username": "{self.username}",
                                "password": "{self.password}",
                                "concurrentSession": "True"
                            }}
                            """
        try:
            rest_response = self.call_rest_api_post(logon_url, rest_log_on_data, DEFAULT_HEADER)
        except Exception as e:
            raise Exception(f"Error occurred on Logon to PVWA: {str(e)}")

        if not rest_response:
            self.logger.error("Connection to PVWA reached timeout")
            raise Exception("Connection to PVWA reached timeout")
        if rest_response.status_code == requests.codes.ok:
            self.logger.info("User authenticated")
            return rest_response.text.replace("\"","")
        self.logger.error(f"Authentication failed with response:\n{rest_response}")
        raise Exception("PVWA authentication failed")


    def logoff_pvwa(self, pvwa_url, connection_session_token):
        self.logger.trace(pvwa_url, connection_session_token, caller_name='logoff_pvwa')
        self.pvwa_url = pvwa_url
        self.connection_session_token = connection_session_token
        self.logger.info('Logging off from PVWA')
        header = DEFAULT_HEADER
        header.update({"Authorization": self.connection_session_token})
        log_off_url = f'{self.pvwa_url}/API/Auth/Logoff'
        rest_log_off_data = ""
        try:
            rest_response = self.call_rest_api_post(log_off_url, rest_log_off_data, header)
        except Exception:
            return

        if rest_response.status_code == requests.codes.ok:
            self.logger.info("session logged off successfully")
            return True
        self.logger.error("Logoff failed")
        return False
