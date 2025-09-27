# Procore Token Manager - Operations Runbook

## Overview

The Procore Token Manager is an automated OAuth token management system that maintains valid access tokens for Procore API integration. It runs on Google Cloud Platform and supports both sandbox and production environments.

## Architecture

### Components

**Cloud Functions (per environment):**
- `{env}-token-manager` - OAuth flow handler and manual token management UI
- `{env}-token-refresh` - Automated token refresh service

**Cloud Scheduler:**
- `{env}-token-refresh-job` - Triggers token refresh on schedule

**Secret Manager:**
- `procore-client-id-{env}` - OAuth client ID
- `procore-client-secret-{env}` - OAuth client secret
- `procore-redirect-uri-{env}` - OAuth redirect URI
- `procore-access-token-{env}` - Current access token (auto-updated)
- `procore-refresh-token-{env}` - Current refresh token (auto-updated)

**Environment Values:**
- `{env}` = `sandbox` or `production`

### Data Flow

```
1. Initial OAuth Flow:
   User → Token Manager UI → Procore OAuth → Callback → Store Tokens

2. Automated Refresh:
   Cloud Scheduler → Token Refresh Function → Procore API → Update Secrets
```

## Environment-Specific Details

### Sandbox Environment

| Component | Value |
|-----------|-------|
| OAuth Base URL | `https://login-sandbox.procore.com` |
| Token Manager Function | `sandbox-token-manager` |
| Refresh Function | `sandbox-token-refresh` |
| Scheduler Job | `sandbox-token-refresh-job` |
| Refresh Schedule | Every hour (`0 * * * *`) |
| Region | `us-central1` |
| Project | `serendia` |

### Production Environment

| Component | Value |
|-----------|-------|
| OAuth Base URL | `https://login.procore.com` |
| Token Manager Function | `production-token-manager` |
| Refresh Function | `production-token-refresh` |
| Scheduler Job | `production-token-refresh-job` |
| Refresh Schedule | Every hour (`0 * * * *`) |
| Region | `us-central1` |
| Project | `serendia` |

## Common Operations

### 1. Initial OAuth Setup

**Purpose:** Obtain initial access and refresh tokens

**Steps:**
```bash
# 1. Open token manager UI
https://us-central1-serendia.cloudfunctions.net/{env}-token-manager

# 2. Click "Authenticate with Procore"
# 3. Log in to Procore and authorize
# 4. Tokens are automatically stored in Secret Manager
```

**Verification:**
```bash
# Check tokens exist
gcloud secrets versions list procore-access-token-{env} \
  --project=serendia \
  --limit=1

gcloud secrets versions list procore-refresh-token-{env} \
  --project=serendia \
  --limit=1
```

### 2. Manual Token Refresh

**Purpose:** Force immediate token refresh without waiting for scheduler

**Method 1: Via UI**
```bash
# Open token manager
https://us-central1-serendia.cloudfunctions.net/{env}-token-manager

# Click "Manual Refresh Tokens" button
```

**Method 2: Via API**
```bash
curl -X POST https://us-central1-serendia.cloudfunctions.net/{env}-token-refresh
```

**Method 3: Via gcloud**
```bash
gcloud functions call {env}-token-refresh \
  --region=us-central1 \
  --project=serendia
```

**Method 4: Trigger scheduler**
```bash
gcloud scheduler jobs run {env}-token-refresh-job \
  --location=us-central1 \
  --project=serendia
```

### 3. View Current Tokens

**Via UI:**
```
https://us-central1-serendia.cloudfunctions.net/{env}-token-manager
```

**Via gcloud:**
```bash
# View token preview (first 20 characters)
gcloud secrets versions access latest \
  --secret=procore-access-token-{env} \
  --project=serendia | head -c 20 && echo "..."
```

### 4. Check Token Refresh Status

**View logs:**
```bash
# Recent refresh attempts
gcloud logging read \
  "resource.type=cloud_run_revision AND 
   resource.labels.service_name={env}-token-refresh AND 
   severity>=INFO" \
  --limit=10 \
  --project=serendia \
  --format=json
```

**Check scheduler history:**
```bash
gcloud scheduler jobs describe {env}-token-refresh-job \
  --location=us-central1 \
  --project=serendia
```

### 5. Monitor Secret Versions

**List all versions:**
```bash
gcloud secrets versions list procore-access-token-{env} \
  --project=serendia \
  --format="table(name,state,createTime)"
```

**Count enabled versions (should be 1):**
```bash
gcloud secrets versions list procore-access-token-{env} \
  --filter="state=ENABLED" \
  --project=serendia \
  --format="value(name)" | wc -l
```

### 6. Update Scheduler Frequency

**Change refresh schedule:**
```bash
# Hourly (recommended for production)
gcloud scheduler jobs update http {env}-token-refresh-job \
  --schedule="0 * * * *" \
  --location=us-central1 \
  --project=serendia

# Every 30 minutes
gcloud scheduler jobs update http {env}-token-refresh-job \
  --schedule="*/30 * * * *" \
  --location=us-central1 \
  --project=serendia

# Every 5 minutes (testing only)
gcloud scheduler jobs update http {env}-token-refresh-job \
  --schedule="*/5 * * * *" \
  --location=us-central1 \
  --project=serendia
```

## Troubleshooting

### Issue: Token refresh failing with 401 Unauthorized

**Possible Causes:**
- Refresh token expired or revoked
- Client credentials changed in Procore
- OAuth app configuration mismatch

**Resolution:**
```bash
# 1. Verify client credentials in Secret Manager
gcloud secrets versions access latest \
  --secret=procore-client-id-{env} \
  --project=serendia

# 2. Check Procore app configuration matches redirect URI
gcloud secrets versions access latest \
  --secret=procore-redirect-uri-{env} \
  --project=serendia

# 3. Re-authenticate via UI to get fresh tokens
# Visit: https://us-central1-serendia.cloudfunctions.net/{env}-token-manager
```

### Issue: Scheduler not triggering function

**Check permissions:**
```bash
# Verify Cloud Scheduler has invoke permissions
gcloud run services get-iam-policy {env}-token-refresh \
  --region=us-central1 \
  --project=serendia

# Should show: service-68642982777@gcp-sa-cloudscheduler.iam.gserviceaccount.com
# with role: roles/run.invoker
```

**Fix permissions if missing:**
```bash
gcloud functions add-invoker-policy-binding {env}-token-refresh \
  --region=us-central1 \
  --member="serviceAccount:service-68642982777@gcp-sa-cloudscheduler.iam.gserviceaccount.com" \
  --project=serendia
```

### Issue: Multiple enabled secret versions

**Symptom:** More than 1 enabled version exists

**Impact:** Increased storage costs, potential confusion

**Resolution:**
```bash
# The system auto-cleans, but you can manually destroy old versions
gcloud secrets versions destroy VERSION_NUMBER \
  --secret=procore-access-token-{env} \
  --project=serendia
```

### Issue: Function timeout or errors

**Check function logs:**
```bash
gcloud logging read \
  "resource.labels.service_name={env}-token-refresh AND 
   severity>=ERROR" \
  --limit=20 \
  --project=serendia \
  --format=json
```

**Common errors:**
- Network timeout: Increase function timeout
- Secret access denied: Check service account permissions
- Procore API errors: Check Procore service status

## Deployment

### Deploy Token Manager Function

```bash
cd ~/projects/clients/serendia/po-automation/procore-token-manager/{env}

gcloud functions deploy {env}-token-manager \
  --runtime python312 \
  --trigger-http \
  --entry-point token_manager_handler \
  --allow-unauthenticated \
  --region=us-central1 \
  --source . \
  --project=serendia
```

### Deploy Token Refresh Function

```bash
cd ~/projects/clients/serendia/po-automation/procore-token-manager/{env}

gcloud functions deploy {env}-token-refresh \
  --runtime python312 \
  --trigger-http \
  --entry-point scheduled_refresh_handler \
  --region=us-central1 \
  --source . \
  --project=serendia

# Grant scheduler permissions
gcloud functions add-invoker-policy-binding {env}-token-refresh \
  --region=us-central1 \
  --member="serviceAccount:service-68642982777@gcp-sa-cloudscheduler.iam.gserviceaccount.com" \
  --project=serendia
```

### Create Scheduler Job

```bash
gcloud scheduler jobs create http {env}-token-refresh-job \
  --schedule="0 * * * *" \
  --uri="https://us-central1-serendia.cloudfunctions.net/{env}-token-refresh" \
  --http-method=POST \
  --time-zone="America/Chicago" \
  --location=us-central1 \
  --oidc-service-account-email="68642982777-compute@developer.gserviceaccount.com" \
  --oidc-token-audience="https://us-central1-serendia.cloudfunctions.net/{env}-token-refresh" \
  --project=serendia
```

### Create Required Secrets

```bash
# Client credentials (from Procore app configuration)
echo -n "YOUR_CLIENT_ID" | gcloud secrets create procore-client-id-{env} \
  --data-file=- \
  --replication-policy="automatic" \
  --project=serendia

echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create procore-client-secret-{env} \
  --data-file=- \
  --replication-policy="automatic" \
  --project=serendia

echo -n "YOUR_REDIRECT_URI" | gcloud secrets create procore-redirect-uri-{env} \
  --data-file=- \
  --replication-policy="automatic" \
  --project=serendia

# Token storage (will be populated after OAuth)
gcloud secrets create procore-access-token-{env} \
  --replication-policy="automatic" \
  --project=serendia

gcloud secrets create procore-refresh-token-{env} \
  --replication-policy="automatic" \
  --project=serendia
```

## Security Considerations

### Access Control

**Service Account Permissions:**
- Cloud Function service account needs `roles/secretmanager.secretAccessor`
- Cloud Scheduler needs `roles/run.invoker` on refresh function
- Token manager function is `--allow-unauthenticated` (contains no sensitive data in UI)
- Token refresh function requires authentication via OIDC

### Secret Rotation

**Automatic:**
- Access tokens refresh every hour
- Old secret versions destroyed automatically (keep only latest)

**Manual (when needed):**
- Client ID/Secret: Update in Secret Manager after Procore app changes
- Refresh token: Re-authenticate via OAuth UI

### Monitoring

**Set up alerts for:**
- Failed token refreshes (check logs for ERROR severity)
- Scheduler job failures
- Function invocation errors

```bash
# Example: Check for recent errors
gcloud logging read \
  "resource.labels.service_name={env}-token-refresh AND 
   severity=ERROR AND 
   timestamp>\"$(date -u -d '1 hour ago' --iso-8601=seconds)\"" \
  --project=serendia
```

## Reference URLs

### Sandbox
- Token Manager UI: `https://us-central1-serendia.cloudfunctions.net/sandbox-token-manager`
- Refresh Endpoint: `https://us-central1-serendia.cloudfunctions.net/sandbox-token-refresh`
- Procore OAuth: `https://login-sandbox.procore.com/oauth/authorize`

### Production
- Token Manager UI: `https://us-central1-serendia.cloudfunctions.net/production-token-manager`
- Refresh Endpoint: `https://us-central1-serendia.cloudfunctions.net/production-token-refresh`
- Procore OAuth: `https://login.procore.com/oauth/authorize`

## Support Contacts

- **Procore API Support:** https://developers.procore.com/
- **GCP Support:** https://cloud.google.com/support
- **Internal Team:** dylan@alamoinnovation.com

## Maintenance Schedule

**Weekly:**
- Review token refresh logs for errors
- Verify secret version counts (should be 1 per secret)

**Monthly:**
- Audit Cloud Function performance metrics
- Review Cloud Scheduler execution history
- Check for GCP service updates

**Quarterly:**
- Review and update client credentials if needed
- Audit IAM permissions
- Update documentation for any changes

## Recovery Procedures

### Complete Token Reset

If tokens are corrupted or lost:

```bash
# 1. Delete existing tokens
gcloud secrets delete procore-access-token-{env} --project=serendia
gcloud secrets delete procore-refresh-token-{env} --project=serendia

# 2. Recreate secrets
gcloud secrets create procore-access-token-{env} \
  --replication-policy="automatic" \
  --project=serendia

gcloud secrets create procore-refresh-token-{env} \
  --replication-policy="automatic" \
  --project=serendia

# 3. Re-authenticate via UI
# Visit: https://us-central1-serendia.cloudfunctions.net/{env}-token-manager
```

### Disaster Recovery

**Backup Configuration:**
- Client credentials stored in Secret Manager (backed up by GCP)
- Code stored in GitHub repository
- Infrastructure as code approach allows quick redeployment

**Recovery Steps:**
1. Redeploy functions from source code
2. Recreate scheduler jobs
3. Re-authenticate to obtain new tokens

**RTO (Recovery Time Objective):** < 30 minutes
**RPO (Recovery Point Objective):** Current tokens (may need re-auth)
