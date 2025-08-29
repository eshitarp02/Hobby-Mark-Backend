import pytest
from unittest.mock import patch, MagicMock
from backend import activity_api

def make_event(sortOrder):
    return {
        "httpMethod": "GET",
        "path": "/activity-log",
        "queryStringParameters": {
            "userId": "u1",
            "sortOrder": str(sortOrder)
        }
    }

def test_sort_ascending(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    with patch("backend.activity_api.get_db") as mock_get_db:
        mock_activities = MagicMock()
        mock_get_db.return_value = {"activities": mock_activities, "users": MagicMock()}
        mock_activities.count_documents.return_value = 2
        mock_activities.find.return_value.sort.return_value.skip.return_value.limit.return_value = [
            {"timestamp": "2025-08-01"}, {"timestamp": "2025-08-02"}
        ]
        event = make_event(1)
        result = activity_api.lambda_handler(event, None)
        assert result["statusCode"] == 200
        body = result["body"]
        assert "2025-08-01" in body and "2025-08-02" in body


def test_sort_descending(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    with patch("backend.activity_api.get_db") as mock_get_db:
        mock_activities = MagicMock()
        mock_get_db.return_value = {"activities": mock_activities, "users": MagicMock()}
        mock_activities.count_documents.return_value = 2
        mock_activities.find.return_value.sort.return_value.skip.return_value.limit.return_value = [
            {"timestamp": "2025-08-02"}, {"timestamp": "2025-08-01"}
        ]
        event = make_event(0)
        result = activity_api.lambda_handler(event, None)
        assert result["statusCode"] == 200
        body = result["body"]
        assert "2025-08-02" in body and "2025-08-01" in body
