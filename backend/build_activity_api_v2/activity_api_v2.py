import os
import json
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple, Optional

import boto3
from pymongo import MongoClient, DESCENDING

import os
import json
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple, Optional
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
# Default to smarter, warmer Sonnet; still overridable via env
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-5-sonnet-20240620")
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

# ...existing code...

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
            logger.warning("Failed to parse body as JSON.")
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
                logger.warning(f"Failed to cast param {name} value {val}")
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
            logger.error(f"DB ping failed: {e}")
            return _resp(500, {"db": "fail", "error": str(e)})

    # ...existing code...
    # and ?temperature, ?top_p for sampling overrides.
    # -----------------------------
    if method == 'GET' and (path.endswith('/activity-suggestion') or path.endswith('/activity-suggestion-v2')):
        user_id = qs.get('userId')
        if not user_id:
            return _resp(400, {"error": "Missing userId"})

        # topK param (default 3, capped 3 for cost/perf)
        try:
            top_k = max(1, min(3, int((qs.get('topK') or '3'))))
        except Exception:
            top_k = 3

        # Set fresh=1, temperature=1.2, top_p=1.0 as defaults if not provided
        force_fresh = True
        temperature = float(qs.get('temperature', 1.2))
        top_p = float(qs.get('top_p', 1.0))

        cursor = (
            activities.find({"userId": user_id}, {"_id": 0})
            .sort([("timestamp", DESCENDING), ("lastUpdated", DESCENDING)])
            .limit(top_k)
        )
        docs = list(cursor)
        if not docs:
            return _resp(404, {"error": "No activity found for user"})

        # Single Bedrock call for up to 3 docs
        messages_map = _generate_batch_lines(
            activities, docs, bedrock, MODEL_ID,
            force_fresh=force_fresh,
            temperature=temperature,
            top_p=top_p,
        )

        def to_popup(doc, one_line: str):
            line1 = one_line
            line2 = ""
            ts = doc.get("timestamp")
            ts_out = to_iso_z(ts) if isinstance(ts, datetime) else ts
            return {
                "ui": {"title": "Suggested For You"},
                "bodyLines": [line1] if not line2 else [line1, line2],
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
                "meta": {"source": MODEL_ID, "mood": doc.get("mood"), "timestamp": ts_out},
            }

        suggestions = []
        for d in docs:
            text = messages_map.get(d.get("activityId")) or _fallback_line(d)
            suggestions.append(to_popup(d, text))

        return _resp(200, {"suggestions": suggestions})

    # ...existing code...
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
# Default to smarter, warmer Sonnet; still overridable via env
MODEL_ID = os.getenv("MODEL_ID", "anthropic.claude-3-5-sonnet-20240620")
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


# -----------------------------
# Date/Time normalization utilities (ISO-8601 Z + Mongo Date)
# -----------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_iso_z(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _try_fromiso(s: str) -> datetime:
    # Accept 'Z' and offset forms
    s2 = s.strip()
    if s2.endswith('Z'):
        s2 = s2.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s2)
    except Exception:
        # Fallbacks for common forms
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z",
                    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(s2, fmt)
                if fmt.endswith('%z') and dt.tzinfo is not None:
                    return dt
                # naive -> assume UTC
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        # Last resort: date-only
        try:
            dt = datetime.strptime(s.strip(), "%Y-%m-%d")
            return dt.replace(tzinfo=timezone.utc)
        except Exception as e:
            raise ValueError(f"Unparsable datetime: {s}") from e


def parse_to_utc_datetime(value: Any) -> datetime:
    """Convert input (str|datetime|None|epoch) to tz-aware UTC datetime. None -> now()."""
    if value is None or value == "":
        return now_utc()
    if isinstance(value, datetime):
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value).astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        # epoch seconds
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        dt = _try_fromiso(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    raise ValueError("Unsupported datetime input type")


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in doc.items() if k != '_id'}
    for k in ("timestamp", "lastUpdated"):
        if isinstance(out.get(k), datetime):
            out[k] = to_iso_z(out[k])
    # Also normalize cache ts if present
    if isinstance(out.get("suggestion16"), dict):
        ts = out["suggestion16"].get("ts")
        if isinstance(ts, datetime):
            out["suggestion16"]["ts"] = to_iso_z(ts)
    return out


# -----------------------------
# Legacy single-activity generator (kept for backward compatibility)
# -----------------------------

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
# New helpers for batch (3 latest) generation, <=16 words, cached 24h
# -----------------------------
CACHE_TTL_HOURS = 24


def enforce_word_limit(s: str, n: int = 16) -> str:
    words = (s or "").split()
    return " ".join(words[:n])


def _normalize_doc(d: Dict[str, Any]) -> Dict[str, Any]:
    mood = (d.get("mood") or "").lower()
    if "engert" in mood or "enger" in mood:  # e.g., "engertices"
        d = {**d, "mood": "energetic"}
    return d


def _prompt_system() -> str:
    return (
        "You are a concise motivational coach for a mobile popup.\n"
        "Goal: Generate EXACTLY N short, personalized messages—one per activity—each <= 16 words.\n"
        "Personalize using activityType, description, mood, and bookmark (if present). Be warm, specific, and actionable.\n"
        "If bookmark looks like a time (e.g., “6:30 AM”), anchor the suggestion to that time.\n"
        "No lists, no quotes, no markdown, no hashtags, <= 1 emoji total across all messages.\n"
        "Output STRICT JSON ONLY:\n"
        "[\n"
        '  {"activityId":"...", "message":"..."},\n'
        '  {"activityId":"...", "message":"..."}\n'
        "]"
    )


def _build_batch_user_prompt(docs: List[Dict[str, Any]]) -> str:
    lines = [
        "Generate messages for these activities (most recent first). Keep each message <= 16 words.",
        "",
    ]
    for i, d in enumerate(docs, start=1):
        lines += [
            f"{i}) activityId={d.get('activityId')}",
            f"   activityType={d.get('activityType')}",
            f"   description={(d.get('description') or '').strip()}",
            f"   mood={d.get('mood') or ''}",
            f"   bookmark={d.get('bookmark') or ''}",
            "",
        ]
    lines.append("Return the JSON array now.")
    return "\n".join(lines)


def _prompt_hash(system_text: str, user_text: str) -> str:
    h = hashlib.sha256()
    h.update(system_text.encode("utf-8"))
    h.update(b"\n---\n")
    h.update(user_text.encode("utf-8"))
    return h.hexdigest()


def _cache_fresh(cache_doc: Optional[Dict[str, Any]], model_id: str, prompt_hash: str) -> bool:
    if not cache_doc:
        return False
    if cache_doc.get("modelId") != model_id:
        return False
    if cache_doc.get("promptHash") != prompt_hash:
        return False
    try:
        ts = cache_doc.get("ts")
        if isinstance(ts, datetime):
            ts_dt = ts
        else:
            ts_dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except Exception:
        return False
    return (now_utc() - ts_dt) <= timedelta(hours=CACHE_TTL_HOURS)


def _read_cache_for(collection, doc: Dict[str, Any], model_id: str, prompt_hash: str) -> Optional[str]:
    cache = doc.get("suggestion16")
    if _cache_fresh(cache, model_id, prompt_hash):
        return cache.get("text")
    return None


def _write_cache_for(collection, doc: Dict[str, Any], text: str, model_id: str, prompt_hash: str):
    collection.update_one(
        {"activityId": doc["activityId"]},
        {"$set": {
            "suggestion16": {
                "modelId": model_id,
                "text": text,
                "promptHash": prompt_hash,
                "ts": now_utc(),  # store as real datetime
            },
            "lastUpdated": now_utc(),
        }}
    )


def _fallback_line(d: Dict[str, Any]) -> str:
    at = (d.get("activityType") or "activity").strip()
    desc = (d.get("description") or "").strip()
    mood = (d.get("mood") or "your").strip()
    bm = (d.get("bookmark") or "").strip()
    base = f"{at} — {desc} matches your {mood} vibe."
    if bm:
        base += " Try it at " + bm.replace("bookmark at", "").strip() + "."
    return enforce_word_limit(base, 16)


def _generate_batch_lines(collection, docs: List[Dict[str, Any]], bedrock_client, model_id: str) -> Dict[str, str]:
    """
    Returns mapping: { activityId: message (<=16 words) }
    Respects per-activity 24h cache and writes new suggestions back to the document.
    """
    if not docs:
        return {}

    # Normalize and prepare prompts
    normalized = [_normalize_doc(d) for d in docs]
    system_text = _prompt_system()
    user_text = _build_batch_user_prompt(normalized)
    p_hash = _prompt_hash(system_text, user_text)

    # Check cache first
    cached: Dict[str, str] = {}
    all_fresh = True
    for d in normalized:
        txt = _read_cache_for(collection, d, model_id, p_hash)
        if txt:
            cached[d["activityId"]] = enforce_word_limit(txt, 16)
        else:
            all_fresh = False

    if all_fresh:
        return cached

    # Build Bedrock request body (Anthropic)
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": [{"type": "text", "text": user_text}]}],
        "system": system_text,
        "max_tokens": 220,
        "temperature": 0.6,
        "top_p": 0.9,
    }

    # Invoke once for all docs
    try:
        resp = bedrock_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        raw = resp["body"].read()
        try:
            parsed = json.loads(raw)
        except Exception:
            text_raw = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
            try:
                parsed = json.loads(text_raw)
            except Exception:
                parsed = {"content": [{"type": "text", "text": text_raw}]}

        # Extract text if returned as content blocks
        if isinstance(parsed, dict) and "content" in parsed:
            text = ""
            for block in parsed.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = []

        out_map: Dict[str, str] = {}
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                aid = item.get("activityId")
                msg = enforce_word_limit((item.get("message") or "").strip(), 16)
                if aid and msg:
                    out_map[aid] = msg

        # Write cache for produced or fallback for missing
        for d in normalized:
            aid = d["activityId"]
            if aid in out_map:
                _write_cache_for(collection, d, out_map[aid], model_id, p_hash)
            elif aid not in cached:
                fb = _fallback_line(d)
                _write_cache_for(collection, d, fb, model_id, p_hash)
                out_map[aid] = fb

        out_map.update(cached)
        return out_map

    except Exception:
        # On any error, return cached or fallback for each
        out_map = dict(cached)
        for d in normalized:
            aid = d["activityId"]
            if aid not in out_map:
                out_map[aid] = _fallback_line(d)
        return out_map


# -----------------------------
# Lambda handler
# -----------------------------

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
    # GET /activity-suggestion-v2  (latest 3, single batch call, <=16 words each)
    # -----------------------------
    if method == 'GET' and path.endswith('/activity-suggestion-v2'):
        user_id = qs.get('userId')
        if not user_id:
            return _resp(400, {"error": "Missing userId"})

        # topK param (default 3, capped 3 for cost/perf)
        try:
            top_k = max(1, min(3, int((qs.get('topK') or '3'))))
        except Exception:
            top_k = 3

        cursor = (
            activities.find({"userId": user_id}, {"_id": 0})
            .sort([("timestamp", DESCENDING), ("lastUpdated", DESCENDING)])
            .limit(top_k)
        )
        docs = list(cursor)
        if not docs:
            return _resp(404, {"error": "No activity found for user"})

        # Single Bedrock call for up to 3 docs
        messages_map = _generate_batch_lines(activities, docs, bedrock, MODEL_ID)

        def to_popup(doc, one_line: str):
            # If your UI expects 2 lines, keep line2 minimal or empty
            line1 = one_line
            line2 = ""
            ts = doc.get("timestamp")
            ts_out = to_iso_z(ts) if isinstance(ts, datetime) else ts
            return {
                "ui": {"title": "Suggested For You"},
                "bodyLines": [line1] if not line2 else [line1, line2],
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
                "meta": {"source": MODEL_ID, "mood": doc.get("mood"), "timestamp": ts_out},
            }

        suggestions = []
        for d in docs:
            text = messages_map.get(d.get("activityId")) or _fallback_line(d)
            suggestions.append(to_popup(d, text))

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

        ts_in = data.get('timestamp')  # optional incoming timestamp
        now_dt = now_utc()
        activity = {
            "activityId": str(uuid.uuid4()),
            "userId": userId,
            "activityType": activityType,
            "description": description,
            "bookmark": data.get('bookmark'),
            "mood": data.get('mood'),
            "timestamp": parse_to_utc_datetime(ts_in),  # store as datetime
            "lastUpdated": now_dt,                      # store as datetime
        }
        activities.insert_one(activity)
        # Serialize for response
        return _resp(201, {"message": "Activity logged", "activityId": activity["activityId"], "timestamp": to_iso_z(activity["timestamp"])})

    # -----------------------------
    # PUT /activity-log (update)
    # -----------------------------
    if method == 'PUT' and path.endswith('/activity-log'):
        activityId = data.get('activityId')
        if not activityId:
            return _resp(400, {"error": "Missing activityId"})

        allowed = ["activityType", "description", "mood", "timestamp", "bookmark", "suggestion16"]
        update_fields = {k: v for k, v in data.items() if k in allowed}
        if "timestamp" in update_fields:
            try:
                update_fields["timestamp"] = parse_to_utc_datetime(update_fields["timestamp"])
            except Exception:
                return _resp(400, {"error": "Invalid timestamp; use ISO-8601, e.g., 2025-08-19T06:30:00Z"})
        update_fields['lastUpdated'] = now_utc()

        result = activities.update_one({"activityId": activityId}, {"$set": update_fields})
        return _resp(200, {"message": "Activity updated"} if result.matched_count else {"error": "Activity not found"})

    # -----------------------------
    # GET /activity-log (paged, ISO-8601 filters -> proper Date queries)
    # -----------------------------
    if method == 'GET' and path.endswith('/activity-log'):
        def parse_or_400(name: str) -> Optional[datetime]:
            val = get_param(name)
            if not val:
                return None
            try:
                return parse_to_utc_datetime(val)
            except Exception:
                raise ValueError(name)

        user_id = get_param('userId')
        activity_type = get_param('activityType')
        page = get_param('page', 1, int)
        page_size = get_param('pageSize', 10, int)
        sort_order = int(get_param('sortOrder', 0))  # default desc for timelines
        sort_dir = 1 if sort_order == 1 else -1

        try:
            start_dt = parse_or_400('startDate')
            end_dt = parse_or_400('endDate')
        except ValueError as e:
            return _resp(400, {"error": f"Invalid {str(e)}; use ISO-8601 like 2025-08-19T00:00:00Z"})

        query: Dict[str, Any] = {}
        if user_id:
            query['userId'] = user_id
        if activity_type:
            query['activityType'] = activity_type
        if start_dt or end_dt:
            ts_filter: Dict[str, Any] = {}
            if start_dt:
                ts_filter['$gte'] = start_dt
            if end_dt:
                ts_filter['$lte'] = end_dt
            query['timestamp'] = ts_filter

        total = activities.count_documents(query)
        cursor = (
            activities.find(query)
            .sort("timestamp", sort_dir)
            .skip(max(0, (page - 1) * page_size))
            .limit(page_size)
        )

        items = [serialize_doc(doc) for doc in cursor]
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
                "startDate": to_iso_z(start_dt) if start_dt else None,
                "endDate": to_iso_z(end_dt) if end_dt else None,
                "page": page, "pageSize": page_size
            }
        })

    # -----------------------------
    # Legacy: GET /user-logs/{userId} (kept; now uses date filters as real Dates)
    # -----------------------------
    if method == 'GET' and '/user-logs/' in path:
        userId = path.split('/user-logs/')[-1]
        if not userId:
            return _resp(400, {"error": "Missing userId"})

        startDate = get_param('startDate')
        endDate   = get_param('endDate')
        try:
            start_dt = parse_to_utc_datetime(startDate) if startDate else None
            end_dt = parse_to_utc_datetime(endDate) if endDate else None
        except Exception:
            return _resp(400, {"error": "Invalid date filter; use ISO-8601 like 2025-08-19T00:00:00Z"})

        query: Dict[str, Any] = {"userId": userId}
        if start_dt or end_dt:
            ts = {}
            if start_dt: ts['$gte'] = start_dt
            if end_dt:   ts['$lte'] = end_dt
            query['timestamp'] = ts

        page      = get_param('page', 1, int)
        page_size = get_param('pageSize', 10, int)

        cursor = (
            activities.find(query)
            .sort("timestamp", -1)
            .skip(max(0, (page - 1) * page_size))
            .limit(page_size)
        )
        logs = [serialize_doc(doc) for doc in cursor]
        return _resp(200, {"logs": logs, "page": page, "pageSize": page_size})

    return _resp(400, {"error": "Invalid request"})
