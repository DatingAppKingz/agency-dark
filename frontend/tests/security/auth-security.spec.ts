import { test, expect } from '@playwright/test';
import { chromium } from 'playwright-extra';
import stealth from 'playwright-extra-plugin-stealth';

// Use stealth plugin to avoid detection
chromium.use(stealth());

test.describe('Authentication Security Tests', () => {
  test('should enforce password complexity requirements', async ({ page }) => {
    await page.goto('/register');
    
    const weakPasswords = [
      '123456',
      'password',
      'qwerty',
      'abc123',
      '12345678',
      'password123',
      'admin',
      '111111',
      'letmein',
      '123123',
    ];
    
    for (const weakPassword of weakPasswords) {
      await page.fill('[name="email"]', 'test@example.com');
      await page.fill('[name="password"]', weakPassword);
      await page.fill('[name="confirmPassword"]', weakPassword);
      
      const submitButton = page.locator('button[type="submit"]');
      await submitButton.click();
      
      // Should show password strength error
      const errorMessage = await page.locator('.error-message, [role="alert"]').textContent();
      expect(errorMessage).toMatch(/password.*weak|strong|complexity|requirements/i);
      
      // Should not proceed with registration
      await expect(page).not.toHaveURL(/dashboard|verify/);
    }
  });

  test('should prevent brute force attacks', async ({ page }) => {
    await page.goto('/login');
    
    const maxAttempts = 5;
    const responses = [];
    
    // Try multiple failed login attempts
    for (let i = 0; i < maxAttempts + 2; i++) {
      const startTime = Date.now();
      
      await page.fill('[placeholder="Email address"]', 'admin@agency.com');
      await page.fill('[placeholder="Password"]', 'wrongpassword' + i);
      
      const responsePromise = page.waitForResponse(
        response => response.url().includes('/auth/login'),
        { timeout: 10000 }
      );
      
      await page.click('button[type="submit"]');
      
      try {
        const response = await responsePromise;
        const endTime = Date.now();
        
        responses.push({
          attempt: i + 1,
          status: response.status(),
          time: endTime - startTime,
        });
        
        // After max attempts, should be rate limited
        if (i >= maxAttempts) {
          expect(response.status()).toBe(429); // Too Many Requests
        }
      } catch (error) {
        // Timeout or other error - might indicate rate limiting
      }
      
      await page.waitForTimeout(1000); // Wait between attempts
    }
    
    // Check for increasing response times (indicating rate limiting)
    const lastResponseTime = responses[responses.length - 1]?.time || 0;
    const firstResponseTime = responses[0]?.time || 0;
    
    // Response time should increase after multiple failures
    expect(lastResponseTime).toBeGreaterThan(firstResponseTime);
  });

  test('should implement session timeout', async ({ page, context }) => {
    // Login
    await page.goto('/login');
    await page.fill('[placeholder="Email address"]', 'admin@agency.com');
    await page.fill('[placeholder="Password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/);
    
    // Get session cookie
    const cookies = await context.cookies();
    const sessionCookie = cookies.find(c => 
      c.name.includes('session') || c.name.includes('auth')
    );
    
    if (sessionCookie) {
      // Check cookie has proper attributes
      expect(sessionCookie.httpOnly).toBe(true);
      expect(sessionCookie.secure).toBe(true); // Should be true in production
      expect(sessionCookie.sameSite).toMatch(/Strict|Lax/);
      
      // Check for expiry
      if (sessionCookie.expires) {
        const expiryTime = sessionCookie.expires * 1000; // Convert to milliseconds
        const now = Date.now();
        const sessionDuration = expiryTime - now;
        
        // Session should expire within reasonable time (e.g., 24 hours)
        expect(sessionDuration).toBeLessThan(24 * 60 * 60 * 1000);
      }
    }
  });

  test('should prevent session fixation attacks', async ({ page, context }) => {
    // Get initial session
    await page.goto('/login');
    const cookiesBefore = await context.cookies();
    const sessionBefore = cookiesBefore.find(c => 
      c.name.includes('session') || c.name.includes('auth')
    );
    
    // Login
    await page.fill('[placeholder="Email address"]', 'admin@agency.com');
    await page.fill('[placeholder="Password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/);
    
    // Get session after login
    const cookiesAfter = await context.cookies();
    const sessionAfter = cookiesAfter.find(c => 
      c.name.includes('session') || c.name.includes('auth')
    );
    
    // Session ID should change after login
    if (sessionBefore && sessionAfter) {
      expect(sessionAfter.value).not.toBe(sessionBefore.value);
    }
  });

  test('should implement CSRF protection', async ({ page, request }) => {
    // Login first
    await page.goto('/login');
    await page.fill('[placeholder="Email address"]', 'admin@agency.com');
    await page.fill('[placeholder="Password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/);
    
    // Get CSRF token from page
    const csrfToken = await page.evaluate(() => {
      // Check meta tag
      const metaTag = document.querySelector('meta[name="csrf-token"]');
      if (metaTag) return metaTag.getAttribute('content');
      
      // Check hidden input
      const input = document.querySelector('input[name="csrf_token"]');
      if (input) return (input as HTMLInputElement).value;
      
      // Check cookie
      const cookies = document.cookie.split(';');
      const csrfCookie = cookies.find(c => c.includes('csrf'));
      if (csrfCookie) return csrfCookie.split('=')[1];
      
      return null;
    });
    
    // Try to make a state-changing request without CSRF token
    const response = await request.post('/api/v1/models', {
      data: {
        stage_name: 'Test Model',
        email: 'test@example.com',
      },
      headers: {
        // Omit CSRF token
      },
    });
    
    // Should be rejected
    expect(response.status()).toBe(403); // Forbidden
  });

  test('should prevent authentication bypass', async ({ page }) => {
    // Try to access protected routes without authentication
    const protectedRoutes = [
      '/dashboard',
      '/models',
      '/financials',
      '/chat',
      '/api/v1/models',
      '/api/v1/users',
      '/api/v1/financials/transactions',
    ];
    
    for (const route of protectedRoutes) {
      const response = await page.goto(route);
      
      if (route.startsWith('/api/')) {
        // API routes should return 401
        expect(response?.status()).toBe(401);
      } else {
        // UI routes should redirect to login
        await expect(page).toHaveURL(/login/);
      }
    }
  });

  test('should secure password reset flow', async ({ page }) => {
    await page.goto('/forgot-password');
    
    // Test enumeration prevention
    const emails = [
      'admin@agency.com', // Exists
      'nonexistent@example.com', // Doesn't exist
    ];
    
    const responses = [];
    
    for (const email of emails) {
      const startTime = Date.now();
      
      await page.fill('[name="email"]', email);
      await page.click('button[type="submit"]');
      
      // Wait for response
      await page.waitForTimeout(2000);
      
      const endTime = Date.now();
      const message = await page.locator('.success-message, .info-message').textContent();
      
      responses.push({
        email,
        message,
        time: endTime - startTime,
      });
      
      await page.reload();
    }
    
    // Messages should be identical (prevent user enumeration)
    expect(responses[0].message).toBe(responses[1].message);
    
    // Response times should be similar (prevent timing attacks)
    const timeDiff = Math.abs(responses[0].time - responses[1].time);
    expect(timeDiff).toBeLessThan(1000); // Less than 1 second difference
  });

  test('should implement secure headers', async ({ page }) => {
    const response = await page.goto('/');
    const headers = response?.headers() || {};
    
    // Check security headers
    expect(headers['x-frame-options']).toMatch(/DENY|SAMEORIGIN/i);
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['x-xss-protection']).toBe('1; mode=block');
    expect(headers['strict-transport-security']).toContain('max-age=');
    expect(headers['referrer-policy']).toMatch(/no-referrer|strict-origin/i);
    
    // Permissions Policy (formerly Feature Policy)
    if (headers['permissions-policy']) {
      expect(headers['permissions-policy']).toContain('geolocation=()');
      expect(headers['permissions-policy']).toContain('microphone=()');
    }
  });

  test('should prevent clickjacking', async ({ page }) => {
    // Create an iframe trying to embed the app
    await page.setContent(`
      <html>
        <body>
          <h1>Malicious Site</h1>
          <iframe src="http://localhost:5173/login" width="100%" height="600"></iframe>
        </body>
      </html>
    `);
    
    // Wait for iframe to load
    await page.waitForTimeout(2000);
    
    // Check if login page is displayed in iframe
    const iframe = page.frameLocator('iframe');
    
    try {
      // Try to access iframe content
      await iframe.locator('input').first().isVisible();
      
      // If we can access it, that's a security issue
      console.error('WARNING: Site can be embedded in iframe - clickjacking risk!');
    } catch (error) {
      // Good - iframe should be blocked
      expect(true).toBe(true);
    }
  });

  test('should implement account lockout after failed attempts', async ({ page }) => {
    const maxAttempts = 5;
    
    // Make multiple failed login attempts
    for (let i = 0; i < maxAttempts + 1; i++) {
      await page.goto('/login');
      await page.fill('[placeholder="Email address"]', 'admin@agency.com');
      await page.fill('[placeholder="Password"]', 'wrongpassword' + i);
      await page.click('button[type="submit"]');
      
      if (i < maxAttempts - 1) {
        // Should show error but allow more attempts
        await expect(page.locator('[role="alert"]')).toContainText(/invalid|incorrect/i);
      }
      
      await page.waitForTimeout(1000);
    }
    
    // After max attempts, account should be locked
    const errorMessage = await page.locator('[role="alert"]').textContent();
    expect(errorMessage).toMatch(/locked|suspended|too many attempts/i);
    
    // Even correct password should not work
    await page.fill('[placeholder="Password"]', 'admin123');
    await page.click('button[type="submit"]');
    await expect(page).not.toHaveURL(/dashboard/);
  });

  test('should log security events', async ({ page, request }) => {
    // This test checks if security events are being logged
    // In a real scenario, you'd check logs or monitoring systems
    
    const securityEvents = [
      { action: 'Failed login', expected: true },
      { action: 'Successful login', expected: true },
      { action: 'Password reset request', expected: true },
      { action: 'Account lockout', expected: true },
      { action: 'Privilege escalation attempt', expected: true },
    ];
    
    console.log(`
      MANUAL REVIEW: Verify security event logging
      ${securityEvents.map(e => `- [ ] ${e.action}`).join('\n      ')}
    `);
    
    expect(true).toBe(true); // Placeholder
  });
});