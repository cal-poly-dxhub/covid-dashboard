import os
import json
import boto3
import utility
from covid_stats import generate_available_stats

s3 = boto3.client('s3')

lambda_version = os.environ.get('AWS_LAMBDA_FUNCTION_VERSION')
logger = utility.logger

BUCKET = "coviddashboard.calpoly.io"

#post test version if the lambda function being invoked is not a published version
KEY = "stats-test.json" if lambda_version == "$LATEST" else "stats.json"

def lambda_handler(event, context):
    logger.info('event: {}'.format(event))

    statistics = generate_available_stats()

    stat_data = json.dumps(statistics).encode('utf-8')

    try:
        response = s3.put_object(
            Bucket=BUCKET,
            Key=KEY,
            Body=stat_data
        )
        logger.info("s3 put_object response: {}".format(response))
    except:
        logger.error("Could not post statistics to s3")
    finally:
        return {}