# MoodMark AWS Infrastructure Setup

This folder contains notes and scripts for setting up AWS resources:

- S3 bucket: moodmark-user-logs
- API Gateway: Expose /log-activity and /get-suggestion endpoints
- Lambda functions: log_activity, get_suggestion
- (Planned) Cognito for authentication
- (Planned) DynamoDB for analytics

## Setup Steps

1. Create S3 bucket `moodmark-user-logs` (or your preferred name).
2. Deploy Lambda functions in `../backend/` with appropriate IAM roles (S3 access, etc).
3. Set environment variables for each Lambda (e.g., S3_BUCKET, GOOGLE_AI_API_KEY).
4. Create API Gateway REST API with two endpoints:
   - POST /log-activity → log_activity Lambda
   - GET /get-suggestion → get_suggestion Lambda
5. (Planned) Set up Cognito for user authentication.
6. (Planned) Set up DynamoDB for activity aggregation.

See AWS docs for detailed steps or use the AWS Console/CLI.
