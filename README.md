sandbox-token-refresh job deployment command:

gcloud scheduler jobs create http sandbox-token-refresh-job \
    --schedule="*/5 * * * *" \
    --uri="https://us-central1-serendia.cloudfunctions.net/sandbox-token-refresh" \
    --http-method=POST \
    --time-zone="America/Chicago" \
    --location=us-central1 \
    --oidc-service-account-email="68642982777-compute@developer.gserviceaccount.com" \
    --oidc-token-audience="https://us-central1-serendia.cloudfunctions.net/sandbox-token-refresh"

sandbox-token-manager server deployment command:

  gcloud functions deploy sandbox-token-manager \
    --runtime python312 \
    --trigger-http \
    --entry-point token_manager_handler \
    --allow-unauthenticated \
    --region=us-central1 \
    --source .
    --project=serendia

List all Google Secrets

gcloud secrets list --project=serendia

View specific secret value

gcloud secrets versions access latest --secret="Google Secret Value" --project=serendia

Add Google Secret

echo "your-new-secret-value" | gcloud secrets versions add SECRET_NAME --data-file=-

Check Logs

gcloud functions logs read "Service Name" --region=us-central1 --limit=10

Manually call Procore token endpoint:

Replace with your actual values from Secret Manager

curl -X POST "https://login-sandbox.procore.com/oauth/token"
-d "grant_type=authorization_code"
-d "client_id=YOUR_CLIENT_ID"
-d "client_secret=YOUR_CLIENT_SECRET"
-d "code=YOUR_CODE"
-d "redirect_uri=YOUR_REDIRECT_URI"
