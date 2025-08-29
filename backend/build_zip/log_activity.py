import json
import logging
from datetime import datetime
from pymongo import MongoClient
import uuid

import os
import json
from datetime import datetime
from pymongo import MongoClient
import uuid
from common.logger import get_logger, with_logging

logger = get_logger(__name__)
def validate_activity(data):
    required_fields = ['user_id', 'timestamp', 'activity_type', 'title']
    for field in required_fields:
        if field not in data or not data[field]:
            return False, f"Missing or empty field: {field}"
    return True, ""

def get_db():
    uri = os.environ.get('DOCDB_URI')
    username = os.environ.get('DOCDB_USER')
    password = os.environ.get('DOCDB_PASS')
    if not uri or not username or not password:
        raise Exception("Missing DocumentDB environment variables")
    client = MongoClient(
        uri,
        username=username,
        password=password,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=5000
    )
    return client['moodmark']


@with_logging()
def lambda_handler(event, context):
    try:
        db = get_db()
        activities = db['activities']
        users = db['users']

        body = event.get('body')
        if isinstance(body, str):
            data = json.loads(body)
        else:
            data = body

        valid, msg = validate_activity(data)
        if not valid:
            logger.warning(f"Validation failed: {msg}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": msg})
            }

        user_id = str(data['user_id'])
        user_doc = users.find_one({'userId': user_id})
        if not user_doc:
            logger.warning(f"User not found: {user_id}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "User does not exist."})
            }

        activity_log = {
            "activityId": str(uuid.uuid4()),
            "userId": user_id,
            "activityType": str(data['activity_type']),
            "title": str(data['title']),
            "description": str(data.get('description', '')),
            "bookmark": data.get('bookmark'),
            "timestamp": str(data['timestamp']),
            "lastUpdated": datetime.utcnow().isoformat()
        }

        activities.insert_one(activity_log)
        logger.info(f"Activity logged for user: {user_id}")
        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Activity logged", "activityId": activity_log["activityId"]})
        }

    except (ValueError, json.JSONDecodeError):
        logger.error("Invalid JSON input.")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Invalid JSON input."})
        }

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error."})
        }
