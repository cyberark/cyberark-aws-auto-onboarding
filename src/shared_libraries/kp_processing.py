import subprocess
from log_mechanism import LogMechanism
from chilkat import CkSshKey

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = LogMechanism()


def save_key_pair(pem_key):
    logger.trace(pem_key, caller_name='save_key_pair')
    logger.info('Saving key pair to file')
    # Save pem to file
    with open('/tmp/pemValue.pem', 'w') as f:
        print(str(pem_key), file=f)
    #subprocess.call(f'echo {pem_file} > /tmp/pemValue.pem', shell=True)
    subprocess.call(["chmod 777 /tmp/pemValue.pem"], shell=True)


def convert_pem_to_ppk(pem_key):
    logger.trace(caller_name='convert_pem_to_ppk')
    logger.info('Converting key pair from pem to ppk')
    #  convert pem file, get ppk value
    #  Uses Puttygen sent to the lambda
    chilkat_key = CkSshKey()
    save_key_pair(pem_key=pem_key)
    is_loaded = chilkat_key.FromOpenSshPrivateKey(pem_key)
    if not is_loaded:
        logger.error('Convert ', chilkat_key.lastErrorText())
        raise Exception('Failed to load pem file')
    key = chilkat_key.toPuttyPrivateKey(False)
    if not key:
        logger.error('Convert ', chilkat_key.lastErrorText())
        raise Exception('Failed to convert pem')
    logger.trace(key, caller_name='convert_pem_to_ppk')
    if key:
        logger.info("Pem key successfully converted")
    else:
        logger.error("Failed to convert pem key to ppk")
        raise Exception('Failed to convert pem')
    return key


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
