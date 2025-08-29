
import os
import json
import logging
import time
from datetime import datetime, timedelta
from pymongo import MongoClient
import boto3

# --- Helpers ---
_mongo_client = None
def get_db():
    global _mongo_client
    if _mongo_client is None:
        uri = os.environ['DOCDB_URI']
        user = os.environ['DOCDB_USER']
        pw = os.environ['DOCDB_PASS']
        db_name = os.environ.get('DB_NAME', 'moodmark')
        _mongo_client = MongoClient(
            uri,
            username=user,
            password=pw,
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=5000
        )
    return _mongo_client[os.environ.get('DB_NAME', 'moodmark')]

def get_time_of_day(now):
    hour = now.hour
    if 5 <= hour < 12:
        return 'morning'
    elif 12 <= hour < 17:
        return 'afternoon'
    elif 17 <= hour < 22:
        return 'evening'
    else:
        return 'late-night'

def build_prompt(history, now, weather):
    bullets = []
    for act in history:
        mood = int(act.get('mood', 5))
        ts = act.get('timestamp', '')
        title = act.get('title', act.get('activity_type', ''))
        desc = act.get('description', '')
        bullets.append(f"- {title} ({desc}) [{mood}/10, {ts}]")
    prompt = f"Recent activities:\n" + "\n".join(bullets)
    prompt += f"\nTime of day: {get_time_of_day(now)}\nWeather: {weather}\nSuggest a new hobby in strict JSON:"
    return prompt

def call_bedrock_claude(prompt):
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3.5-sonnet-20240620-v1:0')
    region = os.environ.get('AWS_REGION', os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
    client = boto3.client('bedrock-runtime', region_name=region)
    system_instruction = (
        "You are an assistant that always responds in strict JSON with this schema: "
        "{ 'suggestion': string, 'alternatives': [string], 'reasoning': string, 'source': 'ai', 'metrics': { 'db_ms': int, 'llm_ms': int, 'items': int }, 'applied': { 'userId': string, 'filters': { 'avoidRecentDays': 3, 'historyWindowDays': 30 } } }"
        "Do not include any prose or explanation outside the JSON."
    )
    body = {
        "modelId": model_id,
        "contentType": "application/json",
        "accept": "application/json",
        "body": json.dumps({
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        })
    }
    start = time.time()
    response = client.invoke_model(
        modelId=model_id,
        body=body['body'],
        contentType="application/json",
        accept="application/json"
    )
    llm_ms = int((time.time() - start) * 1000)
    result = response['body'].read().decode('utf-8')
    try:
        parsed = json.loads(result)
        # Validate keys
        for k in ["suggestion", "alternatives", "reasoning", "source", "metrics", "applied"]:
            if k not in parsed:
                raise ValueError(f"Missing key: {k}")
        return parsed, llm_ms
    except Exception:
        raise ValueError("Invalid LLM response")

def rule_based_suggestion(history, now):
    # Exclude last 3 days
    cutoff = now - timedelta(days=3)
    filtered = [a for a in history if datetime.fromisoformat(a['timestamp']) < cutoff]
    # Score by mood
    scored = sorted(filtered, key=lambda a: int(a.get('mood', 5)), reverse=True)
    suggestion = scored[0]['title'] if scored else "Try something new!"
    alternatives = [a['title'] for a in scored[1:3]] if len(scored) > 2 else ["Read a book", "Go for a walk"]
    reasoning = "Based on your past activities and mood scores."
    return {
        "suggestion": suggestion,
        "alternatives": alternatives,
        "reasoning": reasoning,
        "source": "rule",
        "metrics": {},
        "applied": {}
    }

def lambda_handler(event, context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,x-api-key",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Content-Type": "application/json"
    }
    if event.get('httpMethod', '') == 'OPTIONS':
        return {"statusCode": 200, "headers": headers, "body": json.dumps({})}
    try:
        params = event.get('queryStringParameters') or {}
        user_id = params.get('userId')
        if not user_id:
            return {"statusCode": 400, "headers": headers, "body": json.dumps({"error": "Missing userId"})}
        time_of_day = params.get('timeOfDay')
        weather = params.get('weather', 'clear')
        now = datetime.utcnow()
        if not time_of_day:
            time_of_day = get_time_of_day(now)
        db_start = time.time()
        db = get_db()
        coll = db[os.environ.get('COLL_ACTIVITIES', 'activities')]
        thirty_days_ago = now - timedelta(days=30)
        items = list(coll.find({
            "userId": user_id,
            "timestamp": {"$gte": thirty_days_ago.isoformat()}
        }).sort("timestamp", -1).limit(60))
        db_ms = int((time.time() - db_start) * 1000)
        # Exclude last 3 days
        cutoff = now - timedelta(days=3)
        history = [
            {
                "title": i.get("title", i.get("activity_type", "")),
                "description": i.get("description", ""),
                "mood": int(i.get("mood", 5)),
                "timestamp": i.get("timestamp", "")
            }
            for i in items if datetime.fromisoformat(i.get("timestamp", thirty_days_ago.isoformat())) < cutoff
        ]
        metrics = {"db_ms": db_ms, "llm_ms": 0, "items": len(history)}
        applied = {"userId": user_id, "filters": {"avoidRecentDays": 3, "historyWindowDays": 30}}
        prompt = build_prompt(history, now, weather)
        try:
            result, llm_ms = call_bedrock_claude(prompt)
            result["metrics"]["db_ms"] = db_ms
            result["metrics"]["llm_ms"] = llm_ms
            result["metrics"]["items"] = len(history)
            result["applied"] = applied
            return {"statusCode": 200, "headers": headers, "body": json.dumps(result)}
        except Exception as e:
            logger.exception("Bedrock/LLM error, using fallback.")
            fallback = rule_based_suggestion(history, now)
            fallback["metrics"] = metrics
            fallback["applied"] = applied
            return {"statusCode": 200, "headers": headers, "body": json.dumps(fallback)}
    except Exception as e:
        logger.exception("Internal error.")
        return {"statusCode": 500, "headers": headers, "body": json.dumps({"error": str(e)})}
