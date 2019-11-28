pipeline {
    agent {
        node {
            label 'ansible'
        }
    }
    environment {
        AWS_REGION = sh(script: 'curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | python -c "import json,sys;obj=json.load(sys.stdin);print obj[\'region\']"', returnStdout: true).trim()
        shortCommit = sh(script: "git log -n 1 --pretty=format:'%h'", returnStdout: true).trim()
    }
    stages {
        stage('Install virtual environment') {
            steps {
                sh '''
                    apt-get install zip
                    python -m pip install --user virtualenv
                    python -m virtualenv --no-site-packages .testenv
                    source ./.testenv/bin/activate
                    
                    # Install lambda functions requirements
                    pip install -r requirements.txt --target ./src/aws_ec2_auto_onboarding/package
                    pip install -r requirements.txt --target ./src/aws_environment_setup/package
                    
                    # Install security tools
                    pip install safety bandit
                '''
            }
        }
        stage('Package aws_environment_setup lambda function') {
            steps {
                sh '''
                    cd src/aws_environment_setup
                    cd package
                    zip -r9 ${OLDPWD}/aws_environment_setup.zip .
                    cd $OLDPWD
                    zip -g aws_environment_setup.zip AWSEnvironmentSetup.py
                '''
            }
        }
        stage('Package aws_ec2_auto_onboarding lambda function') {
            steps {
                sh '''
                    cd src/aws_ec2_auto_onboarding
                    cd package
                    zip -r9 ${OLDPWD}/aws_ec2_auto_onboarding.zip .
                    cd $OLDPWD
                    zip -g aws_ec2_auto_onboarding.zip aws_services.py AWSEc2AutoOnboarding.py instance_processing.py kp_processing.py pvwa_api_calls.py pvwa_integration.py puttygen
                '''
            }
        }
    }
}