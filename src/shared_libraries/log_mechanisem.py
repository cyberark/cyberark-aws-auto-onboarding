import boto3
import json

DEBUG_LEVEL_INFO = 'info' # Outputs erros and info only.
DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information

class log_mechanisem:
    def __init__(self):
        self.debug_level = get_debug_level()
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
    AOB_DEBUG_LEVEL = "AOB_Debug_Level"
    lambdaClient = boto3.client('lambda')

    lambdaRequestData = dict()
    lambdaRequestData["Parameters"] = [AOB_DEBUG_LEVEL]
    try:
        response = lambdaClient.invoke(FunctionName='TrustMechanism',
                                       InvocationType='RequestResponse',
                                       Payload=json.dumps(lambdaRequestData))
    except Exception as e:
        raise Exception("Error retrieving parameters from parameter parameter store:{0}".format(e))
    
    jsonParsedResponse = json.load(response['Payload'])
    # parsing the parameters, jsonParsedResponse is a list of dictionaries
    for ssmStoreItem in jsonParsedResponse:
        if ssmStoreItem['Name'] == AOB_DEBUG_LEVEL:
            aob_debug_level = ssmStoreItem['Value']
    return aob_debug_level