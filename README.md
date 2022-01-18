
Protecting privileged accounts is never an easy task. They must be identified and managed, but in most cases it takes time and effort
to cover the entire organization's network. This process is even more challenging in Cloud environments, due to their dynamic nature.
Instances (containers and virtual servers) are ephemeral and may be spun up and down all the time, which can cause a situation where
privileged accounts of critical applications and workloads are not managed while they are active.

CyberArk provides a solution that detects unmanaged privileged SSH Keys in newly created Unix/Linux EC2 instances and unmanaged Windows
instances in Amazon Web Services (AWS) environments, and automatically onboards them to the CyberArk Vault. When an SSH Key\Password is
onboarded, it is immediately changed. This solution also detects when EC2 instances are terminated and subsequently deletes the irrelevant 
accounts from the Vault.

Unlike schedule-based scanners, this is an Event Driven discovery that detects changes in the environment in real time. AWS CloudWatch informs
CyberArk about new EC2 instances and triggers the CyberArk Lambda function that initiates the onboarding process.

The solution is packaged as a CloudFormation template, which automates deployment. We recommend that customers deploy it for all AWS accounts
and on all regions.

This solution supports CyberArk environments that are deployed in the Cloud and in hybrid architectures.

# Features
- Automatic onboarding and management of new AWS instances upon spin up
- Automatic de-provisioning of accounts for terminated AWS instances
- Multi region support - Single solution deployment for all regions in the AWS account 
- Near real time on boarding of new instances spinning up  


# Prerequisites
This solution requires the following:

1. The CyberArk PAS solution is installed on-prem / Cloud / hybrid with v9.10 or higher.
2. The CyberArk license must include SSH key manager.
3.  Network access from the Lambda VPC to CyberArk's PVWA.
4. The CPM that manages the SSH keys must have a network connection to the target devices (for example, vpc peering).
5. To connect to new instances, PSM must have a network connection to the target devices (for example, vpc peering).
6. The expected maximum number of instances must be within the number of accounts license limits.
7. PVWA is configured with SSL (unless its a POC environment).
8. In the "UnixSSH" platform, set the "ChangeNotificationPeriod" value to 60 sec (this platform will be used for managing Unix accounts,
and setting this parameter gives the instance time to boot before attempting to change the password).
9. In the "WinServerLocal" platform, set the "ChangeNotificationPeriod" value to 60 sec (this platform will be used for managing Unix accounts,
and setting this parameter gives the instance time to boot before attempting to change the password) .
10. Dedicated Vault user for the solution with the following authorizations (not Admin):

	| General Vault Permissions:|
	| ------ |
		 Add Safes

11. StackSet Enabled according to AWS documentation:
    https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/stacksets-prereqs-self-managed.html

12. If the Keypair and/or the Safes already exist (and are not created by the solution), the Vault user 
must be the owner of these Safes with the following permissions:

	|	 Key Pair Safe Permissions:|
	| ------ |
		Add Accounts
		List Accounts
		Retrieve Account
		Update Accounts Properties

	|	 Unix Accounts Safe Permissions:|
	| ------ |
		Add Accounts
		List Accounts
		Delete Account
		Update Accounts Properties
		Initiate CPM account management operations


# Deployment using Cloud Formation 
This solution requires NAT GW to allow Lambda access to the AWS resources  
For further information, see https://docs.aws.amazon.com/lambda/latest/dg/vpc.html \
For a CyberArk example network template, see: \
https://github.com/cyberark/pas-on-cloud/blob/master/aws/PAS-network-environment-NAT.json


1. Download cyberark-aws-auto-onboarding solution zip files and CloudFormation template from
[https://github.com/cyberark/cyberark-aws-auto-onboarding/tree/master/dist](https://github.com/cyberark/cyberark-aws-auto-onboarding/tree/master/dist)

2. Upload the solution to your S3 Bucket in the same region you want to deploy the solution.(* see note) 
3. Deploy CyberArk-AOB-MultiRegion-CF.json.
4. Deploy CyberArk-AOB-MultiRegion-CF-VaultEnvCreation.yaml.
5. Deploy CyberArk-AOB-MultiRegion-StackSet.json.
6. Upload the old/existing key pairs used to create instances in your AWS region to the Key Pair Safe in the Vault according to the following naming 
convention:\
[AWSAccount].[Region].[KeyPairName]\
example - 1231231231.us-east-2.Mykey


> ***Note:** Note: This solution must be installed in every AWS region. For each region, use a dedicated Vault user and make sure the Lambda VPC has network access to the PVWA.

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

2. Existing AWS instances (pre-installed) are not onboarded automatically (only after restart).
3. This solution currently handles a maximum of 100 events in 4 seconds.
4. EC2 instance public IPs must be elastic IPs to allow continuous access and management after changing the instance state.
5. For the CPM to manage new Windows instances for some versions (see the list below), the user must run the following command manually on all
new Windows instances:

```sh
netsh firewall set service RemoteAdmin enable
```

>**Note**: CPM will fail to rotate the password if this command has not been executed.

##### List of Windows instances that require this command to be run manually:

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

# Debugging and Troubleshooting
* There are three main lambdas:
	1. SafeHandler - Creates the safes for the solution and uploads the solution main key pair.
	2. Elasticity - Onboards new instances to PAS.
	3. TrustMechanism - Responsible for SSM integration.
>**Note**: You can find the lambdas by searching in the cloudformation's resource tab `AWS::Lambda::Function`

* All information about debugging is available through AWS CloudWatch and can be accessed easily
through each lambda function under the monitoring section.
* The debug level can be controlled by editing the SSM parameter - `AOB_Debug_Level`.
* There are 3 debug levels :
	* Info - Displays general information and errors.
	* Debug - Displays detailed information and errors.
	* Trace - Displays every call made by the solution in details.

# Contributing
Feel free to open pull requests with additional features or improvements!

1. Fork it.
2. Create your feature branch.
```sh
git checkout -b my-new-feature)
```
3. Commit your changes.
```sh
git commit -am 'Added some feature'
```
4. Push to the branch.
```sh
git push origin my-new-feature
```
5. Create a new Pull Request.


# Deleting the solution 
### Order of deletion:
1. Delete StackSet.
2. Delete the CloudFormations in the following order:
	- CyberArk-AOB-MultiRegion-CF-VaultEnvCreation
	- CyberArk-AOB-MultiRegion-CF


# Licensing
Copyright 1999-2020 CyberArk Software Ltd.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this software except in compliance with the License. You may obtain a copy of the License at

[http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

## This solution is provided to the community as a sample code and is not supported by CyberArk
