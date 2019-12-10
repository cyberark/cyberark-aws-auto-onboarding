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
                    sudo apt-get install -y zip
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
        stage('Copy zips') {
            steps {
                sh '''
                    rm -rf reports/
                    rm -rf artifacts/
                    mkdir reports
                    mkdir artifacts
                    mkdir artifacts/aws_ec2_auto_onboarding
                    mkdir artifacts/aws_environment_setup
                    cp src/aws_ec2_auto_onboarding/aws_ec2_auto_onboarding.zip artifacts/
                    cp src/aws_environment_setup/aws_environment_setup.zip artifacts/
                    cd artifacts
                    unzip aws_ec2_auto_onboarding.zip -d aws_ec2_auto_onboarding
                    unzip aws_environment_setup.zip -d aws_environment_setup
                '''
            }
        }
        stage('Scan requirements file for vulnerabilities') {
            steps {
                sh '''
                    source ./.testenv/bin/activate
                    safety check -r requirements.txt --full-report > reports/safety.txt || true
                '''
            }
        }
        stage('Scan distributables code for vulnerabilities') {
            steps {
                sh '''
                    source ./.testenv/bin/activate
                    bandit -r artifacts/. --format html > reports/bandit.html || true
                '''
            }
        }
        stage('Deploy AOB solution')
        {
            steps{
                script{
                        withCredentials([
                            usernamePassword(credentialsId: 'aob-autodeployment-user', usernameVariable: 'VAULT_USERNAME', passwordVariable: 'VAULT_PASSWORD')
                        ])
                    sh '''
                        params=`python tests/describe_resources.py`
                        anisble-playbook deployment/AutoOnboarding.yml -e VaultUser=${VAULT_USERNAME} VaultPassword=${VAULT_PASSWORD} $params
                    '''
                }
            }
        }
        stage('Deploy AOB solution')
        {
            steps{
                script{
                    sh '''
                        pytest blah blah
                    '''
                }
            }
        }
    }
    post {
        success {
            archiveArtifacts artifacts: 'artifacts/*.zip', fingerprint: true
            archiveArtifacts artifacts: 'reports/*', fingerprint: true
        }
    }
}