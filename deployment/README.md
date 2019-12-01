# PAS-Orchestrator

In today’s modern infrastructure, organizations are moving towards hybrid environments, which consist of multiple public clouds, private clouds and on-premises platforms.

CyberArk has created a tailored installation and deployment method for each platform to enable easy implementation. For example, CloudFormation templates enable easy deployment on AWS, while Azure Resource Manager (ARM) templates enable easy deployment on Azure. However, it is difficult to combine the different methods to orchestrate and automate a hybrid deployment.

PAS Orchestrator is a set of Ansible roles which provides a holistic solution to deploying CyberArk Core PAS components simultaneously in multiple environments, regardless of the environment’s location.

The Ansible roles are responsible for the entire deployment process, and can be integrated with the organization’s CI/CD pipeline.

Each PAS component’s Ansible role is responsible for the component end-2-end deployment, which includes the following stages for each component:
- Copy the installation package to the target server
- Installing prerequisites
 - Silent installation of the component
- Post installation procedure and hardening
- Registration in the Vault

Ansible Roles for PVWA, CPM and PSM can be found in the following links:
 - PSM: [https://github.com/cyberark/psm](https://github.com/cyberark/psm)
 - CPM: [https://github.com/cyberark/cpm](https://github.com/cyberark/cpm)
 - PVWA: [https://github.com/cyberark/pvwa](https://github.com/cyberark/pvwa)

The PAS Orchestrator role is an example of how to use the component roles
demonstrating paralel installation on multiple remote servers

## Requirements

- IP addresses / hosts to execute the playbook against with Windows 2016 installed on the remote hosts
- WinRM open on port 5986 (**not 5985**) on the remote host
- Pywinrm is installed on the workstation running the playbook
- The workstation running the playbook must have network connectivity to the remote host
- The remote host must have Network connectivity to the CyberArk vault and the repository server
  - 443 port outbound
  - 443 port outbound (for PVWA only)
  - 1858 port outbound
- Administrator access to the remote host
- CyberArk components CD image on the workstation running the playbook

## Environment setup

- Get the PAS Orchestrator Playbook
    ```
    git clone https://github.com/cyberark/pas-orchestrator.git
    cd pas-orchestrator
    ```
- Install Python requirements
    ```
    pip install -r requirements.txt
    ```
- Get the components roles
    ```
    ansible-galaxy install --roles-path ./roles --role-file requirements.yml
    ```
- Update the inventories hosts file with the remote hosts IPs

## Role Variables

These are the variables used in this playbook

**Deployment Variables**

| Variable                         | Required     | Default                                                                        | Comments                                 |
|----------------------------------|--------------|--------------------------------------------------------------------------------|------------------------------------------|
| vault_ip                         | yes          | None                                                                           | Vault ip to perform registration         |
| dr_vault_ip                      | no           | None                                                                           | vault dr ip to perform registration      |
| vault_port                       | no           | 1858                                                                           | vault port                               |
| vault_username                   | no           | "administrator"                                                                | vault username to perform registration   |
| vault_password                   | yes          | None                                                                           | vault password to perform registration   |
| accept_eula                      | yes          | "No"                                                                           | Accepting EULA condition                 |
| cpm_zip_file_path                | yes          | None                                                                           | Path to zipped CPM image                 |
| pvwa_zip_file_path               | yes          | None                                                                           | Path to zipped PVWA image                |
| psm_zip_file_path                | yes          | None                                                                           | Path to zipped PSM image                 |

Variables related to the components can be found on the Components README

## Usage

The Role consists of two parts, each part runs independently:

**Part 1 - Components Deployment**

The task will trigger the components main roles, each role will trigger it's sub tasks (prerequisities/installation, etc.)
by default, all tasks are set to true except registration.
This process executes tasks on all hosts in parallel, reducing deployment time

*IMPORTANT: Component Registration should be always set to false in this phase

**Part 2 - Components Registration**

This task will execute the registration process of the components, all the previous tasks are set to false and only registration is enabled
This process executes the registration of each component in serial

## Inventory

Prior to running pas-orchestrator hosts file should be "updated" [https://github.com/cyberark/pas-orchestrator/blob/master/inventories/production/hosts] with relevant hosts data.

    # file: production
    # TODO: Add description how to add hosts

    [pvwa]
    # Add here list of hosts or ip adresses of pvwa dedicated machines
    # pvwa01.example.com
    # pvwa02.example.com
    10.2.0.155


    [cpm]
    # Add here list of hosts or ip adresses of cpm dedicated machines
    # cpm01.example.com
    # cpm02.example.com
    10.2.0.155


    [psm]
    # Add here list of hosts or ip adresses of psm dedicated machines
    # psm01.example.com
    # psm02.example.com
    10.2.0.155


    [psmp]
    # Add here list of hosts or ip adresses of psmp dedicated machines
    # psmp01.example.com
    # psmp02.example.com


    # DO NOT EDIT BELOW!!!
    [windows:children]
    pvwa
    cpm
    psm

## Running the  playbook:

 To run the above playbook, execute the following command example :

    ansible-playbook -i ./inventories/production pas-orchestrator.yml -e "vault_ip=VAULT_IP ansible_user=DOMAIN\USER cpm_zip_file_path=/tmp/pas_packages/cpm.zip pvwa_zip_file_path=/tmp/pas_packages/pvwa.zip psm_zip_file_path=/tmp/pas_packages/psm.zip  connect_with_rdp=Yes accept_eula=Yes"

Command example for out of Domain , no hardening deployment in drive D:

    ansible-playbook -i ./inventories/production pas-orchestrator.yml -e "vault_ip=VAULT_IP ansible_user=DOMAIN\USER cpm_zip_file_path=/tmp/pas_packages/cpm.zip pvwa_zip_file_path=/tmp/pas_packages/pvwa.zip psm_zip_file_path=/tmp/pas_packages/psm.zip {psm_out_of_domain:true} connect_with_rdp=Yes accept_eula=Yes psm_installation_drive=D: cpm_installation_drive=D: pvwa_installation_drive=D: {psm_hardening:false} {cpm_hardening:false} {pvwa_hardening:false}"

 ** *Vault and remote host passwords are entered via Prompt*

## Troubleshooting

In case of a failure, a Log folder with be created on the Ansible workstation with the relevant logs copied from the remote host machine.
The logs are available under  - pas-orchestrator/tasks/logs

## Idempotence
Every stage in the roles contains validation and can be run multiple times without error.

## Limitations
- Only single component per server is supported
- There is a check sum verification to the CD image zip file , it must be the original CyberArk release

## License

Apache License, Version 2.0
