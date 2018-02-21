Protecting privileged accounts is never an easy task. They must be identified and managed, but in most cases it takes time and effort to cover the entire organization network. This process is challenged even more in Cloud environments, due to its dynamic nature. Instances (containers and virtual servers) may be spinning up and down all the time, which can cause a situation in which critical applications are not managed while they are active.

CyberArk provides a solution that detects unmanaged privileged SSH Keys in new Unix/Linux or Windows based EC2 instances in Amazon Web Services (AWS) environments, and automatically onboards them to the CyberArk Vault. This solution also detects when EC2 instances are deprecated and subsequently deletes the irrelevant accounts from the Vault. Once the SSH Key or password is onboarded, it is changed immediately.

Unlike schedule-based scanners, this solution was designed using Event Driven architecture. AWS CloudWatch informs CyberArk about new EC2 instances, and triggers the CyberArk Lambda function that initiates the onboarding process.

The solution is wrapped with a CloudFormation template, which automates deployment. We recommend that customers deploy it for all AWS accounts and on all Regions.

This solution supports CyberArk environments that are deployed in Cloud, and Hybrid architectures.

Note: This code is provided as a sample only and is not intended to run in a production environment. It is not supported by CyberArk. – not sure about this we will have to advise with legal




Features
•Automatic onboarding and management of new AWS instances upon spin up
•Automatic deletion of AWS instance accounts upon spin down 




Prerequisites

This solution requires the following:
1.CyberArk PAS solution installed on prem / Cloud / Hybrid with v9.10 or higher 
2.Cyberark license must include SSH key manager 
3.Network access from the Lambda VPC to CyberArk's PVWA
4.The CPM that manages the SSH keys must have a network connection to the target devices
5.To connect to new instances, PSM must have a network connection to the target devices
6.The expected maximum number of instances must be within the number of accounts license limits  
7.In the "UnixSSH" platform, set the "ChangeNotificationPeriod" value to 60 sec (this platform will be used for managing Unix accounts, and setting this parameter gives the instance time to boot before attempting to change the password) 

8.Dedicated Vault user for the solution with the following authorizations (not Admin):





General Vault Permissions

Add Safes 


9.If the Keypair and/or the Unix Accounts Safes already exist (not created by the solution), the Vault user must be the owner of these Safes with the following permissions:





Key Pair Safe Permissions


Add Accounts
 
List Accounts 
Retrieve Account 
Update Accounts Properties 





Unix Accounts Safe Permissions


Add Accounts
 
List Accounts 
Delete Account 
Update Accounts Properties 
Initiate CPM account management operations  


Deployment Options 

This solution requires NAT GW to allow Lambda access to the AWS resources  

Reference for further information: https://docs.aws.amazon.com/lambda/latest/dg/vpc.html

We have released two CFTs:

1.aws _auto_onboarding_0.1.1.json - This CFT is for use when you already have NAT GW in the VPC you plan to use for the Lambda deployment 

2.aws _auto_onboarding_0.1.1_with_NAT.json  This CFT is for use when you do not have NAT GW in the VPC you plan to use for the Lambda deployment 

Deployment  
1.Download the Event Driven Automatic Onboarding solution from the public GIT
https://github.com/cyberark/cyberark-aws-auto-onboarding

2.Upload the solution to your S3 Bucket in the region in which you will deploy the solution. ** see note 
Upload the NAT-Gateway_0.1.0.json template to the bucket as well. * see note
This template will be called by the main CFT as a nested template and will create the NAT GW in the VPC

      4. Open the CloudFormation and fill in all the details (see below) 

          Note:  If your AWS accounts are already managed by CyberArk, specify the name of the Safe in the "Target safe for xxx accounts" parameter

      5. Execute the CloudFormation.

      6. Upload the old/existing key pairs used to create instances in the AWS region to the Key Pair Safe in the Vault.

  Update the account's User name with  the following naming convention: AWS.<AWS Account>.<Region name>.<key pair name>




Notes:

         * This step is only relevant if you deploy the NAT CFT -  aws _auto_onboarding_0.1.1_with_NAT.json

** This solution must be installed in every AWS region. For each region, use a dedicated Vault user and make sure the Lambda VPC has network acess to the PVWA.

CloudFormation input screen: 

The following table lists the parameters to provide in the CloudFormation:






Parameter

Description

Bucket Name The name of the S3 bucket where the Lambda platform is located 
PVWA IP PVWA server/instance IP address 
VPC Lambda's VPC that contains the subnet with access permissions to the PVWA 
Subnet The Lambda's subnet with access permissions to the PVWA 
Vault user name 
The name of the Vault user that has permissions to create and delete accounts in target Safes
** Note: Follow the guidelines
 
Vaut user password The password for the Vault user 
Target safe for Unix accounts 
The name of the Safe to which the SSH Keys will be onboarded

** Note: If this Safe does not exist, it will be created automatically
 
CPM name 
The name of the CPM that will manage the onboarded SSH Keys
 
Target safe for Windows accounts 
The name of the Safe to which the passwords will be onboarded

** Note: If this Safe does not exist, it will be created automatically
 
CPM name The name of the CPM that will manage the onboarded passwords  
Target safe for the Key Pairs 
The name of the Safe to which the Key Pairs created by CyberArk will be onboarded

** Note: If this Safe does not exist, it will be created automatically
 
Key Pair name 
The name of the Key Pair, if it needs to be created by CyberArk

** Note: CyberArk creates the Key Pair and stores it in the Vault. The Key Pair is never downloaded to users' endpoints.
 
Public NAT GW CIDR* The IPv4 range of addresses for the NAT GW public subnet 
Private NAT GW CIDR* The IPv4 range of addresses for the NAT GW private subnet  
Internet GW ID * The ID of the internet GW that exist in the VPC 


*These fields only exist in the Elasticity v0.1.1 - With NAT.json template 


Solution Upgrade Procedure 
1.Replace the solution files in the bucket 
2.Update the CloudFormation stack with the new template



Limitations
1.CyberArk currently supports onboarding for the following AWS accounts:•SSH keys on: •AWS Linux, RHL AMIs: ec2-user
•Ubuntu: ubuntu user
•Centos: centos user
•openSuse: root user
•Debian: admin user
•Fedora: fedora user

•Windows devices 
•Amazon AMI/custom AMI with a key that was created by the solution or uploaded in advance to the Safe in the Vault supplied in the solution deployment (not supplied hard coded by Amazon).

2.Existing AWS instances (pre-installed) are not onboarded automatically.
3.EC2 instance public IPs must be elastic IPs to allow continous access and management after changing the instance state.
4.This solution currently handles a maximum of 100 events in 4 seconds.

5.in order for the CPM to manage new Windows instances for some versions (you can find the list below), the user must run the following command manually on all new Windows instances:
•netsh firewall set service RemoteAdmin enable.

If this command is not run, the CPM will fail to rotate the password.

List of Windows instances that require this command to be run manually:
•Microsoft Windows Server 2016 Base
•Microsoft Windows Server 2016 Base with Containers
•Microsoft Windows Server 2016 with SQL Server 2017 Express
•Microsoft Windows Server 2016 with SQL Server 2017 Web 

•Microsoft Windows Server 2016 with SQL Server 2017 Standard

•Microsoft Windows Server 2016 with SQL Server 2017 Enterprise

•Microsoft Windows Server 2016 with SQL Server 2016 Express

•Microsoft Windows Server 2016 with SQL Server 2016 Web 
•Microsoft Windows Server 2016 with SQL Server 2016 Standard
•Microsoft Windows Server 2016 with SQL Server 2016 Enterprise




Debugging

All information about debugging is available through AWS CloudWatch

Contributing

Feel free to open pull requests with additional features or improvements!
1.Fork it
2.Create your feature branch (git checkout -b my-new-feature)
3.Commit your changes (git commit -am 'Added some feature')
4.Push to the branch (git push origin my-new-feature)
5.Create a new Pull Request




Licensing

Copyright 2016-2018 CyberArk

Licensed under the Apache License, Version 2.0 (the "License"); you may not use this software except in compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.

Security Recommendation
1.The solution creates the following two Dynamo DB tables :  Instances , Sessions 
Manipulation of these tables can affects the security of the solution .
Cyberark reccomends that only selected trusted users should have access and update permissions to these tables .




Deleting the solution 

There is a known issue with auto-deleting the network interface of a Lambda deployed in an existing VPC 

Therefore, follow these steps when deleting the stack: 

1 . Wait for the following status event in the cloud formation log:



2 . Go to: EC2 → Network Interfaces

3 . Choose the network interface of your stack and then perform Detach and Delete 




Troubleshooting Tools 
1.All Instance on boarding status is saved in a DynamoDB table that is located under :
DynamoDB→ Tables → Instances   , Go to the Items tab
2.All solution logs are written to CloudWatch , available under :
CloudWatch → Logs , Search for your cloud formation stack name 
