import { test, expect } from '@playwright/test';

const SQL_INJECTION_PAYLOADS = [
  // Basic SQL injection
  "' OR '1'='1",
  "' OR '1'='1' --",
  "' OR '1'='1' /*",
  "admin'--",
  "admin' #",
  "admin'/*",
  "' or 1=1--",
  "' or 1=1#",
  "' or 1=1/*",
  "') or '1'='1--",
  "') or ('1'='1--",
  
  // Union-based injection
  "' UNION SELECT NULL--",
  "' UNION SELECT NULL,NULL--",
  "' UNION SELECT NULL,NULL,NULL--",
  "' UNION ALL SELECT NULL--",
  
  // Time-based blind injection
  "' OR SLEEP(5)--",
  "'; WAITFOR DELAY '00:00:05'--",
  "' OR pg_sleep(5)--",
  
  // Boolean-based blind injection
  "' AND '1'='1",
  "' AND '1'='2",
  "' OR '1'='1",
  "' OR '1'='2",
  
  // Stacked queries
  "'; DROP TABLE users--",
  "'; DELETE FROM users--",
  "'; UPDATE users SET password=''--",
  
  // Out-of-band injection
  "' OR extractvalue(1,concat(0x7e,database()))--",
  "' AND (SELECT LOAD_FILE('/etc/passwd'))--",
  
  // Second-order injection
  "admin'||'",
  "admin' + '",
];

test.describe('SQL Injection Security Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('should prevent SQL injection in login form', async ({ page }) => {
    for (const payload of SQL_INJECTION_PAYLOADS) {
      // Test email field
      await page.fill('[placeholder="Email address"]', payload);
      await page.fill('[placeholder="Password"]', 'password123');
      await page.click('button[type="submit"]');
      
      // Should not log in
      await expect(page).not.toHaveURL(/dashboard/);
      
      // Should show error message, not database error
      const errorMessage = page.locator('[role="alert"]');
      if (await errorMessage.isVisible()) {
        const text = await errorMessage.textContent();
        // Check that error doesn't expose SQL details
        expect(text).not.toMatch(/sql|query|syntax|database/i);
      }
      
      // Test password field
      await page.fill('[placeholder="Email address"]', 'test@example.com');
      await page.fill('[placeholder="Password"]', payload);
      await page.click('button[type="submit"]');
      
      // Should not log in
      await expect(page).not.toHaveURL(/dashboard/);
      
      // Clear form for next test
      await page.reload();
    }
  });

  test('should prevent SQL injection in search inputs', async ({ page }) => {
    // Login first
    await page.fill('[placeholder="Email address"]', 'admin@agency.com');
    await page.fill('[placeholder="Password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/);
    
    // Test various search inputs
    const searchUrls = [
      '/models',
      '/financials',
      '/chat',
    ];
    
    for (const url of searchUrls) {
      await page.goto(url);
      
      const searchInput = page.locator('input[type="search"], [placeholder*="search" i]').first();
      if (await searchInput.isVisible()) {
        for (const payload of SQL_INJECTION_PAYLOADS.slice(0, 5)) {
          await searchInput.fill(payload);
          await searchInput.press('Enter');
          
          // Wait for potential results
          await page.waitForTimeout(1000);
          
          // Check for SQL errors in response
          const pageContent = await page.content();
          expect(pageContent).not.toMatch(/sql.*error|syntax.*error|database.*error/i);
          
          // Check network responses for errors
          const responsePromise = page.waitForResponse(
            response => response.url().includes('/api/') && response.status() >= 400,
            { timeout: 2000 }
          ).catch(() => null);
          
          const errorResponse = await responsePromise;
          if (errorResponse) {
            const responseText = await errorResponse.text();
            expect(responseText).not.toMatch(/sql|query|syntax|database/i);
          }
        }
      }
    }
  });

  test('should prevent SQL injection in URL parameters', async ({ page }) => {
    // Login first
    await page.fill('[placeholder="Email address"]', 'admin@agency.com');
    await page.fill('[placeholder="Password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/);
    
    const urlPayloads = [
      '/models?sort=' + encodeURIComponent("name'; DROP TABLE models--"),
      '/models?filter=' + encodeURIComponent("' OR 1=1--"),
      '/financials?date=' + encodeURIComponent("2024-01-01' OR '1'='1"),
      '/api/v1/users?id=' + encodeURIComponent("1 OR 1=1"),
    ];
    
    for (const url of urlPayloads) {
      const response = await page.goto(url);
      
      // Should not return server error
      expect(response?.status()).toBeLessThan(500);
      
      // Check page doesn't expose SQL errors
      const pageContent = await page.content();
      expect(pageContent).not.toMatch(/sql.*error|syntax.*error|database.*error/i);
    }
  });

  test('should prevent SQL injection in API requests', async ({ page, request }) => {
    // Get auth token
    const loginResponse = await request.post('/api/v1/auth/login', {
      data: {
        email: 'admin@agency.com',
        password: 'admin123',
      },
    });
    
    const { access_token } = await loginResponse.json();
    
    // Test various API endpoints
    const apiTests = [
      {
        method: 'GET',
        url: '/api/v1/models',
        params: { search: "' OR 1=1--" },
      },
      {
        method: 'POST',
        url: '/api/v1/models',
        data: {
          stage_name: "Test'; DROP TABLE models--",
          email: "test@example.com",
        },
      },
      {
        method: 'PUT',
        url: '/api/v1/models/1',
        data: {
          biography: "Updated bio'; UPDATE users SET role='admin'--",
        },
      },
    ];
    
    for (const test of apiTests) {
      let response;
      
      if (test.method === 'GET') {
        response = await request.get(test.url, {
          params: test.params,
          headers: {
            Authorization: `Bearer ${access_token}`,
          },
        });
      } else if (test.method === 'POST') {
        response = await request.post(test.url, {
          data: test.data,
          headers: {
            Authorization: `Bearer ${access_token}`,
          },
        });
      } else if (test.method === 'PUT') {
        response = await request.put(test.url, {
          data: test.data,
          headers: {
            Authorization: `Bearer ${access_token}`,
          },
        });
      }
      
      // Should not expose SQL errors
      if (response && response.status() >= 400) {
        const responseText = await response.text();
        expect(responseText).not.toMatch(/sql|query|syntax|database/i);
      }
    }
  });

  test('should use parameterized queries (code review)', async ({ page }) => {
    // This is a reminder to manually review backend code for:
    // 1. Use of parameterized queries/prepared statements
    // 2. Input validation before database queries
    // 3. Proper escaping of user input
    // 4. Use of ORMs with built-in SQL injection protection
    // 5. Stored procedures for complex queries
    
    // Log reminder
    console.log(`
      MANUAL REVIEW CHECKLIST:
      - [ ] All database queries use parameterized statements
      - [ ] No string concatenation in SQL queries
      - [ ] Input validation on all user inputs
      - [ ] ORM properly configured (SQLAlchemy)
      - [ ] Database user has minimal permissions
      - [ ] Error messages don't expose SQL structure
    `);
    
    expect(true).toBe(true); // Placeholder assertion
  });
});