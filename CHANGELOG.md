# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)



## [1.0] - 2017-12-29


The first tagged version.

### Added
- CloudFormation template to deploy the solution on AWS
- Automatic onboard privileged accounts SSH keys for new instances.
- Supported users and OS flavor:
	- ec2-user for AWS Linux and RHEL AMIs
	- ubuntu user for Ubuntu
	- centos user for Centos
	- root user for openSusue
	- admin user for Debian
	- fedora user for Fedora
- Creation of Key Pair and secure store it by CyberArk Vault



[1.0]: https://github.com/cyberark/cyberark-aws-auto-onboarding