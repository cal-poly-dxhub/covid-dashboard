import logging
import db_config
import boto3

RESOURCE = db_config.RESOURCE_ARN
SECRET = db_config.SECRET_ARN
DB = db_config.DB

logger = logging.getLogger()
logger.setLevel(logging.INFO)


'''
formats the response of a call to execute_statement as a list of dictionary objects
REQUIRED:
- The call to table.execute_statement(...) must contain the parameter `includeResultMetadata=True`.
  This allows for labeled columns to be correctly identified as the keys within each dictionary.
'''
def generate_map_from_response(response):
    response_set = []
    obj = {}
    for record in response['records']:
        for i in range(len(record)):
            obj[response['columnMetadata'][i]['label']] = list(record[i].values())[0]
        response_set.append(obj.copy())
    return response_set


# Substitute to `generate_map_from_response` for data order by a date object (key).
# Instead of data in this form:
# {
#   "Test_Date": '2021-01-01',
#   "X": 1,
#   "Y": 0, ...
# },
# {
#   "Test_Date": '2021-01-03',
#   "X": 13,
#   "Y": 4, ...
# }
# We have data in the form:
# {
#   "X": {"2021-01-01": 1, "2021-01-03": 13},
#   "Y": {"2021-01-01": 0, "2021-01-03": 4}, ...
# }
def generate_daily_map_from_response(key, response):
    col_names = []
    key_index = None
    result = {}

    #sets the keys of the response object
    col_names = [column['label'] for column in response['columnMetadata']]
    for i in range(len(col_names)):
        if  col_names[i] != key:
            result[col_names[i]] = {}
        else:
            key_index = i

    for record in response['records']:
        for i in range(len(col_names)):
            if i != key_index:
                date = list(record[key_index].values())[0]
                val = list(record[i].values())[0]
                
                result[col_names[i]][date] = val
    return result


#requirements:
# - dates consists of a list of dates that is a complete range without gaps
def get_rolling_average(dates, day_range, positives, totals):
    rolling_avg = []

    for i in range(len(dates)):
        #gurantee length of below list slices is at most day_range
        j = i if i < day_range else day_range - 1
        
        positive = sum(positives[i - j : i + 1])
        total = sum(totals[i - j : i + 1])
        
        rolling_percent = positive  / total if total != 0 else 0
        rolling_avg.append(round(rolling_percent, 4))
    return rolling_avg


def get_response(sql_stmt):
    test_table = boto3.client('rds-data')

    response = test_table.execute_statement(
        resourceArn = RESOURCE,
        secretArn = SECRET,
        database = DB,
        sql = sql_stmt,
        includeResultMetadata=True
    )
    return response


def get_table_items(table):
    dynamodb = boto3.resource('dynamodb')
    dynamo_table = dynamodb.Table(table)

    response = dynamo_table.scan()
    items = response['Items']

    return items