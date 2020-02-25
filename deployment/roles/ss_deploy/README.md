
cf_deploy
=========
This role deploys cloudformation to aws

Role Tasks
--------------
- **main** - Deploys the cloudformation

Role Variables
--------------

### General variables

- **deploy_bucket** - The S3 bucket used to upload the cloudformation before deploying
- **cf_template_url** - The URL to fetch the cloudformation before uploading it to the deployment bucket
- **cf_template_parameters** - The parameters passed to the cloudformation
- **aws_region** - The AWS Region that the cloudformation is going to be deployed to

Outputs
------------
- **cf_output** - The JSON output with all the cloudformation stack resources

Dependencies
------------


Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

	- hosts: localhost
	  connection: local
	  gather_facts: no
	  tasks:	  
        - include_role:
            name: cf_deploy
          vars:
			- bucket: mybucket
            - cf_template_url: https://raw.githubusercontent.com/organization/repository/cloudformation.template
            - cf_template_parameters:
                Parameter1: Value1
                Parameter2: Value2
            - aws_region: us-east-1

Todo
-------


License
-------

BSD

Author Information
------------------

Avishay Bar,
Cloud Initiatives team,
CyberArk 2018
