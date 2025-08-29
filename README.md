# MoodMark – Hobby Activity Logger & Smart Suggestion App

MoodMark is an end-to-end solution for logging your hobby activities and getting personalized, AI-powered suggestions for what to do next. It features an Android app frontend and a secure, scalable AWS backend.

---

## Features
- **Log Activities:** Record your hobby activities (reading, watching, drawing, etc.) with details and optional bookmarks.
- **Smart Suggestions:** Tap "I'm Bored" to get a fun, personalized suggestion based on your recent activities (powered by Google AI Studio).
- **Cloud Storage:** All logs are securely stored in your own S3 bucket.
- **Modular & Scalable:** Designed for easy integration with authentication, analytics, voice input, and sharing features.

---

## Project Structure

```
moddy/
│
├── android-app/           # Android Studio project (UI, API calls)
├── backend/               # AWS Lambda functions (Python)
│   ├── log_activity.py    # Lambda: log activity to S3
│   ├── get_suggestion.py  # Lambda: fetch logs, call Google AI, return suggestion
│   └── requirements.txt   # Python dependencies
├── infra/                 # AWS setup (CloudFormation, notes)
│   ├── moodmark-cloudformation.yaml
│   └── README.md
└── .github/workflows/     # GitHub Actions pipeline for CI/CD
```

---

## Quick Start

### 1. Android App
- Open `android-app/` in Android Studio.
- Use the provided `network.kt` for API calls.
- Update the API base URL to your deployed API Gateway endpoint.

### 2. Backend (AWS Lambda)
- See `backend/` for Lambda code and dependencies.
- Deploy using the CloudFormation template in `infra/`.
- Set environment variables for S3 bucket and Google AI API key.

### 3. Infrastructure
- Use `infra/moodmark-cloudformation.yaml` to provision S3, Lambda, and API Gateway.
- See `infra/README.md` for setup notes.

### 4. CI/CD
- GitHub Actions pipeline auto-deploys infra on PRs to `dev` branch.
- Store AWS role and region in GitHub secrets.

---

## Planned Enhancements
- User authentication (AWS Cognito)
- Aggregated analytics (DynamoDB)
- Grouping/filtering by hobby type
- Weekly insights
- Voice command input
- Social sharing

---

## Security & Best Practices
- All secrets managed via environment variables or GitHub secrets.
- IAM roles follow least-privilege principle.
- Modular, extensible codebase for future features.

---

## License
MIT