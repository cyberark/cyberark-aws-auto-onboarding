#!/bin/sh

ENVIRONMENT_LAMBDA_ZIP=${ENVIRONMENT_LAMBDA_ZIP:-aws_environment_setup.zip}
ONBOARDING_LAMBDA_ZIP=${ONBOARDING_LAMBDA_ZIP:-aws_ec2_auto_onboarding.zip}

log_info () {
    local NO_FORMAT="\033[0m"
    local C_GOLD1="\033[38;5;220m"
    echo -e "${C_GOLD1}[INFO]${NO_FORMAT} $1"
}

log_done () {
    local NO_FORMAT="\033[0m"
    local C_GREEN3="\033[38;5;34m"
    echo -e "${C_GREEN3}[DONE]${NO_FORMAT} $1"
}

# Fetch python requirements
log_info "Fetching dependencies"
pip install --quiet -r /tmp/requirements.txt --target /tmp/cache/package

log_done Fetched!

# Create aws_environment_setup.zip package
log_info "Building $ENVIRONMENT_LAMBDA_ZIP"
rm -f ${ENVIRONMENT_LAMBDA_ZIP}

cd /tmp/cache/package
zip -q -r9 /tmp/output/${ENVIRONMENT_LAMBDA_ZIP} .

cd /tmp/src/aws_environment_setup
zip -q -g /tmp/output/${ENVIRONMENT_LAMBDA_ZIP} AWSEnvironmentSetup.py

log_done "${ENVIRONMENT_LAMBDA_ZIP} built!"

# Create aws_ec2_auto_onboarding.zip package
log_info "Building ${ONBOARDING_LAMBDA_ZIP}"
rm -f ${ONBOARDING_LAMBDA_ZIP}

cd /tmp/cache/package
zip -q -r9 /tmp/output/${ONBOARDING_LAMBDA_ZIP} .

cd /tmp/src/aws_ec2_auto_onboarding
zip -q -g /tmp/output/${ONBOARDING_LAMBDA_ZIP} aws_services.py AWSEc2AutoOnboarding.py instance_processing.py kp_processing.py pvwa_api_calls.py pvwa_integration.py puttygen

log_done "${ONBOARDING_LAMBDA_ZIP} built!"
