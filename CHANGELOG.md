# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)

## [0.4.0] - 2022-05-17
### Added
- Added the ability to set what tags should be looked to set Platform, Safe, and Username
- Added error handleing when proper EC2 tags are not set to output error with better description of the issue

### Changed
- Updated logging to decrease output of logs when set to "Info" to only include necessary information and errors
- Added "debug" logging setting and moved most "info" logs to "debug"
- Added and updated logging for troubleshooting purposes
- Updated CloudFormation Template to support code changes
- Suppressed warning about "InsecureRequestWarning" in logs

## [0.3.0] - 2022-05-05
### Added
- Added the ability to set Platform, Safe, and Username via EC2 Instance Tags; AOBPlatform, AOBSafe, AOBUsername

### Changed
- Fixed calls to PVWA to use v2 interface
- Updated delete account command to account for more failures by updating address to show terminated and disabling password management
- Updated Readme

## [0.2.0] - 2020-7-7
### Added
- Log mechanism
- POC mode (support no ssl for non production environments)

## [0.1.2] - 2019-10-23

### Changed
- Update PVWA API Calls to support version 10.6 and up

## [0.1.1] - 2018-02-21

### Added
- Automatic on-board local administrator account for new Windows instances.
- CloudFormation with automatic deployment and configuration of NAT Gateway.

### Changed
- Automatically add network access for the solution in the PVWA security group level
- CloudFormation automatically attache CloudWatch to Lambda

## [0.1.0] - 2017-12-29
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
