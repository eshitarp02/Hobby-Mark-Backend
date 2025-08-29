import unittest
from unittest.mock import patch, MagicMock
import os
import json
from backend import get_suggestion

class TestGetSuggestion(unittest.TestCase):
    def setUp(self):
        os.environ["USE_BEDROCK"] = "true"
        os.environ["BEDROCK_MODEL_ID"] = "anthropic.claude-3-sonnet-20240229-v1:0"
        os.environ["LOG_LEVEL"] = "INFO"

    @patch("backend.get_suggestion.call_bedrock_claude")
    def test_lambda_handler_bedrock_enabled(self, mock_bedrock):
        mock_bedrock.return_value = ({
            "suggestion": "Test suggestion",
            "alternatives": ["Alt1", "Alt2"],
            "reasoning": "Test reasoning",
            "source": "ai",
            "metrics": {"db_ms": 0, "llm_ms": 100, "items": 2},
            "applied": {"userId": "", "filters": {"avoidRecentDays": 3, "historyWindowDays": 30}},
        }, 100)
        event = {"queryStringParameters": {"userId": "user123"}}
        result = get_suggestion.lambda_handler(event, None)
        body = json.loads(result["body"])
        self.assertEqual(body["applied"]["userId"], "user123")
        self.assertEqual(body["source"], "ai")

    def test_lambda_handler_bedrock_disabled(self):
        os.environ["USE_BEDROCK"] = "false"
        event = {"queryStringParameters": {"userId": "user456"}}
        result = get_suggestion.lambda_handler(event, None)
        body = json.loads(result["body"])
        self.assertEqual(body["source"], "rule")
        self.assertEqual(body["applied"]["userId"], "user456")

    @patch("backend.get_suggestion.call_bedrock_claude", side_effect=Exception("Bedrock error"))
    def test_lambda_handler_bedrock_error(self, mock_bedrock):
        os.environ["USE_BEDROCK"] = "true"
        event = {"queryStringParameters": {"userId": "user789"}}
        result = get_suggestion.lambda_handler(event, None)
        body = json.loads(result["body"])
        self.assertEqual(body["source"], "rule")
        self.assertEqual(body["applied"]["userId"], "user789")

if __name__ == "__main__":
    unittest.main()
