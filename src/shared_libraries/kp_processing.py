import subprocess
import sys
from log_mechanism import LogMechanism

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
    save_key_pair(pem_key=pem_key)
    try:
        subprocess.call(["cp puttygen /tmp "], shell=True)
        subprocess.call(["chmod 777 /tmp/puttygen "], shell=True)
        subprocess.check_output("cat /tmp/pemValue.pem", shell=True)
        conversion = subprocess.check_output('/tmp/puttygen /tmp/pemValue.pem -O private -o /dev/stdout',
                                             shell=True, stderr=subprocess.PIPE)
        ppk_key = str(conversion).replace('\'', '').replace('\\n', '\n')
    except Exception as e:
        logger.error(f'Exception occured: {e}')
        raise Exception(f'Exception occured: {e}')
    if 'Private-Lines' in ppk_key:
        logger.info("Pem key successfully converted")
        print(f'\n\n\n_________________________\n{ppk_key}')
    else:
        logger.error("Failed to convert pem key to ppk", str(ppk_key))
        raise Exception('Failed to convert pem')

    return ppk_key


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
