import boto3
import json

DEBUG_LEVEL_INFO = 'info' # Outputs erros and info only.
DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information

class log_mechanisem:
    def __init__(self):
        self.debug_level = get_debug_level()
        print(self.debug_level)
    def error(self, message,debug_level=DEBUG_LEVEL_INFO):
        if debug_level == self.debug_level.lower or self.debug_level.lower == 'trace':
            print('[ERROR] ' + message)
    def info(self, message,debug_level=DEBUG_LEVEL_INFO):
        if debug_level == self.debug_level.lower or self.debug_level.lower == 'trace':
            print('[INFO] ' + message)
    def trace(self,*args, caller_name):
        if self.debug_level.lower == 'trace':
            print ('[TRACE] {caller_name}:\n'.format(caller_name=caller_name), args, sep = ' | ')
        
def get_debug_level():
    ssm = boto3.client('ssm')
    ssm_parameter = ssm.get_parameter(
        Name='AOB_Debug_Level'
    )
    aob_debug_level = ssm_parameter['Parameter']['Value']
    return aob_debug_level