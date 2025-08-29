
import os
import json
import logging
import os
import json
import time
import logging
import boto3
from botocore.config import Config

# ---------- CloudWatch logging setup ----------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

def _resolve_bedrock_region():
    """
    Resolve the Bedrock region in a safe order.
    Returns: (region, source)
    """
    session = boto3.session.Session()
    region = (
        os.getenv("BEDROCK_REGION")
        or os.getenv("AWS_REGION")
        or session.region_name
        or "eu-west-2"
    )

    if os.getenv("BEDROCK_REGION"):
        source = "BEDROCK_REGION"
    elif os.getenv("AWS_REGION"):
        source = "AWS_REGION"
    elif session.region_name:
        source = "boto3_session"
    else:
        source = "default_eu-west-2"

    return region, source


def _anthropic_payload(system_instruction: str, prompt: str) -> dict:
    """
    Build the Anthropic-on-Bedrock request payload.
    """
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "temperature": 0.2,
        "system": system_instruction,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }


def call_bedrock_claude(prompt: str):
    """
    Calls Bedrock Claude with correct Anthropic payload.
    Returns: (result_dict, llm_ms)
    - result_dict: parsed JSON (or wrapped) following your schema
    - llm_ms: time spent in the invoke call in milliseconds.
    """
    model_id = os.environ.get(
        "BEDROCK_MODEL_ID",
        "anthropic.claude-3-sonnet-20240229-v1:0"
    )
    system_instruction = (
        "You are an assistant that always responds in strict JSON with this schema: "
        "{ 'suggestion': string, 'alternatives': [string], 'reasoning': string, 'source': 'ai', "
        "'metrics': { 'db_ms': int, 'llm_ms': int, 'items': int }, "
        "'applied': { 'userId': string, 'filters': { 'avoidRecentDays': 3, 'historyWindowDays': 30 } } } "
        "Do not include any prose or explanation outside the JSON."
    )

    region, source = _resolve_bedrock_region()
    logger.info("bedrock.region.selected=%s source=%s model_id=%s", region, source, model_id)

    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            read_timeout=12,   # short, so API GW doesn't hit 29s
            connect_timeout=3,
            retries={"max_attempts": 2, "mode": "adaptive"},
        ),
    )

    payload = _anthropic_payload(system_instruction, prompt)

    start = time.perf_counter()
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json",
    )
    llm_ms = max(1, int((time.perf_counter() - start) * 1000))  # never 0
    logger.info("bedrock.invoke_model.ok duration_ms=%d", llm_ms)

    body = response.get("body")
    if hasattr(body, "read"):
        body = body.read()
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")

    # Parse Anthropic response to get the text content
    data = json.loads(body)
    text = ""
    if isinstance(data, dict) and "content" in data and data["content"]:
        first = data["content"][0]
        text = first.get("text") if isinstance(first, dict) else str(first)
    else:
        text = body if isinstance(body, str) else json.dumps(data)

    # The system prompt asked for strict JSON in the text; attempt to parse
    try:
        result = json.loads(text)
    except Exception:
        result = {
            "suggestion": text.strip()[:300],
            "alternatives": [],
            "reasoning": "Model returned non-JSON; wrapped automatically.",
            "source": "ai",
            "metrics": {"db_ms": 0, "llm_ms": llm_ms, "items": 0},
            "applied": {"userId": "", "filters": {"avoidRecentDays": 3, "historyWindowDays": 30}},
        }

    # Ensure metrics.llm_ms is set (or updated) in the parsed JSON
    if isinstance(result, dict):
        result.setdefault("metrics", {})
        existing = result["metrics"].get("llm_ms", 0)
        try:
            existing = int(existing)
        except Exception:
            existing = 0
        result["metrics"]["llm_ms"] = max(existing, llm_ms, 1)
        result.setdefault("source", "ai")

    return result, llm_ms


def lambda_handler(event, context):
    """
    Lambda handler that honors USE_BEDROCK and returns your existing schema.
    """
    use_bedrock = os.getenv("USE_BEDROCK", "true").lower() == "true"
    user_id = None
    try:
        if isinstance(event, dict):
            qi = event.get("queryStringParameters") or {}
            user_id = qi.get("userId") or event.get("userId")
    except Exception:
        pass

    logger.info("request.start use_bedrock=%s userId=%s", use_bedrock, user_id)

    # If Bedrock disabled, return rule-based fallback quickly
    if not use_bedrock:
        body = {
            "suggestion": "Try something new!",
            "alternatives": ["Read a book", "Go for a walk"],
            "reasoning": "Based on your past activities and mood scores.",
            "source": "rule",
            "metrics": {"db_ms": 0, "llm_ms": 0, "items": 0},
            "applied": {"userId": user_id, "filters": {"avoidRecentDays": 3, "historyWindowDays": 30}},
        }
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body),
        }

    prompt = "Provide a JSON suggestion following the given schema for the user."

    try:
        result, llm_ms = call_bedrock_claude(prompt)
    except Exception as e:
        logger.exception("Bedrock/LLM error, using fallback.")
        result = {
            "suggestion": "Try something new!",
            "alternatives": ["Read a book", "Go for a walk"],
            "reasoning": "Fallback due to LLM error.",
            "source": "rule",
            "metrics": {"db_ms": 0, "llm_ms": 0, "items": 0},
            "applied": {"userId": user_id, "filters": {"avoidRecentDays": 3, "historyWindowDays": 30}},
        }
        llm_ms = 0

    # Ensure applied.userId is always the actual caller's id
    if isinstance(result, dict):
        result.setdefault("applied", {})
        result["applied"]["userId"] = user_id  # force the actual caller's id
        result["applied"].setdefault("filters", {"avoidRecentDays": 3, "historyWindowDays": 30})

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(result),
    }
