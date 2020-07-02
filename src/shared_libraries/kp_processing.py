import subprocess
import sys
from log_mechanism import LogMechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = LogMechanism()


def save_key_pair(pemKey):
    # Save pem to file
    logger.trace(caller_name='save_key_pair')
    logger.info('Saving key pair to file')
    savePemToFileCommand = 'echo {0} > /tmp/pemValue.pem'.format(pemKey)
    subprocess.call([savePemToFileCommand], shell=True)
    subprocess.call(["chmod 777 /tmp/pemValue.pem"], shell=True)


def convert_pem_to_ppk(pemKey):
    logger.trace(caller_name='convert_pem_to_ppk')
    logger.info('Converting pem to ppk')
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
        if 'Private-Lines' in ppk_key:
            print("Pem key successfully converted")
        else:
            print("Failed to convert pem key to ppk")
            raise Exception("Failed to convert pem key to ppk"))
    return False

    return ppkKey


def run_command_on_container(command, print_output):
    logger.trace(caller_name='run_command_on_container')
    decrypted_password = ""
    with subprocess.Popen(' '.join(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True) as process:
        if print_output:
            decrypted_password = print_process_outputs_on_end(process)
        else:
            process.wait()
    return [process.returncode, decrypted_password]


def print_process_outputs_on_end(process):
    logger.trace(caller_name='print_process_outputs_on_end')
    out = process.communicate()[0].decode('utf-8')
    # out = filter(None, map(str.strip, out.decode('utf-8').split('\n')))
    return out
