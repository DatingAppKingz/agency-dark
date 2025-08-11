/**
 * OAuth Security E2E Tests
 * Tests security aspects of OAuth implementation
 */

import { test, expect, Page } from '@playwright/test';
import crypto from 'crypto';

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const API_URL = process.env.API_URL || 'http://localhost:8000';

test.describe('OAuth Security Tests', () => {
  test('PKCE implementation', async ({ page }) => {
    // Intercept OAuth authorization request
    let authUrl: string = '';
    await page.route('**/oauth/authorize**', async (route) => {
      authUrl = route.request().url();
      await route.continue();
    });
    
    // Start OAuth flow
    await page.goto(`${BASE_URL}/login`);
    await page.click('[data-testid="oauth-google"]');
    
    // Verify PKCE parameters
    const url = new URL(authUrl);
    const codeChallenge = url.searchParams.get('code_challenge');
    const codeChallengeMethod = url.searchParams.get('code_challenge_method');
    
    expect(codeChallenge).toBeTruthy();
    expect(codeChallenge?.length).toBeGreaterThanOrEqual(43); // Base64 URL encoded
    expect(codeChallengeMethod).toBe('S256');
  });

  test('State parameter validation', async ({ page }) => {
    // Start OAuth flow and capture state
    await page.goto(`${BASE_URL}/login`);
    
    let stateParam: string | null = null;
    await page.route('**/*', async (route) => {
      const url = new URL(route.request().url());
      if (url.searchParams.has('state')) {
        stateParam = url.searchParams.get('state');
      }
      await route.continue();
    });
    
    await page.click('[data-testid="oauth-google"]');
    
    // Verify state parameter exists and is secure
    expect(stateParam).toBeTruthy();
    expect(stateParam?.length).toBeGreaterThanOrEqual(32);
    
    // Try callback with invalid state
    await page.goto(`${BASE_URL}/auth/callback?code=test_code&state=invalid_state`);
    
    // Should show error
    await expect(page.locator('[data-testid="state-mismatch-error"]')).toBeVisible();
  });

  test('CSRF protection', async ({ page }) => {
    // Get initial CSRF token
    await page.goto(`${BASE_URL}/login`);
    const csrfToken = await page.evaluate(() => {
      return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    });
    
    expect(csrfToken).toBeTruthy();
    
    // Verify CSRF token is included in OAuth requests
    let hasCSRFHeader = false;
    await page.route('**/oauth/**', async (route) => {
      const headers = route.request().headers();
      if (headers['x-csrf-token'] === csrfToken) {
        hasCSRFHeader = true;
      }
      await route.continue();
    });
    
    await page.click('[data-testid="oauth-google"]');
    
    expect(hasCSRFHeader).toBeTruthy();
  });

  test('Token storage security', async ({ page, context }) => {
    // Login with OAuth
    await page.goto(`${BASE_URL}/login`);
    await page.click('[data-testid="oauth-google"]');
    
    // Mock successful callback
    await page.goto(`${BASE_URL}/auth/callback?code=test_code&state=valid_state`);
    
    // Check token storage
    const localStorage = await page.evaluate(() => {
      return Object.keys(window.localStorage);
    });
    
    const sessionStorage = await page.evaluate(() => {
      return Object.keys(window.sessionStorage);
    });
    
    // Tokens should not be in localStorage
    expect(localStorage).not.toContain('access_token');
    expect(localStorage).not.toContain('refresh_token');
    
    // Check for httpOnly cookies
    const cookies = await context.cookies();
    const sessionCookie = cookies.find(c => c.name === 'session' || c.name === 'auth_token');
    
    if (sessionCookie) {
      expect(sessionCookie.httpOnly).toBeTruthy();
      expect(sessionCookie.secure).toBeTruthy(); // In production
      expect(sessionCookie.sameSite).toBe('Strict');
    }
  });

  test('Authorization code reuse prevention', async ({ page }) => {
    const authCode = 'test_auth_code_123';
    
    // First token exchange (should succeed)
    const response1 = await page.request.post(`${API_URL}/oauth/token`, {
      data: {
        grant_type: 'authorization_code',
        code: authCode,
        client_id: 'test_client',
        code_verifier: 'test_verifier',
      },
    });
    
    expect(response1.status()).toBe(200);
    
    // Second token exchange with same code (should fail)
    const response2 = await page.request.post(`${API_URL}/oauth/token`, {
      data: {
        grant_type: 'authorization_code',
        code: authCode,
        client_id: 'test_client',
        code_verifier: 'test_verifier',
      },
    });
    
    expect(response2.status()).toBe(400);
    const error = await response2.json();
    expect(error.error).toBe('invalid_grant');
  });

  test('Token expiration handling', async ({ page }) => {
    // Login
    await page.goto(`${BASE_URL}/login`);
    await page.click('[data-testid="oauth-google"]');
    await page.goto(`${BASE_URL}/auth/callback?code=test_code&state=valid_state`);
    
    // Wait for token to expire (mock with short expiry)
    await page.evaluate(() => {
      // Simulate expired token
      const event = new CustomEvent('token-expired');
      window.dispatchEvent(event);
    });
    
    // Try to access protected resource
    const response = await page.request.get(`${API_URL}/api/v1/me`);
    
    // Should get 401
    expect(response.status()).toBe(401);
    
    // Page should handle token refresh automatically
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Wait for refresh
    await page.waitForResponse(response => 
      response.url().includes('/token/refresh') && response.status() === 200
    );
    
    // Should be able to access dashboard
    await expect(page.locator('[data-testid="dashboard"]')).toBeVisible();
  });

  test('Redirect URI validation', async ({ page }) => {
    // Try OAuth with invalid redirect URI
    const maliciousRedirect = 'http://evil.com/callback';
    
    const response = await page.request.get(`${API_URL}/oauth/authorize`, {
      params: {
        client_id: 'test_client',
        response_type: 'code',
        redirect_uri: maliciousRedirect,
        scope: 'read',
      },
    });
    
    expect(response.status()).toBe(400);
    const error = await response.json();
    expect(error.error).toBe('invalid_redirect_uri');
  });

  test('Scope validation', async ({ page }) => {
    // Request invalid scope
    const response = await page.request.get(`${API_URL}/oauth/authorize`, {
      params: {
        client_id: 'test_client',
        response_type: 'code',
        redirect_uri: 'http://localhost:3000/callback',
        scope: 'admin delete_everything super_user',
      },
    });
    
    // Should reject invalid scopes
    expect(response.status()).toBe(400);
    const error = await response.json();
    expect(error.error).toBe('invalid_scope');
  });

  test('Rate limiting on token endpoint', async ({ page }) => {
    const attempts = 10;
    const responses = [];
    
    // Make rapid requests
    for (let i = 0; i < attempts; i++) {
      const response = await page.request.post(`${API_URL}/oauth/token`, {
        data: {
          grant_type: 'authorization_code',
          code: `invalid_code_${i}`,
          client_id: 'test_client',
        },
      });
      responses.push(response.status());
    }
    
    // Should hit rate limit
    const rateLimited = responses.some(status => status === 429);
    expect(rateLimited).toBeTruthy();
  });

  test('Client authentication', async ({ page }) => {
    // Try token exchange without client credentials
    const response = await page.request.post(`${API_URL}/oauth/token`, {
      data: {
        grant_type: 'authorization_code',
        code: 'test_code',
      },
    });
    
    expect(response.status()).toBe(401);
    const error = await response.json();
    expect(error.error).toBe('invalid_client');
  });

  test('Token revocation security', async ({ page }) => {
    // Get token first
    await page.goto(`${BASE_URL}/login`);
    await page.click('[data-testid="oauth-google"]');
    await page.goto(`${BASE_URL}/auth/callback?code=test_code&state=valid_state`);
    
    // Get token from storage
    const token = await page.evaluate(() => {
      return sessionStorage.getItem('access_token');
    });
    
    // Revoke token
    const revokeResponse = await page.request.post(`${API_URL}/oauth/revoke`, {
      data: {
        token: token,
        token_type_hint: 'access_token',
      },
    });
    
    expect(revokeResponse.status()).toBe(200);
    
    // Try to use revoked token
    const meResponse = await page.request.get(`${API_URL}/api/v1/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    expect(meResponse.status()).toBe(401);
  });

  test('Clickjacking protection', async ({ page }) => {
    // Check for X-Frame-Options header
    const response = await page.goto(`${BASE_URL}/oauth/authorize`);
    const headers = response?.headers();
    
    expect(headers?.['x-frame-options']).toMatch(/DENY|SAMEORIGIN/i);
    
    // Try to load in iframe
    await page.setContent(`
      <iframe src="${BASE_URL}/oauth/authorize"></iframe>
    `);
    
    // Should not load in iframe
    const iframe = page.frameLocator('iframe');
    await expect(iframe.locator('body')).not.toBeVisible();
  });

  test('Secure headers validation', async ({ page }) => {
    const response = await page.goto(`${BASE_URL}/login`);
    const headers = response?.headers();
    
    // Check security headers
    expect(headers?.['strict-transport-security']).toBeTruthy();
    expect(headers?.['x-content-type-options']).toBe('nosniff');
    expect(headers?.['x-frame-options']).toBeTruthy();
    expect(headers?.['content-security-policy']).toBeTruthy();
  });

  test('JWT signature validation', async ({ page }) => {
    // Get a valid token
    const validTokenResponse = await page.request.post(`${API_URL}/oauth/token`, {
      data: {
        grant_type: 'client_credentials',
        client_id: 'test_client',
        client_secret: 'test_secret',
      },
    });
    
    const { access_token } = await validTokenResponse.json();
    
    // Tamper with token (change payload)
    const [header, payload, signature] = access_token.split('.');
    const decodedPayload = JSON.parse(Buffer.from(payload, 'base64').toString());
    decodedPayload.scope = 'admin';
    const tamperedPayload = Buffer.from(JSON.stringify(decodedPayload)).toString('base64');
    const tamperedToken = `${header}.${tamperedPayload}.${signature}`;
    
    // Try to use tampered token
    const response = await page.request.get(`${API_URL}/api/v1/me`, {
      headers: {
        'Authorization': `Bearer ${tamperedToken}`,
      },
    });
    
    expect(response.status()).toBe(401);
  });
});

test.describe('OAuth Compliance Tests', () => {
  test('RFC 6749 compliance - Authorization Code Grant', async ({ page }) => {
    // Test all required parameters
    const authResponse = await page.request.get(`${API_URL}/oauth/authorize`, {
      params: {
        response_type: 'code',
        client_id: 'test_client',
        redirect_uri: 'http://localhost:3000/callback',
      },
    });
    
    expect(authResponse.status()).toBe(200);
    
    // Missing required parameter
    const errorResponse = await page.request.get(`${API_URL}/oauth/authorize`, {
      params: {
        response_type: 'code',
        // Missing client_id
        redirect_uri: 'http://localhost:3000/callback',
      },
    });
    
    expect(errorResponse.status()).toBe(400);
  });

  test('RFC 7636 compliance - PKCE', async ({ page }) => {
    // Generate PKCE challenge
    const verifier = crypto.randomBytes(32).toString('base64url');
    const challenge = crypto
      .createHash('sha256')
      .update(verifier)
      .digest('base64url');
    
    // Authorization request with PKCE
    const authResponse = await page.request.get(`${API_URL}/oauth/authorize`, {
      params: {
        response_type: 'code',
        client_id: 'test_client',
        redirect_uri: 'http://localhost:3000/callback',
        code_challenge: challenge,
        code_challenge_method: 'S256',
      },
    });
    
    expect(authResponse.status()).toBe(200);
    
    // Token exchange with verifier
    const tokenResponse = await page.request.post(`${API_URL}/oauth/token`, {
      data: {
        grant_type: 'authorization_code',
        code: 'test_code',
        client_id: 'test_client',
        code_verifier: verifier,
      },
    });
    
    expect(tokenResponse.status()).toBe(200);
  });

  test('OpenID Connect compliance', async ({ page }) => {
    // Request with OpenID scope
    const response = await page.request.get(`${API_URL}/oauth/authorize`, {
      params: {
        response_type: 'code',
        client_id: 'test_client',
        redirect_uri: 'http://localhost:3000/callback',
        scope: 'openid email profile',
      },
    });
    
    expect(response.status()).toBe(200);
    
    // Token response should include id_token
    const tokenResponse = await page.request.post(`${API_URL}/oauth/token`, {
      data: {
        grant_type: 'authorization_code',
        code: 'test_code',
        client_id: 'test_client',
        client_secret: 'test_secret',
      },
    });
    
    const tokens = await tokenResponse.json();
    expect(tokens.id_token).toBeTruthy();
  });
});

export default {};