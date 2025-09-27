import os
import json
import logging
from datetime import datetime, timezone
from google.cloud import secretmanager
import requests
from typing import Dict, Optional
from urllib.parse import parse_qs, unquote

# Simple logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenManager:
    """Sandbox OAuth and token management service"""
    
    def __init__(self):
        self.environment = 'sandbox'
        self.project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'serendia')
        
        # Initialize Secret Manager client
        self.secret_client = secretmanager.SecretManagerServiceClient()
        
        # Get credentials from Secret Manager
        self.client_id = self._get_secret_value('procore-client-id-sandbox')
        self.client_secret = self._get_secret_value('procore-client-secret-sandbox')
        self.redirect_uri = self._get_secret_value('procore-redirect-uri-sandbox')

        # Debug logging
        logger.info(f"=== TOKENMANAGER INIT DEBUG ===")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"Project ID: {self.project_id}")
        logger.info(f"Client ID (from Secret Manager): {self.client_id[:10] if self.client_id else 'None'}...")
        logger.info(f"Client Secret exists: {bool(self.client_secret)}")
        logger.info(f"Client Secret length: {len(self.client_secret) if self.client_secret else 0}")
        logger.info(f"Redirect URI: {self.redirect_uri}")
        
        # Validate required credentials
        if not self.client_id:
            logger.error(f"No client ID found for sandbox environment")
        if not self.client_secret:
            logger.error(f"No client secret found for sandbox environment")
        if not self.redirect_uri:
            logger.error(f"No redirect URI found for sandbox environment")
        
        logger.info(f"TokenManager initialized: environment={self.environment}, project_id={self.project_id}")
                
        # Set OAuth base URL for sandbox
        self.oauth_base = 'https://login-sandbox.procore.com'
    
    def _get_secret_value(self, secret_name: str) -> Optional[str]:
        """Get secret value from Secret Manager"""
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.secret_client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("utf-8")
            logger.info(f"Successfully retrieved secret: {secret_name}")
            return secret_value
        except Exception as e:
            logger.warning(f"Failed to get secret {secret_name}: {e}")
            return None
    
    def get_oauth_url(self) -> str:
        """Generate OAuth authorization URL"""
        if not self.client_id:
            logger.error("Cannot generate OAuth URL - no client ID available")
            return "#"
        
        return f"{self.oauth_base}/oauth/authorize?client_id={self.client_id}&response_type=code&redirect_uri={self.redirect_uri}"
    
    def _get_secret_names(self) -> Dict[str, str]:
        """Get sandbox secret names"""
        return {
            'access_token': 'procore-access-token-sandbox',
            'refresh_token': 'procore-refresh-token-sandbox'
        }
    
    def exchange_code_for_tokens(self, authorization_code: str) -> Dict[str, any]:
        """Exchange authorization code for access and refresh tokens"""
        
        # Validate we have required credentials
        if not self.client_id or not self.client_secret:
            error_msg = f"Missing credentials for sandbox: client_id={bool(self.client_id)}, client_secret={bool(self.client_secret)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'environment': self.environment,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        url = f"{self.oauth_base}/oauth/token"
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': authorization_code,
            'redirect_uri': self.redirect_uri
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        # Debug logging
        logger.info(f"=== TOKEN EXCHANGE DEBUG ===")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"URL: {url}")
        logger.info(f"Authorization code: {authorization_code[:20]}...{authorization_code[-10:]}")
        logger.info(f"Code length: {len(authorization_code)}")
        
        try:
            logger.info(f"Exchanging authorization code for tokens (sandbox)")
            response = requests.post(url, data=data, headers=headers, timeout=30)

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data['access_token']
                refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 7200)
                
                # Store tokens in Secret Manager
                self._store_tokens(access_token, refresh_token)
                
                logger.info(f"OAuth successful - tokens stored in Secret Manager for sandbox")
                return {
                    'success': True,
                    'message': 'OAuth tokens exchanged and stored successfully for sandbox',
                    'environment': self.environment,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                error_msg = f"OAuth token exchange failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                
                # Enhanced debugging for 401 errors
                if response.status_code == 401:
                    logger.error("=== 401 DEBUGGING ===")
                    logger.error(f"Client ID from Secret Manager: {self.client_id}")
                    logger.error(f"Client Secret length: {len(self.client_secret)}")
                    logger.error(f"Redirect URI: {self.redirect_uri}")
                    logger.error(f"Environment: {self.environment}")
                
                return {
                    'success': False,
                    'error': error_msg,
                    'environment': self.environment,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            error_msg = f"Exception during OAuth token exchange: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'environment': self.environment,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def get_current_tokens(self) -> Dict[str, Optional[str]]:
        """Get current tokens from Secret Manager"""
        secret_names = self._get_secret_names()
        
        try:
            # Get access token
            access_name = f"projects/{self.project_id}/secrets/{secret_names['access_token']}/versions/latest"
            access_response = self.secret_client.access_secret_version(request={"name": access_name})
            access_token = access_response.payload.data.decode("utf-8")
            
            # Get refresh token
            refresh_name = f"projects/{self.project_id}/secrets/{secret_names['refresh_token']}/versions/latest"
            refresh_response = self.secret_client.access_secret_version(request={"name": refresh_name})
            refresh_token = refresh_response.payload.data.decode("utf-8")
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token
            }
        except Exception as e:
            logger.error(f"Failed to get tokens from Secret Manager for sandbox: {e}")
            return {'access_token': None, 'refresh_token': None}
    
    def refresh_access_token(self) -> Dict[str, any]:
        """Refresh access token using refresh token"""
        logger.info(f"Starting access token refresh process for sandbox")
        tokens = self.get_current_tokens()
        refresh_token = tokens.get('refresh_token')
        
        if not refresh_token:
            error_msg = 'No refresh token available for sandbox'
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'environment': self.environment,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        
        url = f"{self.oauth_base}/oauth/token"
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': refresh_token
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        try:
            logger.info(f"Refreshing Procore access token for sandbox")
            response = requests.post(url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                new_access_token = token_data['access_token']
                new_refresh_token = token_data.get('refresh_token', refresh_token)
                
                # Store new tokens in Secret Manager
                self._store_tokens(new_access_token, new_refresh_token)
                
                logger.info(f"Access token refresh successful for sandbox")
                return {
                    'success': True,
                    'environment': self.environment,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                error_msg = f"Access token refresh failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                
                return {
                    'success': False,
                    'error': error_msg,
                    'environment': self.environment,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
        except Exception as e:
            error_msg = f"Exception during access token refresh: {str(e)}"
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'environment': self.environment,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def _store_tokens(self, access_token: str, refresh_token: str):
        """Store tokens and immediately cleanup old versions to simulate replacement"""
        secret_names = self._get_secret_names()
        logger.info(f"Storing tokens in Secret Manager for sandbox")
        
        # Store new access token
        access_parent = f"projects/{self.project_id}/secrets/{secret_names['access_token']}"
        access_payload = {"data": access_token.encode("utf-8")}
        self.secret_client.add_secret_version(
            request={"parent": access_parent, "payload": access_payload}
        )
        
        # Store new refresh token
        refresh_parent = f"projects/{self.project_id}/secrets/{secret_names['refresh_token']}"
        refresh_payload = {"data": refresh_token.encode("utf-8")}
        self.secret_client.add_secret_version(
            request={"parent": refresh_parent, "payload": refresh_payload}
        )
        
        # Immediately destroy all old versions, keeping only the latest one
        self._destroy_old_versions(secret_names['access_token'], keep_latest=1)
        self._destroy_old_versions(secret_names['refresh_token'], keep_latest=1)
        
        logger.info(f"Tokens stored and old versions destroyed for sandbox")

    def _destroy_old_versions(self, secret_name: str, keep_latest: int = 1):
        """Destroy all but the most recent N versions of a secret"""
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            
            # List all versions
            versions = self.secret_client.list_secret_versions(
                request={"parent": secret_path}
            )
            
            # Get enabled versions and sort by creation time (newest first)
            enabled_versions = []
            for version in versions:
                if version.state == secretmanager.SecretVersion.State.ENABLED:
                    enabled_versions.append({
                        'name': version.name,
                        'create_time': version.create_time
                    })
            
            # Sort by creation time (newest first)
            enabled_versions.sort(key=lambda v: v['create_time'], reverse=True)
            
            # Destroy all but the most recent versions
            versions_to_destroy = enabled_versions[keep_latest:]
            
            for version in versions_to_destroy:
                try:
                    self.secret_client.destroy_secret_version(
                        request={"name": version['name']}
                    )
                    logger.debug(f"Destroyed old version: {version['name']}")
                except Exception as e:
                    logger.warning(f"Failed to destroy version {version['name']}: {e}")
            
            if versions_to_destroy:
                logger.info(f"Destroyed {len(versions_to_destroy)} old versions of {secret_name}")
                
        except Exception as e:
            logger.warning(f"Failed to cleanup old versions for {secret_name}: {e}")
            # Don't fail the main operation if cleanup fails

# Cloud Function entry points
def token_manager_handler(request):
    """HTTP Cloud Function handler for sandbox token management"""
    print("=== PRINT: HANDLER START ===")
    logger.info("=== HANDLER START ===")
    print("=== PRINT: Sandbox token manager handler started ===")
    logger.info("Sandbox token manager handler started")
    
    try:
        # Parse query parameters for OAuth callback
        code = None
        error = None
        
        print("=== PRINT: REQUEST ANALYSIS ===")
        logger.info("=== REQUEST ANALYSIS ===")
        # Debug request object
        print(f"PRINT: Request object type: {type(request)}")
        logger.info(f"Request object type: {type(request)}")
        print(f"PRINT: Request attributes: {dir(request)}")
        logger.info(f"Request attributes: {dir(request)}")
        print(f"PRINT: Request method: {getattr(request, 'method', 'Unknown')}")
        logger.info(f"Request method: {getattr(request, 'method', 'Unknown')}")
        
        # Parse URL parameters
        try:
            print("=== PRINT: URL PARSING ATTEMPT ===")
            
            # For Flask requests, use request.args directly (most reliable)
            if hasattr(request, 'args'):
                print(f"PRINT: Using request.args for parameter extraction")
                if 'code' in request.args:
                    code = request.args['code']
                    print(f"PRINT: OAuth code from request.args: {code[:20]}...{code[-10:] if len(code) > 10 else ''}")
                
                if 'error' in request.args:
                    error = request.args['error']
                    print(f"PRINT: OAuth error from request.args: {error}")
                
                # Debug: show all parameters
                args_dict = dict(request.args)
                print(f"PRINT: All request.args: {args_dict}")
            
            # Fallback: manual URL parsing (for debugging)
            elif hasattr(request, 'url') and '?' in str(request.url):
                print(f"PRINT: Fallback to manual URL parsing")
                url_str = str(request.url)
                query_part = url_str.split('?', 1)[1]
                print(f"PRINT: Query part: {query_part}")
                
                # Use proper URL parsing instead of manual string splitting
                query_params = parse_qs(query_part)
                print(f"PRINT: Parsed query params: {query_params}")
                
                # Extract and URL-decode parameters
                if 'code' in query_params:
                    code = query_params['code'][0]
                    print(f"PRINT: OAuth code found and decoded: {code[:20]}...{code[-10:]}")
                
                if 'error' in query_params:
                    error = query_params['error'][0]
                    print(f"PRINT: OAuth error found: {error}")
            else:
                print("PRINT: No URL parameters found - showing HTML interface")
                    
        except Exception as e:
            print(f"PRINT: URL parsing failed with exception: {e}")
            import traceback
            print(f"PRINT: Traceback: {traceback.format_exc()}")
        
        print(f"=== PRINT: AFTER PARSING: code={code is not None}, error={error} ===")
        logger.info(f"=== AFTER PARSING: code={code is not None}, error={error} ===")
        
        print(f"PRINT: Creating TokenManager for sandbox")
        logger.info(f"Creating TokenManager for sandbox")
        
        # Create TokenManager
        token_manager = TokenManager()
        logger.info(f"TokenManager created successfully")
        
        # Handle OAuth callback
        if error:
            logger.error(f"OAuth error received: {error}")
            return f'<html><body><h1>OAuth Error</h1><p>{error}</p></body></html>', 400
        
        if code:
            logger.info(f"=== PROCESSING OAUTH CALLBACK ===")
            logger.info(f"Processing OAuth callback for sandbox with code: {code[:20]}...{code[-10:]}")
            result = token_manager.exchange_code_for_tokens(code)
            
            if result['success']:
                return f'''<html><body>
                    <h1 style="color: #007bff">Authentication Successful! (SANDBOX)</h1>
                    <p>Tokens have been stored in Secret Manager for <strong>sandbox</strong> environment.</p>
                    <p>You can now close this window.</p>
                </body></html>'''
            else:
                return f'''<html><body>
                    <h1>Authentication Failed</h1>
                    <p>Error: {result.get('error', 'Unknown error')}</p>
                    <p>Environment: sandbox</p>
                </body></html>''', 500
        
        logger.info(f"=== SHOWING HTML INTERFACE (no code parameter) ===")
        # Show OAuth interface (no code parameter)
        # Get current tokens for display
        current_tokens = token_manager.get_current_tokens()
        access_token_preview = current_tokens['access_token'][:10] + '...' if current_tokens['access_token'] else 'None'
        refresh_token_preview = current_tokens['refresh_token'][:10] + '...' if current_tokens['refresh_token'] else 'None'
        
        return f'''<html><head>
            <title>Procore Sandbox Token Manager</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .button {{ 
                    padding: 15px 25px; 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 5px; 
                    font-size: 16px; 
                    display: inline-block; 
                    margin: 10px 5px;
                    border: none;
                    cursor: pointer;
                }}
                .auth-button {{ background-color: #007bff; }}
                .refresh-button {{ background-color: #28a745; }}
                .info {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .tokens {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 10px 0; font-family: monospace; }}
                .disclaimer {{ background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 10px 0; border-left: 4px solid #ffc107; }}
            </style>
            <script>
                async function refreshTokens() {{
                    const button = document.getElementById('refresh-btn');
                    button.disabled = true;
                    button.textContent = 'Refreshing...';
                    
                    try {{
                        const response = await fetch('https://us-central1-serendia.cloudfunctions.net/sandbox-token-refresh', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }}
                        }});
                        
                        const result = await response.json();
                        
                        if (result.status === 'success') {{
                            alert('✅ Tokens refreshed successfully! Refresh this page to see updated tokens.');
                        }} else {{
                            alert('❌ Token refresh failed: ' + result.message);
                        }}
                    }} catch (error) {{
                        alert('❌ Error calling refresh service: ' + error.message);
                    }} finally {{
                        button.disabled = false;
                        button.textContent = 'Manual Refresh Tokens';
                    }}
                }}
            </script>
        </head><body>
            <h1>Procore Sandbox Token Manager</h1>
            
            <div class="info">
                <h3 style="color: #007bff">Authentication</h3>
                <a href="{token_manager.get_oauth_url()}" class="button auth-button">
                    🔐 Authenticate with Procore
                </a>
            </div>
            
            <div class="info">
                <h3 style="color: #28a745">Current Tokens</h3>
                <div class="tokens">
                    <strong>Access Token:</strong> {access_token_preview}<br>
                    <strong>Refresh Token:</strong> {refresh_token_preview}
                </div>
                
                <button id="refresh-btn" onclick="refreshTokens()" class="button refresh-button">
                    🔄 Manual Refresh Tokens
                </button>
            </div>
            
            <div class="disclaimer">
                <h4>⚡ Automated Token Management</h4>
                <p>The <code>sandbox-token-refresh</code> service automatically handles access token refresh <strong>every 5 minutes</strong>. 
                Manual refresh is only needed for testing or immediate token updates.</p>
            </div>
        </body></html>'''
        
    except Exception as e:
        error_msg = f"Handler error: {str(e)}"
        logger.error(error_msg)
        
        return f'''<html><body>
            <h1>Function Error</h1>
            <p>Error: {error_msg}</p>
            <p>Check Cloud Functions logs for details.</p>
        </body></html>''', 500

def scheduled_refresh_handler(request):
    """HTTP Cloud Function handler for scheduled token refresh"""
    logger.info("Scheduled token refresh started")
    
    try:
        # Parse request method and body for debugging
        method = request.method
        logger.info(f"Request method: {method}")
        
        # Handle both GET (for testing) and POST (for scheduler)
        if method not in ['GET', 'POST']:
            return {'status': 'error', 'message': 'Method not allowed'}, 405
        
        # Create TokenManager and refresh tokens
        token_manager = TokenManager()
        logger.info("TokenManager created for scheduled refresh")
        
        # Perform the refresh
        result = token_manager.refresh_access_token()
        
        if result['success']:
            logger.info("Scheduled token refresh completed successfully")
            return {
                'status': 'success',
                'message': 'Access token refreshed successfully',
                'timestamp': result.get('timestamp'),
                'environment': 'sandbox'
            }
        else:
            logger.error(f"Scheduled token refresh failed: {result.get('error')}")
            return {
                'status': 'error',
                'message': 'Access token refresh failed',
                'error': result.get('error'),
                'timestamp': result.get('timestamp'),
                'environment': 'sandbox'
            }, 500
            
    except Exception as e:
        error_msg = f"Scheduled refresh handler error: {str(e)}"
        logger.error(error_msg)
        
        return {
            'status': 'error',
            'message': 'Exception during scheduled refresh',
            'error': error_msg,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }, 500
