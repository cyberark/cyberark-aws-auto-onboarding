Protecting privileged accounts is never an easy task. They must be identified and managed, but in most cases it takes time and effort to cover the entire organization network. This process is challenged even more in Cloud environments, due to its dynamic nature. Instances (containers and virtual servers) are ephemeral and may be spun up and down all the time, which may cause a situation in which privilege accounts of critical applications and workloads are not managed while they are active.

CyberArk provides a solution that detects unmanaged privileged SSH Keys in new created Unix/Linux EC2 instances in Amazon Web Services (AWS) environments, and automatically onboards them to the CyberArk Vault. Once an SSH Key is onboarded, it is changed immediately. This solution also detects when EC2 instances are terminated and subsequently deletes the irrelevant accounts from the Vault. 

Unlike schedule-based scanners, this is an Event Driven discovery that detects changes in the environment in real time. AWS CloudWatch informs CyberArk about new EC2 instances, and triggers the CyberArk Lambda function that initiates the onboarding process.

The solution is packaged as CloudFormation template, which automates deployment. We recommend that customers deploy it for all AWS accounts and on all Regions.

This solution supports CyberArk environments that are deployed in Cloud, and Hybrid architectures.


# Features
- Automatic onboarding and management of new AWS instances upon spin up
- Automatic de-provision accounts for terminated AWS instances
- Multi region support - Single solution deployment for all regions in the AWS account 
- Near real time on boarding of new instances spinning up  
- Deployment with Ansible


# Prerequisites
This solution requires the following:

1. CyberArk PAS solution installed on prem / Cloud / Hybrid with v9.10 or higher 
2. Cyberark license must include SSH key manager 
3. Network access from the Lambda VPC to CyberArk's PVWA
4. The CPM that manages the SSH keys must have a network connection to the target devices
5. To connect to new instances, PSM must have a network connection to the target devices
6. The expected maximum number of instances must be within the number of accounts license limits  
7. In the "UnixSSH" platform, set the "ChangeNotificationPeriod" value to 60 sec (this platform will be used for managing Unix accounts, and setting this parameter gives the instance time to boot before attempting to change the password) 
8. In the "WinServerLocal" platform, set the "ChangeNotificationPeriod" value to 60 sec (this platform will be used for managing Unix accounts, and setting this parameter gives the instance time to boot before attempting to change the password) 
9. Dedicated Vault user for the solution with the following authorizations (not Admin):

| General Vault Permissions|
| ------ |
|Add Safes|

10. If the Keypair and/or the Safes already exist (not created by the solution), the Vault user must be the owner of these Safes with the following permissions:

|Key Pair Safe Permissions|
| ------ |
|Add Accounts|
|List Accounts|
|Retrieve Account|
|Update Accounts Properties|

|Unix Accounts Safe Permissions|
| ------ |
|Add Accounts|
|List Accounts|
|Delete Account|
|Update Accounts Properties|
|Initiate CPM account management operations|


#  Deployment using Ansible 
Requirements for deployment:

- AWS IAM User strong privileges for deploying IAM roles and policies with CloudFormation
- Python 3.6 or higher installed

Steps:
1. Install virtual environment
`pip install virtualenv`
2. Clone auto-onboarding repository
`git clone https://github.com/cyberark/cyberark-aws-auto-onboarding.git`
3. Create a new virtual environment using Requirements.txt
`virtualenv AOB`
3. Activate the virtualenv
`source AOB/bin/activate`
4. Change directory to cyberark-aws-auto-onboarding/deployment
`cd cyberark-aws-auto-onboarding/deployment`
5. Install required packages using requirements.txt
`pip install -r cyberark-aws-auto-onboarding/`
6. edit vars/AOB-Params.yml according to the comments
7. run the playbook and provide two parameters - VaultUser , VaultPassword
`ansible-playbook VaultUser=<Vault Administrative user > VaultPassword=<MuchSecureVeryWow> `




# Deployment using Cloud Formation 

This solution requires NAT GW to allow Lambda access to the AWS resources  
Reference for further information: https://docs.aws.amazon.com/lambda/latest/dg/vpc.html
(Cyberark reference network template already contain NAT GW so please use it for POC 
https://github.com/cyberark/pas-on-cloud/blob/master/aws/PAS-network-environment-NAT.json)


1. Download cyberark-aws-auto-onboarding solution zip files and CloudFormation template from [https://github.com/cyberark/cyberark-aws-auto-onboarding/tree/master/dist](https://github.com/cyberark/cyberark-aws-auto-onboarding/tree/master/dist)

2. Upload the solution to your S3 Bucket in the same region you want to deploy the solution.(* see note) 
3. Upload the NAT-Gateway_0.1.0.json template to the bucket as well.(** see note)
This template will be called by the main CFT as a nested template and will create the NAT GW in the VPC
4. Open the CloudFormation, fill in all the details (see below) and launch it
5. Upload the old/existing key pairs used to create instances in your AWS region to the Key Pair Safe in the Vault 

Update the account User name with  the following naming convention: AWS.[AWS Account].[Region name].[key pair name]

> ***Note:** that this solution must to be installed in every AWS region. For each region, use a dedicated Vault user and make sure the Lambda VPC has a network acess to the PVWA.

> ****Note:** This step is only relevant if you deploy the NAT CFT - aws _auto_onboarding_0.1.1_with_NAT.json

# CloudFormation Template 
The following table lists the parameters to provide in the CloudFormation:

|Parameter Name | Description |
| ------ | ------ |
|Bucket Name|	The name of the S3 bucket where the Lambda is located|
|PVWA IP|	PVWA server/instance IP address|
|VPC |	Lambda's VPC that contains the subnet with access permissions to the PVWA|
|Subnet	| The Lambda's subnet with access permissions to the PVWA|
|Vault user name |The name of the Vault user that has permissions to create and delete accounts in target Safes. (Note: Follow the guidelines)|
|Vaut user password|	The password for the Vault user|
|Target safe for Unix accounts	| The name of the Safe to which the SSH Keys will be onboarded (Note: The deployment will fail if the safe already exist)|
|CPMUnix name | The name of the CPM that will manage the onboarded SSH Keys|
|Target safe for Windows accounts	| The name of the Safe to which the windows accounts will be onboarded (Note: The deployment will fail if the safe already exist)|
|CPMWindows Name | The name of the CPM that will manage the onboarded SSH Keys|
|Target safe for the Key Pairs| The name of the Safe to which the Key Pairs created by CyberArk will be onboarded (Note: The deployment will fail if the safe already exist)|
|Key Pair name|The name of the Key Pair, if it needs to be created by CyberArk (Note: CyberArk creates the Key Pair and stores it in the Vault. The Key Pair is never downloaded to users' endpoints.)|
|Public NAT GW CIDR*|The IPv4 range of addresses for the NAT GW public subnet|
|Private NAT GW CIDR*|The IPv4 range of addresses for the NAT GW private subnet|
|Internet GW ID*|The ID of the internet GW that exist in the VPC|

>***Note:** These fields only exist in the Elasticity v0.1.1 - With NAT.json template 

# Deploy Secondary Cloud Formation - StackSet
- When the Main CloudFormation deployment ends, click on the Stack and navigate to 'Resources' section
  - Search 'Elasticity' and press on 'ElasticityLambda' link
  - Save for later the 'ARN' of the Lambda 
- From GIT copy the content of CyberArk-AOB-MultiRegion-StackSet.json and save it locally or in S3 Bucket
- In Cloud Formation service, in left pane Navigate to 'StackSets'
- Press on Create StackSet
- Select 'Tempate is ready' and the location of the file you saved before
- Enter a name for the Stack Set
- Enter the 'ARN' of the lambda that you saved before
- Press 'Next'
- In 'Configure StackSet options' press 'Next'
- In 'Set deployment options' Enter the Account ID that the solution is deployed (the current Account ID)
- Choose the Regions to provision
- Press 'Next'
- In 'Review' press 'Submit'


# Solution Upgrade Procedure 
1. Replace the solution files in the bucket 
2. Update the cloudFormation stack with the new template

# Limitations
1. CyberArk currently supports onboarding SSH keys for the following AWS accounts:
 - AWS Linux, RHL AMIs: ec2-user
 - Ubuntu: ubuntu user
 - Centos: centos user
 - openSuse: root user
 - Debian: admin user
 - Fedora: fedora user
> Amazon AMI/custom AMI with a key that was created by the solution or uploaded in advance to the Safe in the Vault supplied in the solution deployment (not supplied hard coded by Amazon)

2. Existing AWS instances (pre-installed) are not onboarded automatically
3. This solution currently handles a maximum of 100 events in 4 seconds
4. EC2 instance public IPs must be elastic IPs to allow continous access and management after changing the instance state.
5. in order for the CPM to manage new Windows instances for some versions (you can find the list below), the user must run the following command manually on all new Windows instances:

```sh
netsh firewall set service RemoteAdmin enable
```

>**Note**: The CPM will fail to rotate the password in a case this command hasn't been executed

###### List of Windows instances that require this command to be run manually:

- Microsoft Windows Server 2016 Base
- Microsoft Windows Server 2016 Base with Containers
- Microsoft Windows Server 2016 with SQL Server 2017 Express
- Microsoft Windows Server 2016 with SQL Server 2017 Web 
- Microsoft Windows Server 2016 with SQL Server 2017 Standard
- Microsoft Windows Server 2016 with SQL Server 2017 Enterprise
- Microsoft Windows Server 2016 with SQL Server 2016 Express
- Microsoft Windows Server 2016 with SQL Server 2016 Web 
- Microsoft Windows Server 2016 with SQL Server 2016 Standard
- Microsoft Windows Server 2016 with SQL Server 2016 Enterprise

# Debugging
All information about debugging is available through AWS CloudWatch

# Contributing
Feel free to open pull requests with additional features or improvements!

1. Fork it
2. Create your feature branch
```sh
git checkout -b my-new-feature)
```
3. Commit your changes
```sh
git commit -am 'Added some feature'
```
4. Push to the branch
```sh
git push origin my-new-feature
```
5. Create a new Pull Request


# Deleting the solution 

Delete StackSet

- Open CloudFormation Service in the region that you deployed the following CFs:
- From StackSet choose that stack for CyberArk-AOB-MultiRegion-StackSet.json
- In Actions drop down list, click on "Delete stacks from StackSet"
- In Account numbers enter the current Account ID (Secondary Account ID)
- In Specify regions press on "Add all regions"
- Press on "Next"
- in next page press on "Submit"
- Verify that new operation is in "Running" state, in type "DELETE"
- Wait until Operation shows "SUCCEEDED"
- Again - From Stacks choose that stack for CyberArk-AOB-MultiRegion-StackSet.json
- From Actions choose "Delete StackSet"

Delete the CloudFormation 

- Open CloudFormation Service in the region that you deployed the following CFs:
- CyberArk-AOB-MutliRegion-CF.json
- From Stacks choose that stack for CyberArk-AOB-MutliRegion-CF.json
- press Delete
- Wait until finished (you can hit the refresh button to view progress)


There is a known issue with auto-deleting the network interface of a Lambda deployed in an existing VPC. Therefore, follow these steps when deleting the stack: 

1. Wait for the following status event in the cloud formation log:
```sh
“CloudFormation is waiting for NetworkInterfaces associated with the Lambda Function to be cleaned up.”
```
2. Go to: EC2 → Network Interfaces
3. Choose the network interface of your stack and then perform Detach and Delete 



# Troubleshooting Tools 
All Instance on boarding status is saved in a DynamoDB table that is located under :
DynamoDB→ Tables → Instances   , Go to the Items tab
All solution logs are written to CloudWatch , available under :
CloudWatch → Logs , Search for your cloud formation stack name 


# Licensing
Copyright 1999-2018 CyberArk Software Ltd.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this software except in compliance with the License. You may obtain a copy of the License at

[http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.
