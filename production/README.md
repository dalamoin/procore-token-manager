
  production-token-refresh job deployment

gcloud functions deploy production-token-refresh
--runtime python312
--trigger-http
--entry-point scheduled_refresh_handler
--region=us-central1
--source .
--project=serendia

gcloud scheduler jobs create http sandbox-token-refresh-job
--schedule="*/5 * * * *"
--uri="https://us-central1-serendia.cloudfunctions.net/sandbox-token-refresh"
--http-method=POST
--time-zone="America/Chicago"
--location=us-central1
--oidc-service-account-email="68642982777-compute@developer.gserviceaccount.com"
--oidc-token-audience="https://us-central1-serendia.cloudfunctions.net/sandbox-token-refresh"

sandbox-token-manager server deployment command:

gcloud functions deploy sandbox-token-manager
--runtime python312
--trigger-http
--entry-point token_manager_handler
--allow-unauthenticated
--region=us-central1
--source . --project=serendia
