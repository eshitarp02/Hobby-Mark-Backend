import pytest
from unittest.mock import patch, MagicMock
from backend import get_activitieslogperuserid

def test_get_activities_success(monkeypatch):
    event = {"queryStringParameters": {"userId": "u1"}}
    context = None
    with patch("backend.get_activitieslogperuserid.MongoClient") as mock_mongo:
        mock_db = MagicMock()
        mock_mongo.return_value = mock_db
        mock_db.log.find.return_value = [{"activity": "walk"}, {"activity": "run"}]
        result = get_activitieslogperuserid.lambda_handler(event, context)
        assert result["statusCode"] == 200
        assert "walk" in result["body"]
        assert "run" in result["body"]

def test_get_activities_missing_userid():
    event = {"queryStringParameters": {}}
    context = None
    result = get_activitieslogperuserid.lambda_handler(event, context)
    assert result["statusCode"] == 400
    assert "Missing userId" in result["body"]

def test_get_activities_db_error(monkeypatch):
    event = {"queryStringParameters": {"userId": "u1"}}
    context = None
    with patch("backend.get_activitieslogperuserid.MongoClient") as mock_mongo:
        mock_mongo.side_effect = Exception("DB error")
        result = get_activitieslogperuserid.lambda_handler(event, context)
        assert result["statusCode"] == 500
        assert "DB error" in result["body"]
