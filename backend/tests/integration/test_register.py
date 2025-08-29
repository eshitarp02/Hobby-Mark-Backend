import requests
import pytest

API_URL = "https://tylp1a64mg.execute-api.eu-west-2.amazonaws.com/prod/register"

import random
import string

@pytest.fixture
def user_payload():
    rand_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    name = f"user_inttest_{rand_suffix}"
    email = f"{name}@example.com"
    password = f"Pass_{rand_suffix}"
    return {
        "action": "register",
        "name": name,
        "email": email,
        "password": password
    }

def test_register_success(user_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    response = requests.post(API_URL, json=user_payload, headers=headers)
    assert response.status_code == 201
    assert "userId" in response.text

def test_register_duplicate_email(user_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    requests.post(API_URL, json=user_payload, headers=headers)  # Register once
    response = requests.post(API_URL, json=user_payload, headers=headers)  # Try again
    assert response.status_code == 409
    assert "already exists" in response.text

def test_register_missing_password(user_payload):
    headers = {"x-api-key": "EHsn17DBbq4QvO34nUzsf9pk1GNEcXLi6U9EdN84"}
    payload = user_payload.copy()
    del payload["password"]
    response = requests.post(API_URL, json=payload, headers=headers)
    assert response.status_code == 400
    assert "Missing" in response.text
