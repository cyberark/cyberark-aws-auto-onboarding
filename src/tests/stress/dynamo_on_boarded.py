# return how much 'on boarded' items there in dynamodb 'Instances' table
import boto3

client = boto3.client('dynamodb', region_name='eu-west-2')

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
