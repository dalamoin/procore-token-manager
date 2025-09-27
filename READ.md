**List all Google Secrets

gcloud secrets list --project=serendia

View specific secret value

gcloud secrets versions access latest --secret="Google Secret Value" --project=serendia

Add Google Secret

echo "your-new-secret-value" | gcloud secrets versions add SECRET_NAME --data-file=-

Check Logs

gcloud functions logs read "Service Name" --region=us-central1 --limit=10

Manually call Procore token endpoint:

Replace with your actual values from Secret Manager

curl -X POST "https://login-sandbox.procore.com/oauth/token" \
  -d "grant_type=authorization_code" \
  -d "client_id=DYg52m4iwM_3rkJ2RdplGPd_O2DHhw1cI8u6c_BHecw" \
  -d "client_secret=4Bx8m7X701Es75zIDs9ldKDbsMf62SxQewtsBpIJYcU" \
  -d "code=0r3kkTUxL4vZcfpywmC1I9ZdU8GduCCgNAfLmjzWyYg" \
  -d "redirect_uri=https://us-central1-serendia.cloudfunctions.net/sandbox-token-manager"
