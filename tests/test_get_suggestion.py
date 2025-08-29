import os
import json
import pytest
from unittest.mock import patch, MagicMock
from backend import get_suggestion

@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    monkeypatch.delenv("BEDROCK_REGION", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

@pytest.mark.parametrize("env_var,expected_region", [
    ("BEDROCK_REGION", "us-east-1"),
    ("AWS_REGION", "us-west-2"),
    (None, "eu-west-2")
])
def test_region_resolution(monkeypatch, env_var, expected_region):
    if env_var:
        monkeypatch.setenv(env_var, expected_region)
    region, source = get_suggestion._resolve_bedrock_region()
    assert region == expected_region

@patch("backend.get_suggestion.boto3.client")
def test_happy_path_bedrock_enabled(mock_bedrock_client):
    os.environ["USE_BEDROCK"] = "true"
    mock_client = MagicMock()
    mock_bedrock_client.return_value = mock_client
    anthropic_json = {
        "content": [{"type": "text", "text": json.dumps({
            "suggestion": "X", "alternatives": [], "reasoning": "R", "source": "ai", "metrics": {"db_ms": 0, "llm_ms": 123, "items": 1}, "applied": {"userId": "", "filters": {"avoidRecentDays": 3, "historyWindowDays": 30}}
        })}]
    }
    mock_client.invoke_model.return_value = {"body": json.dumps(anthropic_json)}
    event = {"queryStringParameters": {"userId": "user123"}}
    result = get_suggestion.lambda_handler(event, None)
    body = json.loads(result["body"])
    assert body["source"] == "ai"
    assert body["applied"]["userId"] == "user123"
    assert body["metrics"]["llm_ms"] > 0

@patch("backend.get_suggestion.boto3.client")
def test_fallback_access_denied(mock_bedrock_client):
    os.environ["USE_BEDROCK"] = "true"
    mock_client = MagicMock()
    mock_bedrock_client.return_value = mock_client
    mock_client.invoke_model.side_effect = Exception("AccessDeniedException")
    event = {"queryStringParameters": {"userId": "user456"}}
    result = get_suggestion.lambda_handler(event, None)
    body = json.loads(result["body"])
    assert body["source"] == "rule"
    assert body["applied"]["userId"] == "user456"
    assert body["metrics"]["llm_ms"] == 0

@patch("backend.get_suggestion.boto3.client")
def test_malformed_body_safe_json(mock_bedrock_client):
    os.environ["USE_BEDROCK"] = "true"
    mock_client = MagicMock()
    mock_bedrock_client.return_value = mock_client
    # Return non-JSON text
    mock_client.invoke_model.return_value = {"body": "not a json"}
    event = {"queryStringParameters": {"userId": "user789"}}
    result = get_suggestion.lambda_handler(event, None)
    body = json.loads(result["body"])
    assert body["source"] == "rule"
    assert "Fallback due to LLM error." in body["reasoning"]
    assert body["applied"]["userId"] == "user789"

@patch("backend.get_suggestion.boto3.client")
def test_use_bedrock_false_rule_response(mock_bedrock_client):
    os.environ["USE_BEDROCK"] = "false"
    event = {"queryStringParameters": {"userId": "user999"}}
    result = get_suggestion.lambda_handler(event, None)
    body = json.loads(result["body"])
    assert body["source"] == "rule"
    assert body["metrics"]["llm_ms"] == 0
    assert body["applied"]["userId"] == "user999"

@patch("backend.get_suggestion.boto3.client")
def test_missing_userid_sets_default(mock_bedrock_client):
    os.environ["USE_BEDROCK"] = "true"
    mock_client = MagicMock()
    mock_bedrock_client.return_value = mock_client
    anthropic_json = {
        "content": [{"type": "text", "text": json.dumps({
            "suggestion": "X", "alternatives": [], "reasoning": "R", "source": "ai", "metrics": {"db_ms": 0, "llm_ms": 123, "items": 1}, "applied": {"userId": "", "filters": {"avoidRecentDays": 3, "historyWindowDays": 30}}
        })}]
    }
    mock_client.invoke_model.return_value = {"body": json.dumps(anthropic_json)}
    event = {"queryStringParameters": {}}
    result = get_suggestion.lambda_handler(event, None)
    body = json.loads(result["body"])
    assert body["applied"]["userId"] is None or body["applied"]["userId"] == ""
