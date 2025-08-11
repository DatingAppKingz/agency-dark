/**
 * E2E Tests for OAuth Implementation
 * Tests complete user journeys through OAuth flows
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';
import { v4 as uuidv4 } from 'uuid';

// Test configuration
const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';
const API_URL = process.env.API_URL || 'http://localhost:8000';

// Test data
const testUser = {
  email: 'test@example.com',
  password: 'Test123!',
  username: 'testuser',
};

const testAgency = {
  name: 'Test Agency',
  subdomain: 'test',
};

// Helper functions
async function login(page: Page, email: string, password: string) {
  await page.goto(`${BASE_URL}/login`);
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  await page.waitForURL(`${BASE_URL}/dashboard`);
}

async function logout(page: Page) {
  await page.click('[data-testid="user-menu"]');
  await page.click('[data-testid="logout-button"]');
  await page.waitForURL(`${BASE_URL}/login`);
}

// Test suites
test.describe('OAuth User Journey', () => {
  let context: BrowserContext;
  let page: Page;

  test.beforeEach(async ({ browser }) => {
    context = await browser.newContext();
    page = await context.newPage();
  });

  test.afterEach(async () => {
    await context.close();
  });

  test('Complete OAuth registration flow', async () => {
    // Navigate to registration
    await page.goto(`${BASE_URL}/register`);
    
    // Click OAuth login with Google
    await page.click('[data-testid="oauth-google"]');
    
    // Should redirect to OAuth provider
    await expect(page).toHaveURL(/accounts\.google\.com/);
    
    // Mock OAuth callback (in real test, would complete provider login)
    const callbackUrl = `${BASE_URL}/auth/callback?code=test_code&state=test_state`;
    await page.goto(callbackUrl);
    
    // Should process callback and redirect to dashboard
    await page.waitForURL(`${BASE_URL}/dashboard`);
    
    // Verify user is logged in
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
  });

  test('OAuth login for existing user', async () => {
    // Navigate to login
    await page.goto(`${BASE_URL}/login`);
    
    // Click OAuth login
    await page.click('[data-testid="oauth-google"]');
    
    // Mock OAuth callback
    const callbackUrl = `${BASE_URL}/auth/callback?code=test_code&state=test_state`;
    await page.goto(callbackUrl);
    
    // Should redirect to dashboard
    await page.waitForURL(`${BASE_URL}/dashboard`);
    
    // Verify user session
    const cookies = await context.cookies();
    const sessionCookie = cookies.find(c => c.name === 'session');
    expect(sessionCookie).toBeDefined();
  });

  test('Link additional OAuth account', async () => {
    // Login with regular credentials
    await login(page, testUser.email, testUser.password);
    
    // Navigate to settings
    await page.goto(`${BASE_URL}/settings/linked-accounts`);
    
    // Click to add Instagram
    await page.click('[data-testid="add-provider-instagram"]');
    
    // Should open OAuth flow
    await expect(page).toHaveURL(/api\.instagram\.com/);
    
    // Mock callback
    await page.goto(`${BASE_URL}/auth/callback?provider=instagram&code=test_code`);
    
    // Should return to settings
    await page.waitForURL(`${BASE_URL}/settings/linked-accounts`);
    
    // Verify account is linked
    await expect(page.locator('[data-testid="linked-instagram"]')).toBeVisible();
  });

  test('Unlink OAuth account', async () => {
    // Login and navigate to settings
    await login(page, testUser.email, testUser.password);
    await page.goto(`${BASE_URL}/settings/linked-accounts`);
    
    // Click unlink for a provider
    await page.click('[data-testid="unlink-google"]');
    
    // Confirm in dialog
    await page.click('[data-testid="confirm-unlink"]');
    
    // Wait for removal
    await page.waitForSelector('[data-testid="linked-google"]', { state: 'hidden' });
    
    // Verify account is unlinked
    await expect(page.locator('[data-testid="linked-google"]')).not.toBeVisible();
  });

  test('OAuth consent flow', async () => {
    // Navigate to OAuth authorization
    const authUrl = `${BASE_URL}/oauth/authorize?client_id=test_client&response_type=code&redirect_uri=${encodeURIComponent('http://example.com/callback')}&scope=read write`;
    await page.goto(authUrl);
    
    // Should show consent screen
    await expect(page.locator('h1')).toContainText('Authorize Application');
    
    // Verify scopes are displayed
    await expect(page.locator('[data-testid="scope-read"]')).toBeVisible();
    await expect(page.locator('[data-testid="scope-write"]')).toBeVisible();
    
    // Approve consent
    await page.click('[data-testid="approve-consent"]');
    
    // Should redirect with authorization code
    await page.waitForURL(/code=/);
    const url = new URL(page.url());
    expect(url.searchParams.get('code')).toBeTruthy();
  });
});

test.describe('OAuth Token Lifecycle', () => {
  let page: Page;

  test.beforeEach(async ({ page: p }) => {
    page = p;
  });

  test('Token refresh on expiration', async () => {
    // Login with OAuth
    await page.goto(`${BASE_URL}/login`);
    await page.click('[data-testid="oauth-google"]');
    
    // Mock expired token response
    await page.route('**/api/v1/me', async (route) => {
      await route.fulfill({
        status: 401,
        json: { error: 'token_expired' },
      });
    });
    
    // Navigate to protected page
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Should automatically refresh token
    await page.waitForResponse(response => 
      response.url().includes('/token/refresh') && response.status() === 200
    );
    
    // Page should load successfully
    await expect(page.locator('[data-testid="dashboard"]')).toBeVisible();
  });

  test('Logout revokes tokens', async () => {
    // Login
    await login(page, testUser.email, testUser.password);
    
    // Intercept logout request
    const logoutPromise = page.waitForResponse(
      response => response.url().includes('/logout') && response.status() === 200
    );
    
    // Logout
    await logout(page);
    
    // Wait for logout completion
    await logoutPromise;
    
    // Try to access protected route
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Should redirect to login
    await page.waitForURL(`${BASE_URL}/login`);
  });

  test('Multiple concurrent sessions', async ({ browser }) => {
    // Create two contexts (simulating different devices)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();
    
    const page1 = await context1.newPage();
    const page2 = await context2.newPage();
    
    // Login on both devices
    await login(page1, testUser.email, testUser.password);
    await login(page2, testUser.email, testUser.password);
    
    // Both should have access
    await page1.goto(`${BASE_URL}/dashboard`);
    await page2.goto(`${BASE_URL}/dashboard`);
    
    await expect(page1.locator('[data-testid="dashboard"]')).toBeVisible();
    await expect(page2.locator('[data-testid="dashboard"]')).toBeVisible();
    
    // Logout from one device
    await logout(page1);
    
    // Other device should still have access
    await page2.reload();
    await expect(page2.locator('[data-testid="dashboard"]')).toBeVisible();
    
    // Cleanup
    await context1.close();
    await context2.close();
  });
});

test.describe('OAuth Provider Flows', () => {
  test('Google OAuth flow', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    
    // Click Google login
    await page.click('[data-testid="oauth-google"]');
    
    // Verify redirect to Google
    await expect(page).toHaveURL(/accounts\.google\.com/);
    
    // Verify required parameters
    const url = new URL(page.url());
    expect(url.searchParams.get('client_id')).toBeTruthy();
    expect(url.searchParams.get('redirect_uri')).toBeTruthy();
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('scope')).toContain('openid');
    expect(url.searchParams.get('scope')).toContain('email');
    expect(url.searchParams.get('scope')).toContain('profile');
  });

  test('Instagram OAuth flow', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    
    // Click Instagram login
    await page.click('[data-testid="oauth-instagram"]');
    
    // Verify redirect to Instagram/Facebook
    await expect(page).toHaveURL(/api\.instagram\.com|facebook\.com/);
    
    // Verify required parameters
    const url = new URL(page.url());
    expect(url.searchParams.get('client_id')).toBeTruthy();
    expect(url.searchParams.get('redirect_uri')).toBeTruthy();
    expect(url.searchParams.get('response_type')).toBe('code');
  });

  test('Microsoft OAuth flow', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`);
    
    // Click Microsoft login
    await page.click('[data-testid="oauth-microsoft"]');
    
    // Verify redirect to Microsoft
    await expect(page).toHaveURL(/login\.microsoftonline\.com/);
    
    // Verify required parameters
    const url = new URL(page.url());
    expect(url.searchParams.get('client_id')).toBeTruthy();
    expect(url.searchParams.get('redirect_uri')).toBeTruthy();
    expect(url.searchParams.get('response_type')).toBe('code');
    expect(url.searchParams.get('scope')).toContain('openid');
  });
});

test.describe('OAuth Error Handling', () => {
  test('Handle OAuth provider error', async ({ page }) => {
    // Navigate to callback with error
    await page.goto(`${BASE_URL}/auth/callback?error=access_denied&error_description=User denied access`);
    
    // Should show error message
    await expect(page.locator('[data-testid="oauth-error"]')).toBeVisible();
    await expect(page.locator('[data-testid="oauth-error"]')).toContainText('access denied');
    
    // Should redirect to login
    await page.waitForURL(`${BASE_URL}/login`);
  });

  test('Handle invalid authorization code', async ({ page }) => {
    // Mock invalid code response
    await page.route('**/oauth/token', async (route) => {
      await route.fulfill({
        status: 400,
        json: { error: 'invalid_grant' },
      });
    });
    
    // Navigate to callback with code
    await page.goto(`${BASE_URL}/auth/callback?code=invalid_code&state=test_state`);
    
    // Should show error
    await expect(page.locator('[data-testid="oauth-error"]')).toBeVisible();
  });

  test('Handle network error during OAuth', async ({ page }) => {
    // Simulate network error
    await page.route('**/oauth/**', async (route) => {
      await route.abort('failed');
    });
    
    await page.goto(`${BASE_URL}/login`);
    
    // Try OAuth login
    await page.click('[data-testid="oauth-google"]');
    
    // Should show error message
    await expect(page.locator('[data-testid="network-error"]')).toBeVisible();
  });

  test('Handle expired OAuth session', async ({ page }) => {
    // Login successfully first
    await login(page, testUser.email, testUser.password);
    
    // Simulate session expiration
    await page.evaluate(() => {
      localStorage.removeItem('oauth_token');
      sessionStorage.clear();
    });
    
    // Try to access protected page
    await page.goto(`${BASE_URL}/dashboard`);
    
    // Should redirect to login
    await page.waitForURL(`${BASE_URL}/login`);
    
    // Should show session expired message
    await expect(page.locator('[data-testid="session-expired"]')).toBeVisible();
  });
});

test.describe('Multi-tenant OAuth', () => {
  test('Agency-specific OAuth flow', async ({ page }) => {
    // Navigate to agency-specific login
    await page.goto(`http://${testAgency.subdomain}.${BASE_URL.replace('http://', '')}/login`);
    
    // Click OAuth login
    await page.click('[data-testid="oauth-google"]');
    
    // Verify agency context is preserved
    const url = new URL(page.url());
    expect(url.searchParams.get('state')).toContain(testAgency.subdomain);
    
    // Mock callback
    await page.goto(`http://${testAgency.subdomain}.${BASE_URL.replace('http://', '')}/auth/callback?code=test_code&state=${testAgency.subdomain}_state`);
    
    // Should redirect to agency dashboard
    await page.waitForURL(new RegExp(`${testAgency.subdomain}.*dashboard`));
  });

  test('Cross-agency token isolation', async ({ browser }) => {
    // Create contexts for two different agencies
    const context1 = await browser.newContext({
      baseURL: `http://agency1.${BASE_URL.replace('http://', '')}`,
    });
    const context2 = await browser.newContext({
      baseURL: `http://agency2.${BASE_URL.replace('http://', '')}`,
    });
    
    const page1 = await context1.newPage();
    const page2 = await context2.newPage();
    
    // Login to agency1
    await page1.goto('/login');
    await page1.click('[data-testid="oauth-google"]');
    await page1.goto('/auth/callback?code=agency1_code');
    
    // Login to agency2
    await page2.goto('/login');
    await page2.click('[data-testid="oauth-google"]');
    await page2.goto('/auth/callback?code=agency2_code');
    
    // Try to access agency2 from agency1 context
    await page1.goto('http://agency2.localhost:3000/dashboard');
    
    // Should be denied access
    await page1.waitForURL(/login/);
    
    // Cleanup
    await context1.close();
    await context2.close();
  });
});

// Export test configuration
export default {
  use: {
    baseURL: BASE_URL,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
  timeout: 30000,
  retries: 2,
};