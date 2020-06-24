import subprocess
from log_mechanism import log_mechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = log_mechanism()


def save_key_pair(pemKey):
    logger.trace(pemKey, caller_name='save_key_pair')
    logger.info('Saving key pair to file')
    # Save pem to file
    savePemToFileCommand = 'echo {0} > /tmp/pemValue.pem'.format(pemKey)
    subprocess.call([savePemToFileCommand], shell=True)
    subprocess.call(["chmod 777 /tmp/pemValue.pem"], shell=True)


def convert_pem_to_ppk(pemKey):
    logger.trace(caller_name='convert_pem_to_ppk')
    logger.info('Converting key pair from pem to ppk')
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
        logger.info("Pem key successfully converted")
    else:
        logger.error("Failed to convert pem key to ppk")
        return False

    return ppkKey


def run_command_on_container(command, print_output):
    logger.trace(caller_name='run_command_on_container')
    decryptedPassword = ""
    with subprocess.Popen(' '.join(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True) as p:
        if print_output:
            decryptedPassword = print_process_outputs_on_end(p)
        else:
            p.wait()
    return [p.returncode, decryptedPassword]


def print_process_outputs_on_end(p):
    logger.trace(caller_name='print_process_outputs_on_end')
    out = p.communicate()[0].decode('utf-8')
    # out = filter(None, map(str.strip, out.decode('utf-8').split('\n')))
    return out
