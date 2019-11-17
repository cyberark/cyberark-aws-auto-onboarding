import urllib3
import pvwa_integration
import aws_services
import instance_processing
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def lambda_handler(event, context):

    print (event)

    try:
        message = event["Records"][0]["Sns"]["Message"]
        data = json.loads(message)
    except Exception as e:
        print ("Error on retrieving Message Data from Event Message. Error: {0}".format(e))

    try:
        instance_arn = data["resources"][0]
    except Exception as e:
        print ("Error on retrieving instance_arn from Event Message. Error: {0}".format(e))

    try:
        instanceId = data["detail"]["instance-id"]
    except Exception as e:
        print ("Error on retrieving Instance Id from Event Message. Error: {0}".format(e))

    try:
        actionType = data["detail"]["state"]
    except Exception as e:
        print ("Error on retrieving Action Type from Event Message. Error: {0}".format(e))


    try:
        eventAccountId = data["account"]
    except Exception as e:
        print ("Error on retrieving Event Account Id from Event Message. Error: {0}".format(e))


    try:
        eventRegion = data["region"]
    except Exception as e:
        print ("Error on retrieving Event Region from Event Message. Error: {0}".format(e))


    logName = context.log_stream_name if context.log_stream_name else "None"

    try:
        instanceDetails = aws_services.get_ec2_details(instanceId, context, eventRegion, eventAccountId)

        instanceData = aws_services.get_instance_data_from_dynamo_table(instanceId)
        if actionType == 'terminated':
            if not instanceData:
                print('Item {0} does not exists on DB'.format(instanceId))
                return None
            else:
                instanceStatus = instanceData["Status"]["S"]
                if instanceStatus == OnBoardStatus.OnBoarded_Failed:
                    print("Item {0} is in status OnBoard failed, removing from DynamoDB table".format(instanceId))
                    aws_services.remove_instance_from_dynamo_table(instanceId)
                    return None
        elif actionType == 'running':
            if not instanceDetails["address"]:  # In case querying AWS return empty address
                print("Retrieving Instance address from AWS failed.")
                return None
            if instanceData:
                instanceStatus = instanceData["Status"]["S"]
                if instanceStatus == OnBoardStatus.OnBoarded:
                    print('Item: {0}, exists on DB, no need to add it to vault'.format(instanceId))
                    return None
                elif instanceStatus == OnBoardStatus.OnBoarded_Failed:
                    print("Item {0} exists with status 'OnBoard failed', adding to vault".format(instanceId))
                else:
                    print('Item {0} does not exists on DB, adding to vault'.format(instanceId))
        else:
            print('Unknown instance state')
            return

        storeParametersClass = aws_services.get_params_from_param_store()
        if not storeParametersClass:
            return
        pvwaConnectionnumber, sessionGuid = aws_services.get_available_session_from_dynamo()
        if not pvwaConnectionnumber:
            return
        sessionToken = pvwa_integration.logon_pvwa(storeParametersClass.vaultUsername,
                                                   storeParametersClass.vaultPassword,
                                                   storeParametersClass.pvwaURL, pvwaConnectionnumber)
        if not sessionToken:
            return
        if actionType == 'terminated':
            instance_processing.delete_instance(instanceId, sessionToken, storeParametersClass, instanceData, instanceDetails)
        elif actionType == 'running':
            instance_processing.create_instance(instanceId, sessionToken, instanceDetails, storeParametersClass, logName, eventRegion)
        else:
            print('Unknown instance state')
            return

        pvwa_integration.logoff_pvwa(storeParametersClass.pvwaURL, sessionToken)
        aws_services.release_session_on_dynamo(pvwaConnectionnumber, sessionGuid)

    except Exception as e:
        print("Unknown error occurred:{0}".format(e))
        if actionType == 'terminated':
            # put_instance_to_dynamo_table(instanceId, instanceDetails["address"]\
            # , OnBoardStatus.Delete_Failed, str(e), logName)
            aws_services.update_instances_table_status(instanceId, OnBoardStatus.Delete_Failed, str(e))
        elif actionType == 'running':
            aws_services.put_instance_to_dynamo_table(instanceId, instanceDetails["address"], OnBoardStatus.OnBoarded_Failed, str(e),
                                         logName)
        # TODO: Retry mechanism?
        aws_services.release_session_on_dynamo(pvwaConnectionnumber, sessionGuid)
        return


class OnBoardStatus:
    OnBoarded = "on boarded"
    OnBoarded_Failed = "on board failed"
    Delete_Failed = "delete failed"
