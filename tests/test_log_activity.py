import pytest
from unittest.mock import patch, MagicMock
from backend import log_activity

def test_log_activity_success(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    event = {"body": '{"userId": "u1", "activity": "run"}'}
    context = None
    with patch("backend.log_activity.MongoClient") as mock_mongo:
        mock_db = MagicMock()
        mock_mongo.return_value = mock_db
        mock_db.log.insert_one.return_value = MagicMock(inserted_id="id456")
        result = log_activity.lambda_handler(event, context)
        assert result["statusCode"] == 200
        assert "logged" in result["body"]

def test_log_activity_missing_fields():
    event = {"body": '{"activity": "run"}'}
    context = None
    result = log_activity.lambda_handler(event, context)
    assert result["statusCode"] == 400
    assert "Missing required fields" in result["body"]

def test_log_activity_db_timeout(monkeypatch):
    event = {"body": '{"userId": "u1", "activity": "run"}'}
    context = None
    with patch("backend.log_activity.MongoClient") as mock_mongo:
        mock_mongo.side_effect = Exception("Timeout")
        result = log_activity.lambda_handler(event, context)
        assert result["statusCode"] == 500
        assert "Timeout" in result["body"]
