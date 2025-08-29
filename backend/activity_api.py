import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple

import boto3
from pymongo import MongoClient, DESCENDING

import os
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Tuple
import boto3
from pymongo import MongoClient, DESCENDING
from common.logger import get_logger, with_logging

logger = get_logger(__name__)
# -----------------------------
# DB (DocDB requires TLS; dev-safe: skip CA verification)
# -----------------------------
def get_db():
    """
    Env:
      DOCDB_URI  (e.g., mongodb://host:27017/?replicaSet=rs0&readPreference=secondaryPreferred&retryWrites=false)
      DOCDB_USER
      DOCDB_PASS
    """
    uri = os.environ.get('DOCDB_URI')
    username = os.environ.get('DOCDB_USER')
    password = os.environ.get('DOCDB_PASS')
    if not uri or not username or not password:
        raise Exception("Missing DocumentDB environment variables")
    client = MongoClient(
        uri,
        username=username,
        password=password,
        tls=True,                         # DocDB needs TLS
        tlsAllowInvalidCertificates=True, # DEV ONLY (do NOT use in prod)
        serverSelectionTimeoutMS=5000,
    )
    return client['moodmark']


def _resp(status: int, body_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body_dict),
    }


# -----------------------------
# Bedrock + HTTP helpers
# -----------------------------
# Prefer a custom override; otherwise use Lambda-provided region.
BEDROCK_REGION = (
    os.getenv("BEDROCK_REGION")
    or os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
    or "eu-west-2"
)
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

def _extract_http_meta(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """Support API Gateway REST (v1) and HTTP API (v2)."""
    method = (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method")
        or ""
    ).upper()
    path = event.get("path") or event.get("rawPath") or ""
    qs = event.get("queryStringParameters") or {}
    return method, path, qs


def _build_body(doc: Dict[str, Any]) -> Dict[str, Any]:
    system = (
        "You write copy for a popup. Output exactly TWO lines, each <= 16 words. "
        "Line 1: Reference the user's last activity using \"{activityType} — {description}\" and gently reflect the mood. "
        "Line 2: Clear CTA tailored to the activity (e.g., \"Episode 17...\", \"Start your run...\", \"Open your sketchbook...\"). "
        "If bookmark is truthy/URL, subtly acknowledge with \"your favorite\" or \"bookmarked pick\" (no links in text). "
        "Friendly, supportive, no spoilers, no lists, no quotes/markdown/hashtags, <=1 emoji total, at most one question."
    )
    user = (
        f"activityType: {doc.get('activityType','')}\n"
        f"description: {doc.get('description','')}\n"
        f"mood: {doc.get('mood','')}\n"
        f"bookmark: {doc.get('bookmark')}\n\n"
        "Write the two lines now."
    )
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 120,
        "temperature": 0.6,
        "top_p": 0.9,
        "system": system,
        "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
        "stop_sequences": ["\n\n"]
    }


def _fallback_lines(doc: Dict[str, Any]) -> List[str]:
    label = f"{doc.get('activityType','activity')} — {doc.get('description','')}".strip(" —")
    mood = str(doc.get("mood", "neutral")).lower()
    return [
        f"{label} fits your {mood} vibe.",
        "Tap Next to continue."
    ]


def _generate_lines(doc: Dict[str, Any]) -> List[str]:
    try:
        body = _build_body(doc)
        resp = bedrock.invoke_model(
            modelId=MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(resp["body"].read())
        text = "".join(
            b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text"
        ).strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines[:2] if len(lines) >= 2 else _fallback_lines(doc)
    except Exception:
        return _fallback_lines(doc)


# -----------------------------
# Lambda handler
# -----------------------------
@with_logging()
def lambda_handler(event, context):
    # 1) Extract HTTP meta FIRST
    method, path, qs = _extract_http_meta(event)

    # 2) Init DB/collections BEFORE any route logic
    db = get_db()
    activities = db['activities']
    users = db['users']

    # 3) Parse body safely
    body = event.get('body')
    if isinstance(body, str):
        try:
            data = json.loads(body)
        except Exception:
            data = {}
    else:
        data = body or {}

    def get_param(name, default=None, cast=None):
        val = (qs or {}).get(name, default)
        if val is None or val == '':
            return default
        if cast:
            try:
                return cast(val)
            except Exception:
                return default
        return val

    # Health checks (optional)
    if method == 'GET' and path.endswith('/health'):
        return _resp(200, {"ok": True})
    if method == 'GET' and path.endswith('/db-ping'):
        try:
            db.command("ping")
            return _resp(200, {"db": "ok"})
        except Exception as e:
            return _resp(500, {"db": "fail", "error": str(e)})

    # -----------------------------
    # GET /activity-suggestion
    # -----------------------------
    if method == 'GET' and path.endswith('/activity-suggestion'):
        user_id = qs.get('userId')
        if not user_id:
            return _resp(400, {"error": "Missing userId"})

        cursor = (
            activities.find({"userId": user_id})
            .sort([("timestamp", DESCENDING), ("lastUpdated", DESCENDING)])
        )
        docs = [{k: v for k, v in d.items() if k != "_id"} for d in cursor]
        if not docs:
            return _resp(404, {"error": "No activity found for user"})

        def to_popup(doc, lines):
            return {
                "ui": {"title": "Suggested For You"},
                "bodyLines": lines,
                "cta": {
                    "id": "next",
                    "label": "Next",
                    "action": "open",
                    "payload": {
                        "activityId": doc.get("activityId"),
                        "activityType": doc.get("activityType"),
                        "description": doc.get("description"),
                        "bookmark": doc.get("bookmark"),
                    },
                },
                "meta": {"source": "anthropic", "mood": doc.get("mood"), "timestamp": doc.get("timestamp")},
            }

        suggestions = [to_popup(d, _generate_lines(d)) for d in docs]
        return _resp(200, {"suggestions": suggestions})

    # -----------------------------
    # POST /activity-log (create)
    # -----------------------------
    if method == 'POST' and path.endswith('/activity-log'):
        userId = data.get('userId')
        activityType = data.get('activityType')
        description = data.get('description')

        if not userId or not users.find_one({'userId': userId}):
            return _resp(400, {"error": "Invalid or missing userId"})
        if not activityType or not description:
            return _resp(400, {"error": "Missing mandatory field: activityType or description"})

        now_iso = datetime.utcnow().isoformat()
        activity = {
            "activityId": str(uuid.uuid4()),
            "userId": userId,
            "activityType": activityType,
            "description": description,
            "bookmark": data.get('bookmark'),
            "mood": data.get('mood'),
            "timestamp": data.get('timestamp', now_iso),
            "lastUpdated": now_iso,
        }
        activities.insert_one(activity)
        return _resp(201, {"message": "Activity logged", "activityId": activity["activityId"]})

    # -----------------------------
    # PUT /activity-log (update)
    # -----------------------------
    if method == 'PUT' and path.endswith('/activity-log'):
        activityId = data.get('activityId')
        if not activityId:
            return _resp(400, {"error": "Missing activityId"})

        allowed = ["activityType", "description", "mood", "timestamp", "bookmark"]
        update_fields = {k: v for k, v in data.items() if k in allowed}
        update_fields['lastUpdated'] = datetime.utcnow().isoformat()

        result = activities.update_one({"activityId": activityId}, {"$set": update_fields})
        return _resp(200, {"message": "Activity updated"} if result.matched_count else {"error": "Activity not found"})

    # -----------------------------
    # GET /activity-log (paged)
    # -----------------------------
    if method == 'GET' and path.endswith('/activity-log'):
        user_id = get_param('userId')
        activity_type = get_param('activityType')
        page = get_param('page', 1, int)
        page_size = get_param('pageSize', 10, int)
        start_date = get_param('startDate')
        end_date = get_param('endDate')
        sort_order = int(get_param('sortOrder', 1))  # 1=asc, 0=desc
        sort_dir = 1 if sort_order == 1 else -1

        query = {}
        if user_id:
            query['userId'] = user_id
        if activity_type:
            query['activityType'] = activity_type
        if start_date or end_date:
            query['timestamp'] = {}
            if start_date:
                query['timestamp']['$gte'] = start_date
            if end_date:
                query['timestamp']['$lte'] = end_date

        total = activities.count_documents(query)
        cursor = (
            activities.find(query)
            .sort("timestamp", sort_dir)
            .skip(max(0, (page - 1) * page_size))
            .limit(page_size)
        )

        items = [{k: v for k, v in doc.items() if k != '_id'} for doc in cursor]
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 1

        return _resp(200, {
            "items": items,
            "page": page,
            "pageSize": page_size,
            "count": len(items),
            "total": total,
            "totalPages": total_pages,
            "hasNextPage": (page * page_size) < total,
            "hasPrevPage": page > 1,
            "appliedFilters": {
                "userId": user_id, "activityType": activity_type,
                "startDate": start_date, "endDate": end_date,
                "page": page, "pageSize": page_size
            }
        })

    # -----------------------------
    # Legacy: GET /user-logs/{userId}
    # -----------------------------
    if method == 'GET' and '/user-logs/' in path:
        userId = path.split('/user-logs/')[-1]
        if not userId:
            return _resp(400, {"error": "Missing userId"})

        startDate = get_param('startDate')
        endDate   = get_param('endDate')

        query = {"userId": userId}
        if startDate or endDate:
            query['timestamp'] = {}
            if startDate:
                query['timestamp']['$gte'] = startDate
            if endDate:
                query['timestamp']['$lte'] = endDate

        page      = get_param('page', 1, int)
        page_size = get_param('pageSize', 10, int)

        cursor = (
            activities.find(query)
            .sort("timestamp", -1)
            .skip(max(0, (page - 1) * page_size))
            .limit(page_size)
        )
        logs = [{k: v for k, v in doc.items() if k != '_id'} for doc in cursor]
        return _resp(200, {"logs": logs, "page": page, "pageSize": page_size})

    return _resp(400, {"error": "Invalid request"})
