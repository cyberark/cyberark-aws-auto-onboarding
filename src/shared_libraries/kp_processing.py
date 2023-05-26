import subprocess
import sys
import rsa
import base64
from log_mechanism import LogMechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = LogMechanism()


def save_key_pair(pemKey):
    # Save pem to file
    logger.trace(caller_name='save_key_pair')
    logger.debug('Saving key pair to file')
    savePemToFileCommand = 'echo {0} > /tmp/pemValue.pem'.format(pemKey)
    subprocess.call([savePemToFileCommand], shell=True)
    subprocess.call(["chmod 777 /tmp/pemValue.pem"], shell=True)


def convert_pem_to_ppk(pemKey):
    logger.trace(caller_name='convert_pem_to_ppk')
    logger.debug('Converting pem to ppk')
    #  convert pem file, get ppk value
    #  Uses Puttygen sent to the lambda
    save_key_pair(pemKey=pemKey)
    subprocess.call(["cp ./puttygen /tmp/puttygen"], shell=True)
    subprocess.call(["chmod 777 /tmp/puttygen "], shell=True)
    subprocess.check_output("ls /tmp -l", shell=True)
    subprocess.check_output("cat /tmp/pemValue.pem", shell=True)
    conversionResult = subprocess.call(["/tmp/puttygen /tmp/pemValue.pem -O private -o /tmp/ppkValue.ppk"], shell=True)
    if conversionResult == 0:
        ppkKey = subprocess.check_output("cat /tmp/ppkValue.ppk", shell=True).decode("utf-8")
        if 'Private-Lines' in ppkKey:
            logger.debug("Pem key successfully converted")
        else:
            logger.error("Failed to convert pem key to ppk")
            raise Exception("Failed to convert pem key to ppk")
    return ppkKey


def decrypt_password(instance_password_data):
    logger.trace(caller_name='decrypt_password')
    passwd = base64.b64decode(instance_password_data)
    with open ("/tmp/pemValue.pem", 'r') as f:
        private = rsa.PrivateKey.load_pkcs1(f.read())
    decrypted_password = rsa.decrypt(passwd,private).decode("utf-8")
    return decrypted_password
