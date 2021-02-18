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

    recent_stats = generate_available_stats(historical=False)
    historical_stats = generate_available_stats(historical=True)

    try:
        KEY = "stats-test.json" if lambda_version == "$LATEST" else "stats.json"
        post_stats(KEY, recent_stats)

        KEY = "stats-history-test.json" if lambda_version == "$LATEST" else "stats-history.json"
        post_stats(KEY, historical_stats)
    except:
        logger.error("Could not post statistics to s3")
    finally:
        return {}


def post_stats(key, stats):
    stat_data = json.dumps(stats).encode('utf-8')

    response = s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=stat_data
        )
    logger.info("s3 put_object response: {}".format(response))
    return response