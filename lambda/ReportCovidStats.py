import os
import json
import boto3
import utility
from covid_stats import generate_available_stats

s3 = boto3.client('s3')

lambda_version = os.environ.get('AWS_LAMBDA_FUNCTION_VERSION')
logger = utility.logger

BUCKET = "coviddashboard.calpoly.io"

def lambda_handler(event, context):
    logger.info('event: {}'.format(event))
    body = json.loads(event)
    show_history = body.get('historical')

    #post test version if the lambda function being invoked is not a published version
    KEY = "stats.json" if lambda_version != "$LATEST" else "stats-history.json" if show_history else "stats-test.json"

    statistics = generate_available_stats(show_history)

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