import json
import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*"
}

# DocumentDB connection details
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'moodmark')
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'activities')

def lambda_handler(event, context):
    try:
        print("Lambda handler invoked for /activity-log endpoint")
        user_id = event.get('queryStringParameters', {}).get('user_id')
        if not user_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Missing 'user_id' in query parameters."})
            }

        # Connect to DocumentDB
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # Fetch activities for the user
        activities_cursor = collection.find({"userId": user_id})
        activities = []
        for activity in activities_cursor:
            activity.pop('_id', None)  # Remove MongoDB internal ID
            activities.append(activity)

        if not activities:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"message": "No activity logs found for user."})
            }

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps({"activities": activities})
        }

    except PyMongoError as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Database access error.", "details": str(e)})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Internal server error.", "details": str(e)})
        }
