"""
OAuth2 Discovery and Metadata Endpoints.
Implements RFC 8414 OAuth 2.0 Authorization Server Metadata.
"""
from typing import Dict, Any, List
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from oauth.config import oauth_config

router = APIRouter(tags=["OAuth2 Discovery"])


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata(request: Request) -> JSONResponse:
    """
    OAuth 2.0 Authorization Server Metadata.
    Returns metadata about the OAuth2 authorization server.
    RFC 8414 compliant.
    """
    base_url = str(request.base_url).rstrip("/")
    
    metadata = {
        "issuer": oauth_config.ISSUER,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "token_endpoint_auth_methods_supported": oauth_config.TOKEN_ENDPOINT_AUTH_METHODS,
        "token_endpoint_auth_signing_alg_values_supported": ["RS256", "HS256"],
        "userinfo_endpoint": f"{base_url}/oauth/userinfo",
        "jwks_uri": f"{base_url}/.well-known/jwks.json",
        "registration_endpoint": f"{base_url}/oauth/register",
        "scopes_supported": list(oauth_config.SUPPORTED_SCOPES.keys()),
        "response_types_supported": oauth_config.SUPPORTED_RESPONSE_TYPES,
        "response_modes_supported": oauth_config.SUPPORTED_RESPONSE_MODES,
        "grant_types_supported": oauth_config.SUPPORTED_GRANT_TYPES,
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "claims_supported": [
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "jti",
            "email",
            "email_verified",
            "name",
            "picture",
            "agency_id",
            "role",
            "permissions"
        ],
        "code_challenge_methods_supported": oauth_config.PKCE_METHODS_SUPPORTED if oauth_config.REQUIRE_PKCE else [],
        "introspection_endpoint": f"{base_url}/oauth/introspect",
        "introspection_endpoint_auth_methods_supported": oauth_config.TOKEN_ENDPOINT_AUTH_METHODS,
        "revocation_endpoint": f"{base_url}/oauth/revoke",
        "revocation_endpoint_auth_methods_supported": oauth_config.TOKEN_ENDPOINT_AUTH_METHODS,
        "service_documentation": f"{base_url}/docs",
        "ui_locales_supported": ["en-US"],
        "op_policy_uri": f"{base_url}/policy",
        "op_tos_uri": f"{base_url}/terms",
        "authorization_response_iss_parameter_supported": True,
        "backchannel_logout_supported": False,
        "backchannel_logout_session_supported": False,
        "frontchannel_logout_supported": False,
        "frontchannel_logout_session_supported": False,
        "end_session_endpoint": f"{base_url}/oauth/logout",
        "check_session_iframe": f"{base_url}/oauth/check-session",
        "require_request_uri_registration": False,
        "request_parameter_supported": True,
        "request_uri_parameter_supported": False,
        "pushed_authorization_request_endpoint": f"{base_url}/oauth/par",
        "require_pushed_authorization_requests": False,
        "dpop_signing_alg_values_supported": ["RS256", "ES256"],
        "authorization_signing_alg_values_supported": ["RS256", "ES256"],
        "authorization_encryption_alg_values_supported": ["RSA-OAEP", "RSA-OAEP-256"],
        "authorization_encryption_enc_values_supported": ["A128CBC-HS256", "A192CBC-HS384", "A256CBC-HS512"]
    }
    
    return JSONResponse(content=metadata)


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request) -> JSONResponse:
    """
    OpenID Connect Discovery Document.
    Returns OpenID Connect provider configuration.
    """
    base_url = str(request.base_url).rstrip("/")
    
    config = {
        "issuer": oauth_config.ISSUER,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "userinfo_endpoint": f"{base_url}/oauth/userinfo",
        "jwks_uri": f"{base_url}/.well-known/jwks.json",
        "registration_endpoint": f"{base_url}/oauth/register",
        "scopes_supported": ["openid", "profile", "email", "offline_access"] + list(oauth_config.SUPPORTED_SCOPES.keys()),
        "response_types_supported": oauth_config.SUPPORTED_RESPONSE_TYPES,
        "response_modes_supported": oauth_config.SUPPORTED_RESPONSE_MODES,
        "grant_types_supported": oauth_config.SUPPORTED_GRANT_TYPES,
        "acr_values_supported": [],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "id_token_encryption_alg_values_supported": ["RSA-OAEP", "RSA-OAEP-256"],
        "id_token_encryption_enc_values_supported": ["A128CBC-HS256", "A192CBC-HS384", "A256CBC-HS512"],
        "userinfo_signing_alg_values_supported": ["RS256"],
        "userinfo_encryption_alg_values_supported": ["RSA-OAEP", "RSA-OAEP-256"],
        "userinfo_encryption_enc_values_supported": ["A128CBC-HS256", "A192CBC-HS384", "A256CBC-HS512"],
        "request_object_signing_alg_values_supported": ["RS256", "ES256"],
        "request_object_encryption_alg_values_supported": ["RSA-OAEP", "RSA-OAEP-256"],
        "request_object_encryption_enc_values_supported": ["A128CBC-HS256", "A192CBC-HS384", "A256CBC-HS512"],
        "token_endpoint_auth_methods_supported": oauth_config.TOKEN_ENDPOINT_AUTH_METHODS,
        "token_endpoint_auth_signing_alg_values_supported": ["RS256", "HS256"],
        "display_values_supported": ["page", "popup", "touch", "wap"],
        "claim_types_supported": ["normal"],
        "claims_supported": [
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "auth_time",
            "nonce",
            "acr",
            "amr",
            "azp",
            "email",
            "email_verified",
            "name",
            "given_name",
            "family_name",
            "middle_name",
            "nickname",
            "preferred_username",
            "profile",
            "picture",
            "website",
            "gender",
            "birthdate",
            "zoneinfo",
            "locale",
            "phone_number",
            "phone_number_verified",
            "address",
            "updated_at",
            "agency_id",
            "role",
            "permissions"
        ],
        "service_documentation": f"{base_url}/docs",
        "claims_locales_supported": ["en-US"],
        "ui_locales_supported": ["en-US"],
        "claims_parameter_supported": False,
        "request_parameter_supported": True,
        "request_uri_parameter_supported": False,
        "require_request_uri_registration": False,
        "op_policy_uri": f"{base_url}/policy",
        "op_tos_uri": f"{base_url}/terms",
        "check_session_iframe": f"{base_url}/oauth/check-session",
        "end_session_endpoint": f"{base_url}/oauth/logout",
        "introspection_endpoint": f"{base_url}/oauth/introspect",
        "introspection_endpoint_auth_methods_supported": oauth_config.TOKEN_ENDPOINT_AUTH_METHODS,
        "revocation_endpoint": f"{base_url}/oauth/revoke",
        "revocation_endpoint_auth_methods_supported": oauth_config.TOKEN_ENDPOINT_AUTH_METHODS,
        "code_challenge_methods_supported": oauth_config.PKCE_METHODS_SUPPORTED if oauth_config.REQUIRE_PKCE else [],
        "backchannel_logout_supported": False,
        "backchannel_logout_session_supported": False,
        "frontchannel_logout_supported": False,
        "frontchannel_logout_session_supported": False
    }
    
    return JSONResponse(content=config)


@router.get("/.well-known/jwks.json")
async def jwks(request: Request) -> JSONResponse:
    """
    JSON Web Key Set (JWKS) endpoint.
    Returns the public keys used for signing tokens.
    """
    # In production, this would return actual RSA/EC public keys
    # For now, return a placeholder
    keys = {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": "1",
                "alg": "RS256",
                "n": "placeholder_modulus",  # Base64url-encoded modulus
                "e": "AQAB"  # Base64url-encoded exponent (65537)
            }
        ]
    }
    
    return JSONResponse(content=keys)


@router.get("/oauth/scopes")
async def list_scopes() -> JSONResponse:
    """
    List all available OAuth scopes.
    Custom endpoint for scope discovery.
    """
    scopes = []
    for scope_name, description in oauth_config.SUPPORTED_SCOPES.items():
        scopes.append({
            "name": scope_name,
            "description": description,
            "default": scope_name in oauth_config.DEFAULT_SCOPES
        })
    
    return JSONResponse(content={"scopes": scopes})


@router.get("/oauth/grants")
async def list_grant_types() -> JSONResponse:
    """
    List supported OAuth grant types.
    Custom endpoint for grant type discovery.
    """
    grants = []
    grant_descriptions = {
        "authorization_code": "Authorization Code Grant - Standard OAuth2 flow with authorization code",
        "refresh_token": "Refresh Token Grant - Exchange refresh token for new access token",
        "client_credentials": "Client Credentials Grant - Machine-to-machine authentication",
        "password": "Password Grant - Direct username/password authentication (legacy support)"
    }
    
    for grant_type in oauth_config.SUPPORTED_GRANT_TYPES:
        grants.append({
            "type": grant_type,
            "description": grant_descriptions.get(grant_type, f"OAuth2 {grant_type} grant"),
            "pkce_required": grant_type == "authorization_code" and oauth_config.REQUIRE_PKCE
        })
    
    return JSONResponse(content={"grant_types": grants})


@router.get("/oauth/response-types")
async def list_response_types() -> JSONResponse:
    """
    List supported OAuth response types.
    Custom endpoint for response type discovery.
    """
    response_types = []
    type_descriptions = {
        "code": "Authorization Code - Returns authorization code for token exchange",
        "token": "Implicit Grant - Returns access token directly (not recommended)",
        "id_token": "OpenID Connect - Returns ID token",
        "code id_token": "Hybrid Flow - Returns both code and ID token"
    }
    
    for response_type in oauth_config.SUPPORTED_RESPONSE_TYPES:
        response_types.append({
            "type": response_type,
            "description": type_descriptions.get(response_type, f"OAuth2 {response_type} response"),
            "recommended": response_type == "code"
        })
    
    return JSONResponse(content={"response_types": response_types})


@router.get("/oauth/client-auth-methods")
async def list_client_auth_methods() -> JSONResponse:
    """
    List supported client authentication methods.
    Custom endpoint for client authentication discovery.
    """
    methods = []
    method_descriptions = {
        "client_secret_basic": "HTTP Basic Authentication with client credentials",
        "client_secret_post": "Client credentials in POST body",
        "client_secret_jwt": "JWT signed with client secret",
        "private_key_jwt": "JWT signed with private key",
        "none": "No authentication (public clients with PKCE)"
    }
    
    for method in oauth_config.TOKEN_ENDPOINT_AUTH_METHODS:
        methods.append({
            "method": method,
            "description": method_descriptions.get(method, f"Client authentication via {method}"),
            "public_client": method == "none"
        })
    
    return JSONResponse(content={"authentication_methods": methods})