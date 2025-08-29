import pytest
from unittest.mock import patch, MagicMock
from backend import activity_api

def test_post_activity_valid(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    event = {"body": '{"userId": "u1", "activity": "walk"}'}
    context = None
    with patch("backend.activity_api.some_db_client") as mock_db:
        mock_db.return_value.insert_one.return_value = MagicMock(inserted_id="id123")
        result = activity_api.lambda_handler(event, context)
        assert result["statusCode"] == 200
        assert "success" in result["body"]

def test_post_activity_missing_fields():
    event = {"body": '{"activity": "walk"}'}
    context = None
    result = activity_api.lambda_handler(event, context)
    assert result["statusCode"] == 400
    assert "Missing required fields" in result["body"]

def test_post_activity_db_error(monkeypatch):
    event = {"body": '{"userId": "u1", "activity": "walk"}'}
    context = None
    with patch("backend.activity_api.some_db_client") as mock_db:
        mock_db.return_value.insert_one.side_effect = Exception("DB error")
        result = activity_api.lambda_handler(event, context)
        assert result["statusCode"] == 500
        assert "DB error" in result["body"]

# -----------------------------
# Tests for /activity-suggestion endpoint
# -----------------------------
def test_activity_suggestion_valid(monkeypatch):
    event = {
        "httpMethod": "GET",
        "path": "/activity-suggestion",
        "queryStringParameters": {"userId": "u1"}
    }
    context = None
    mock_activity = {
        "activityType": "run",
        "description": "morning jog",
        "mood": "energized",
        "bookmark": ""
    }
    with patch("backend.activity_api.activities.find") as mock_find, \
         patch("backend.get_suggestion.call_bedrock_claude") as mock_bedrock:
        mock_find.return_value.sort.return_value.limit.return_value.__iter__.return_value = [mock_activity]
        mock_bedrock.return_value = ("Line 1\nLine 2", None)
        result = activity_api.lambda_handler(event, context)
        assert result["statusCode"] == 200
        assert "popup" in result["body"]

def test_activity_suggestion_missing_userid():
    event = {
        "httpMethod": "GET",
        "path": "/activity-suggestion",
        "queryStringParameters": {}
    }
    context = None
    result = activity_api.lambda_handler(event, context)
    assert result["statusCode"] == 400
    assert "Missing userId" in result["body"]

def test_activity_suggestion_no_activity(monkeypatch):
    event = {
        "httpMethod": "GET",
        "path": "/activity-suggestion",
        "queryStringParameters": {"userId": "u1"}
    }
    context = None
    with patch("backend.activity_api.activities.find") as mock_find:
        mock_find.return_value.sort.return_value.limit.return_value.__iter__.return_value = []
        result = activity_api.lambda_handler(event, context)
        assert result["statusCode"] == 404
        assert "No activity found" in result["body"]

def test_activity_suggestion_bedrock_failure(monkeypatch):
    event = {
        "httpMethod": "GET",
        "path": "/activity-suggestion",
        "queryStringParameters": {"userId": "u1"}
    }
    context = None
    mock_activity = {
        "activityType": "run",
        "description": "morning jog",
        "mood": "energized",
        "bookmark": ""
    }
    with patch("backend.activity_api.activities.find") as mock_find, \
         patch("backend.get_suggestion.call_bedrock_claude") as mock_bedrock:
        mock_find.return_value.sort.return_value.limit.return_value.__iter__.return_value = [mock_activity]
        mock_bedrock.side_effect = Exception("Bedrock error")
        result = activity_api.lambda_handler(event, context)
        assert result["statusCode"] == 500
        assert "Bedrock call failed" in result["body"]
