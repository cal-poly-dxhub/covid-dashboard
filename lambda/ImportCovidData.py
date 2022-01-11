import json
import boto3
import logging
import datetime
import db_config
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info('event: {}'.format(event))

    retval = {
        "isBase64Encoded": 'false',
        "statusCode": '200',
        "headers": {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "PUT,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,Date,X-Amzn-Trace-Id,x-amz-apigw-id,x-amzn-RequestId",
        },
        
    }
    
    try:
        action = event['resource'].split("/")[1]
        logger.info("action: {0}".format(action))
    except:
        return error_response(retval, {"message": "resource could not be determined."}, 400)
    
    try:
        input_data = json.loads(event['body'])
        logger.info("input data: {}".format(input_data))
    except:
        return error_response(retval, {"message": "invalid request body"}, 400)
    
    if action == "room":
        room_table = dynamodb.Table('iso_room')
        '''
            input data is expected to be of the form:
                {
                    "key": ~,
                    "ticketStatus": ~,
                    "roomStatus": ~,
                    ...
                }
        '''
        input_data['ticketDateTimeUTC'] = str(datetime.datetime.utcnow())
        try:
            response = room_table.put_item(
                Item=input_data,
                ReturnValues="ALL_OLD"
            )
        except:
            return error_response(retval, {"message": "unable to insert data for `room`."}, 500)
        
        logger.info("dynamodb `iso_room` PUT_ITEM response: {}".format(response))
        retval['body'] = json.dumps(response)
        
    elif action == "case":
        case_table = dynamodb.Table('cases')
        '''
            input data is expected to be of the form:
                {
                    "key": ~,
                    "onCampusResident": ~,
                    "passType": ~,
                    "reasonForHold": ~,
                    "housingLocation": ~,
                    "closeOutReason": ~,
                    ...
                }
        '''
        input_data['caseDateTimeUTC'] = str(datetime.datetime.utcnow())
        
        try:
            response = case_table.put_item(
                Item=input_data,
                ReturnValues="ALL_OLD"
            )
        except:
            return error_response(retval, {"message": "unable to insert data for `case`."}, 500)
        
        logger.info("dynamodb `cases` PUT_ITEM response: {}".format(response))
        retval['body'] = json.dumps(response)
    
    elif action == "tests":
        test_table = boto3.client('rds-data')
        insert_test_stmt =  """
                                INSERT INTO Tests(Result, Test_Date, Result_Date, Source, Reason, Type, ON_CAMPUS_RESIDENT_FLAG, ResponseId, GUID)
                                VALUES(:result, :test_date, :result_date, :source, :reason, :type, :on_campus_resident_flag, :response_id, :guid)
                            """
        params= [
                    { "name": "result", "value": format_param_value(input_data.get("ED_TD_Result")) },
                    { "name": "test_date", "value": format_param_value(input_data.get("ED_TD_Test_Date")) },
                    { "name": "source", "value": format_param_value(input_data.get("ED_TD_Source")) },
                    { "name": "reason", "value": format_param_value(input_data.get("ED_TD_Reason")) },
                    { "name": "type", "value": format_param_value(input_data.get("ED_TYPE")) },
                    { "name": "on_campus_resident_flag", "value": format_param_value(input_data.get("ON_CAMPUS_RESIDENT_FLAG")) },
                    { "name": "response_id", "value": format_param_value(input_data.get("ResponseId")) },
                    { "name": "result_date", "value": format_param_value(input_data.get("ED_TD_Result_Date")) },
                    { "name": "guid", "value": format_param_value(input_data.get("GUID")) }
        ]
        
        try:
            response = test_table.execute_statement(
                resourceArn = db_config.RESOURCE_ARN,
                secretArn = db_config.SECRET_ARN,
                database = db_config.DB,
                sql = insert_test_stmt,
                parameters = params,
                includeResultMetadata = True
            )
        except:
            return error_response(retval, {"message": "unable to insert data for `tests`."}, 500)
        logger.info("amazon aurora `test_data` EXECUTE_STATEMENT response: {}".format(response))
        retval['body'] = json.dumps(response)

    elif action == "compliance":
        compliance_table = dynamodb.Table('compliance')
        '''
            input data is expected to be of the form:
                {
                    "date": ~, (YYYY-MM-DD)
                    "totalRequired": ~,
                    "testedInLast3Days": ~,
                    "testedInLast6Days": ~,
                    ...
                }
        '''

        if type(input_data) != list:
            return error_response(retval, {"message": "request body must be an array of 'compliance' objects"}, 400)
        
        response = []
        for obj in input_data:
            obj['complianceDateTimeUTC'] = str(datetime.datetime.utcnow())
            try:
                result = compliance_table.put_item(
                    Item=obj,
                    ReturnValues="ALL_OLD"
                )
            except:
                logger.error("unable to insert into `compliance` table:\n{}".format(obj))
                result = {"message": "error", "value": obj}
            finally:
                response.append(result)
        
        logger.info("dynamodb `compliance` PUT_ITEM response: {}".format(response))
        retval['body'] = json.dumps(response, default=json_default)

    return retval

def json_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)

def error_response(retval, body, statusCode):
    logger.error("status code - {0}: {1}".format(statusCode, body))
    
    retval['statusCode'] = str(statusCode)
    retval['body'] = json.dumps(body)
    return retval

#formats params on calls to `table.execute_statement(...)` as per aws boto3 doc specification: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/rds-data.html
def format_param_value(param):
    if type(param) == int:
        return {"longValue": param}
    elif type(param) == float:
        return {"doubleValue": param}
    elif type(param) == str:
        return {"stringValue": param}
    elif type(param) == bool:
        return {"booleanValue": param}
    elif param == None:
        return {"isNull": True}
    else:
        raise ValueError("Unrecognized parameter type")