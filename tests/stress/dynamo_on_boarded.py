# return how much 'on boarded' items there in dynamodb 'Instances' table
import argparse
import boto3

parser = argparse.ArgumentParser()
parser.add_argument("main_region", help="AOB main region")
args = parser.parse_args()

client = boto3.client('dynamodb', region_name=args.main_region)

response = client.scan(
    TableName='Instances',
    ScanFilter={
        "Status": {
            'AttributeValueList': [
                {
                    "S": "on boarded"
                }
            ],
            'ComparisonOperator': 'EQ'
        }
    })

print(response['Count'])
