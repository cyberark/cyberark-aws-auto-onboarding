# Deployment scripts

## Introduction

```
.
├── build             # Build the lambda sources as ZIP files (using Docker)
├── configure         # Create a parameters.json file used to deploy the project
├── delete            # Delete the stack and stack-set from AWS
├── deploy            # Deploy the stack and stack-set
├── docker            # Docker files used to build the zip files (see ./build) 
├── sync              # Sync the lambdas source code on S3
└── utils             # Library of useful functions
```

## Prerequisites
 - Docker
 - Bash
 - AWS cli (logged in)

## Usage

Run the scripts in the following order:
```
# Build an image named aws_onboarding_lambda_builder and run it.
$ bin/build

# Zip sources should now be in dist/lambdas. Sync them to the S3 buckets
$ bin/sync

# Configure the stack parameters. A parameters.json file will be generated.
$ bin/configure

# Deploy the required stack and stack-set on AWS
$ bin/deploy

# Optional: Delete the stack and stack-set
$ bin/delete
```
