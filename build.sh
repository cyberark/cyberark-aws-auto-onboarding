#!/bin/bash

docker build -t aws_onboarding_lambda_builder ./docker

# Mount sources
docker run  --rm \
            --mount type=bind,source=${PWD}/src,target=/tmp/src \
            --mount type=bind,source=${PWD}/requirements.txt,target=/tmp/requirements.txt \
            --mount type=bind,source=${PWD}/dist/lambdas,target=/tmp/output \
            -e ENVIRONMENT_LAMBDA_ZIP="aws_environment_setup_0.1.1.zip" \
            -e ONBOARDING_LAMBDA_ZIP="aws_ec2_auto_onboarding_0.1.1.zip" \
            aws_onboarding_lambda_builder