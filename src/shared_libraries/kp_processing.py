import subprocess
import sys
from log_mechanism import LogMechanism

DEBUG_LEVEL_DEBUG = 'debug' # Outputs all information
logger = LogMechanism()


def save_key_pair(pem_key):
    logger.trace(pem_key, caller_name='save_key_pair')
    logger.info('Saving key pair to file')
    # Save pem to file
    with open('pemValue.pem', 'w') as f:
        print(str(pem_key), file=f)
    #subprocess.call(f'echo {pem_file} > /tmp/pemValue.pem', shell=True)
    subprocess.call(["chmod 777 pemValue.pem"], shell=True)


def convert_pem_to_ppk(pem_key):
    logger.trace(caller_name='convert_pem_to_ppk')
    logger.info('Converting key pair from pem to ppk')
    #  convert pem file, get ppk value
    #  Uses Puttygen sent to the lambda
    save_key_pair(pem_key=pem_key)
    subprocess.call(["chmod 777 puttygen "], shell=True)
    subprocess.check_output("cat pemValue.pem", shell=True)
    conversion = subprocess.Popen(['puttygen', 'pemValue.pem', '-O', 'private', '-o',
                                   'ppkValue.ppk'], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    conversion.wait()
    conversion_result = conversion.returncode
    Remove_Me = subprocess.Popen(['cat', 'ppkValue.ppk'], stdout=subprocess.PIPE)
    logger.trace(conversion_result, Remove_Me.stdout.read() ,caller_name='convert_pem_to_ppk')
    if conversion_result == 0:
        ppk_key = subprocess.check_output("cat ppkValue.ppk", shell=True).decode("utf-8")
        logger.info("Pem key successfully converted")
        print(ppk_key)
    else:
        logger.error("Failed to convert pem key to ppk", conversion.stdout.read())
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
