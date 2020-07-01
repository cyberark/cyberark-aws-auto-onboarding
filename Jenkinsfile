pipeline {
    agent {
        node {
            label 'ansible'
        }
    }
    environment {
        AWS_REGION = sh(script: 'curl -s http://169.254.169.254/latest/dynamic/instance-identity/document | python3 -c "import json,sys;obj=json.load(sys.stdin);print (obj[\'region\'])"', returnStdout: true).trim()
        shortCommit = sh(script: "git log -n 1 --pretty=format:'%h'", returnStdout: true).trim()
    }
    stages {
        stage('Install virtual environment') {
            steps {
                sh '''
                if [ $(dpkg-query -W -f='${Status}' zip 2>/dev/null | grep -c "ok installed") -eq 0 ]; then sudo apt-get install -y zip;  fi

                python3 -m pip install --user virtualenv
                python3 -m virtualenv .testenv
                source ./.testenv/bin/activate

                # Install lambda functions requirements
                pip install -r requirements.txt --target ./src/aws_ec2_auto_onboarding/package
                pip install -r requirements.txt --target ./src/aws_environment_setup/package

                # Install linting tools
                pip install cfn-lint pylint awscli ansible

                # Install security tools
                pip install safety bandit
                
                mkdir reports
                '''
            }
        }
        stage("linting & safty validation") {
          parallel {
/*            stage('Check syntax of python - pylint') {
                steps {
                  sh '''
                      source ./.testenv/bin/activate
                      find ./src -maxdepth 2 -type f -name "*.py" | xargs pylint --rcfile .pylintrc
                  '''
              }
            } */
            stage('Check syntax of CloudFormation templates') {
                steps {
                  sh '''
                      source ./.testenv/bin/activate
                      cfn-lint ./dist/**/*.json
                  '''
              }
            }
            stage('Validate CloudFormation templates') {
                steps {
                  sh '''
                      aws cloudformation validate-template --template-body file://dist/multi-region-cft/CyberArk-AOB-MultiRegion-CF.json --region ${AWS_REGION}
                      aws cloudformation validate-template --template-body file://dist/multi-region-cft/CyberArk-AOB-MultiRegion-CF-VaultEnvCreation.yaml --region ${AWS_REGION}
                      aws cloudformation validate-template --template-body file://dist/multi-region-cft/CyberArk-AOB-MultiRegion-StackSet.json --region ${AWS_REGION}
                  '''
              }
            }
            stage('Scan requirements file for vulnerabilities - safety') {
                steps {
                  sh '''
                      source ./.testenv/bin/activate
                      safety check -r requirements.txt --full-report > reports/safety.txt
                  '''
              }
            }
          }
        }
        stage("Package zips") {
          parallel {
            stage('Package aws_environment_setup lambda function') {
               steps {
                 sh '''
                     cp -R src/shared_libraries/* src/aws_environment_setup
                     ls src/aws_environment_setup
                     cd src/aws_environment_setup
                     cd package
                     zip -r9 ${OLDPWD}/aws_environment_setup.zip .
                     cd $OLDPWD
                     zip -g aws_environment_setup.zip aws_services.py aws_environment_setup.py instance_processing.py kp_processing.py pvwa_api_calls.py pvwa_integration.py log_mechanism.py chilkat/*
                 '''
              }
            }
            stage('Package aws_ec2_auto_onboarding lambda function') {
              steps {
                sh '''
                     cp -R src/shared_libraries/* src/aws_ec2_auto_onboarding
                     ls src/aws_ec2_auto_onboarding
                     cd src/aws_ec2_auto_onboarding
                     cd package
                     zip -r9 ${OLDPWD}/aws_ec2_auto_onboarding.zip .
                     cd $OLDPWD
                     zip -g aws_ec2_auto_onboarding.zip aws_services.py aws_ec2_auto_onboarding.py instance_processing.py kp_processing.py pvwa_api_calls.py pvwa_integration.py puttygen log_mechanism.py chilkat/*
                 '''
              }
            }
          }
        }
        stage('Copy zips') {
          steps {
            sh '''
               rm -rf artifacts/
               mkdir -p reports artifacts/{aws_ec2_auto_onboarding,aws_environment_setup}
               cp src/aws_ec2_auto_onboarding/aws_ec2_auto_onboarding.zip src/aws_environment_setup/aws_environment_setup.zip artifacts/
               cd artifacts
               unzip aws_ec2_auto_onboarding.zip -d aws_ec2_auto_onboarding
               unzip aws_environment_setup.zip -d aws_environment_setup
            '''
          }
        }
/*        stage('Scan distributables code for vulnerabilities - bandit') {
          steps {
            sh '''
                source ./.testenv/bin/activate
                bandit -r artifacts/. --format html > reports/bandit.html || true
            '''
          }
        } */
        stage('Upload artifacts to S3 Bucket') {
          steps {
            sh '''
                cd artifacts
                aws s3 cp aws_environment_setup.zip s3://aob-auto-test
                aws s3 cp aws_ec2_auto_onboarding.zip s3://aob-auto-test
            '''
          }
        }
        // stage('Git clone AOB') {
        //     steps{
        //         script{
        //             try{
        //                 git credentialsId: 'jenkins-github-access-token', url: 'https://github.com/cyberark/cyberark-aws-auto-onboarding.git'
        //                 dir ('cyberark-aws-auto-onboarding') {
        //                     sh '''
        //                         git clone --single-branch --branch develop https://github.com/cyberark/cyberark-aws-auto-onboarding.git
        //                     '''
        //                 }
        //             } catch (err) {
        //                 echo err.getMessage()
        //                 sh '''
        //                     git pull
        //                   '''
        //             }
        //         }
        //     }
        // }
        // stage('Git clone AOB tests') {
        //     steps{
        //         script{
        //             git credentialsId: 'jenkins-github-access-token', url: 'https://github.com/cyberark/cyberark-aws-auto-onboarding-tests.git'
        //             dir ('cyberark-aws-auto-onboarding-tests') {
        //             }
        //         }
        //     }
        // }
        // stage('Deploy AOB solution')
        // {
        //     steps{
        //         sh '''
        //             source ./.testenv/bin/activate
        //             cd tests/
        //             ansible-playbook aob_environment_setup.yml -e "{rollback: False, deploy_main_cf: False, deploy_vaultenv: False, deploy_stackset: False}" -vvv
        //         '''
        //     }
        // }
        // stage('Copy PVWA server certificate to jenkins slave')
        // {
        //     steps{
        //         sh '''
        //             sudo aws s3 cp s3://aob-auto-test/server.crt /etc/ssl/certs/server.crt
        //         '''
        //     }
        // }
        // stage('Run Tests')
        // {
        //     steps{
        //         sh '''
        //             source ./.testenv/bin/activate
        //             cd tests/e2e-tests/
        //             python3 main.py
        //         '''
        //     }
        // }
    }
    post {
    //     success {
    //         archiveArtifacts artifacts: 'artifacts/*.zip', fingerprint: true
    //         archiveArtifacts artifacts: 'reports/*', fingerprint: true
    //     }
      always {
        archiveArtifacts artifacts: 'reports/*', fingerprint: true
      }
    }
}
// anisble-playbook deployment/AutoOnboarding.yml -e VaultUser=${VAULT_USERNAME} VaultPassword=${VAULT_PASSWORD} Accounts='138339392836' PvwaIP='' ComponentsVPC='vpc-075eadb618b1a070f' PVWASG='vpc-075eadb618b1a070f' ComponentsSubnet='subnet-0bb6e84a4548c51b1' KeyPairName='pcloud-test-instances-KP'