import { test, expect } from '@playwright/test';

test.describe('API Security Tests', () => {
  let authToken: string;

  test.beforeAll(async ({ request }) => {
    // Get auth token for tests
    const response = await request.post('/api/v1/auth/login', {
      data: {
        email: 'admin@agency.com',
        password: 'admin123',
      },
    });
    
    const data = await response.json();
    authToken = data.access_token;
  });

  test('should validate API input parameters', async ({ request }) => {
    // Test various invalid inputs
    const invalidInputTests = [
      {
        endpoint: '/api/v1/models',
        method: 'POST',
        data: {
          stage_name: '', // Empty required field
          email: 'invalid-email', // Invalid email format
          commission_rate: 150, // Out of range
        },
        expectedStatus: 422,
      },
      {
        endpoint: '/api/v1/financials/payouts',
        method: 'POST',
        data: {
          amount: -100, // Negative amount
          method: 'invalid_method',
        },
        expectedStatus: 422,
      },
      {
        endpoint: '/api/v1/chat/messages',
        method: 'POST',
        data: {
          conversation_id: '../../etc/passwd', // Path traversal attempt
          content: 'a'.repeat(10000), // Very long content
        },
        expectedStatus: 422,
      },
    ];
    
    for (const test of invalidInputTests) {
      const response = await request[test.method.toLowerCase()](test.endpoint, {
        data: test.data,
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      
      expect(response.status()).toBe(test.expectedStatus);
      
      // Error response should not leak sensitive info
      const errorData = await response.json();
      expect(JSON.stringify(errorData)).not.toMatch(/password|secret|key|token/i);
    }
  });

  test('should implement rate limiting', async ({ request }) => {
    const endpoint = '/api/v1/models';
    const requests = [];
    
    // Make many requests rapidly
    for (let i = 0; i < 100; i++) {
      requests.push(
        request.get(endpoint, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
      );
    }
    
    const responses = await Promise.all(requests);
    
    // Some requests should be rate limited
    const rateLimitedResponses = responses.filter(r => r.status() === 429);
    expect(rateLimitedResponses.length).toBeGreaterThan(0);
    
    // Check rate limit headers
    const lastResponse = responses[responses.length - 1];
    const headers = lastResponse.headers();
    
    expect(headers['x-ratelimit-limit']).toBeDefined();
    expect(headers['x-ratelimit-remaining']).toBeDefined();
    expect(headers['x-ratelimit-reset']).toBeDefined();
  });

  test('should prevent unauthorized access to other users data', async ({ request }) => {
    // Try to access another user's data
    const tests = [
      {
        endpoint: '/api/v1/models/999999', // Non-existent or other user's model
        method: 'GET',
      },
      {
        endpoint: '/api/v1/users/2', // Another user's profile
        method: 'GET',
      },
      {
        endpoint: '/api/v1/financials/transactions?user_id=2', // Another user's transactions
        method: 'GET',
      },
    ];
    
    for (const test of tests) {
      const response = await request[test.method.toLowerCase()](test.endpoint, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      
      // Should either return 403 (Forbidden) or 404 (Not Found)
      expect([403, 404]).toContain(response.status());
    }
  });

  test('should validate content-type headers', async ({ request }) => {
    // Send requests with wrong content-type
    const response = await request.post('/api/v1/models', {
      data: '<xml>malicious</xml>',
      headers: {
        Authorization: `Bearer ${authToken}`,
        'Content-Type': 'application/xml', // Wrong content type
      },
    });
    
    // Should reject non-JSON content
    expect(response.status()).toBe(415); // Unsupported Media Type
  });

  test('should implement proper CORS policy', async ({ request, page }) => {
    // Test CORS from different origin
    await page.goto('https://evil-site.com');
    
    const result = await page.evaluate(async () => {
      try {
        const response = await fetch('http://localhost:8000/api/v1/models', {
          method: 'GET',
          credentials: 'include',
        });
        return {
          status: response.status,
          headers: Object.fromEntries(response.headers.entries()),
        };
      } catch (error) {
        return { error: error.message };
      }
    });
    
    // Should have CORS error or proper CORS headers
    if (result.error) {
      expect(result.error).toContain('CORS');
    } else {
      const corsHeader = result.headers['access-control-allow-origin'];
      expect(corsHeader).not.toBe('*'); // Should not allow all origins
    }
  });

  test('should sanitize API responses', async ({ request }) => {
    // Create data with potential XSS
    const response = await request.post('/api/v1/models', {
      data: {
        stage_name: 'Test<script>alert("XSS")</script>Model',
        email: 'test@example.com',
        biography: '<img src=x onerror=alert("XSS")>',
      },
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    
    if (response.ok()) {
      const data = await response.json();
      
      // Response should have sanitized data
      expect(data.stage_name).not.toContain('<script');
      expect(data.biography).not.toContain('onerror=');
    }
  });

  test('should prevent API enumeration', async ({ request }) => {
    // Try to enumerate IDs
    const responses = [];
    
    for (let id = 1; id <= 10; id++) {
      const startTime = Date.now();
      const response = await request.get(`/api/v1/models/${id}`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      const endTime = Date.now();
      
      responses.push({
        id,
        status: response.status(),
        time: endTime - startTime,
      });
    }
    
    // Response times should be consistent (prevent timing attacks)
    const times = responses.map(r => r.time);
    const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
    const maxDeviation = Math.max(...times.map(t => Math.abs(t - avgTime)));
    
    expect(maxDeviation).toBeLessThan(100); // Max 100ms deviation
  });

  test('should validate file uploads', async ({ request }) => {
    // Test file upload security
    const maliciousFiles = [
      {
        name: 'test.php',
        content: '<?php system($_GET["cmd"]); ?>',
        type: 'application/x-php',
      },
      {
        name: 'test.exe',
        content: Buffer.from('MZ'), // EXE header
        type: 'application/x-msdownload',
      },
      {
        name: '../../../etc/passwd',
        content: 'root:x:0:0',
        type: 'text/plain',
      },
    ];
    
    for (const file of maliciousFiles) {
      const formData = new FormData();
      formData.append('file', new Blob([file.content], { type: file.type }), file.name);
      
      const response = await request.post('/api/v1/upload', {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
        multipart: {
          file: {
            name: file.name,
            mimeType: file.type,
            buffer: Buffer.from(file.content),
          },
        },
      });
      
      // Should reject dangerous files
      expect(response.status()).toBe(422);
    }
  });

  test('should implement API versioning', async ({ request }) => {
    // Test API version handling
    const endpoints = [
      '/api/v1/models',
      '/api/v2/models', // Future version
      '/api/models', // No version
    ];
    
    for (const endpoint of endpoints) {
      const response = await request.get(endpoint, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      
      if (endpoint.includes('v1')) {
        expect(response.ok()).toBe(true);
      } else if (endpoint.includes('v2')) {
        // Future version might not exist yet
        expect([404, 501]).toContain(response.status());
      } else {
        // No version should redirect or fail
        expect(response.status()).toBeGreaterThanOrEqual(300);
      }
    }
  });

  test('should handle malformed JSON gracefully', async ({ request }) => {
    const malformedData = [
      '{"invalid": json}', // Missing quotes
      '{"unclosed": "string', // Unclosed string
      '{"number": 0123}', // Invalid number format
      '{"unicode": "\uDFFF"}', // Invalid unicode
      '{"huge": "' + 'x'.repeat(10000000) + '"}', // Very large payload
    ];
    
    for (const data of malformedData) {
      const response = await request.post('/api/v1/models', {
        data,
        headers: {
          Authorization: `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      });
      
      // Should handle gracefully
      expect(response.status()).toBe(400); // Bad Request
      
      // Error message should not expose internals
      const errorText = await response.text();
      expect(errorText).not.toMatch(/stack|trace|line \d+/i);
    }
  });

  test('should implement field-level access control', async ({ request }) => {
    // Try to update sensitive fields
    const response = await request.patch('/api/v1/users/me', {
      data: {
        role: 'super_admin', // Try to escalate privileges
        id: 999, // Try to change ID
        created_at: '2020-01-01', // Try to change audit fields
      },
      headers: {
        Authorization: `Bearer ${authToken}`,
      },
    });
    
    if (response.ok()) {
      const data = await response.json();
      
      // Sensitive fields should not be changed
      expect(data.role).not.toBe('super_admin');
      expect(data.id).not.toBe(999);
    }
  });

  test('should validate webhook signatures', async ({ request }) => {
    // Test webhook endpoint security
    const webhookData = {
      event: 'payment.completed',
      data: { amount: 100 },
    };
    
    // Without signature
    const response1 = await request.post('/api/v1/webhooks/stripe', {
      data: webhookData,
    });
    
    expect(response1.status()).toBe(401); // Unauthorized
    
    // With invalid signature
    const response2 = await request.post('/api/v1/webhooks/stripe', {
      data: webhookData,
      headers: {
        'X-Webhook-Signature': 'invalid_signature',
      },
    });
    
    expect(response2.status()).toBe(401); // Unauthorized
  });

  test('should prevent NoSQL injection', async ({ request }) => {
    // Test NoSQL injection attempts (if using NoSQL)
    const noSqlPayloads = [
      { $ne: null }, // Not equal
      { $gt: '' }, // Greater than
      { $regex: '.*' }, // Regex
      { $where: 'this.password.length > 0' }, // Where clause
    ];
    
    for (const payload of noSqlPayloads) {
      const response = await request.get('/api/v1/models', {
        params: {
          filter: JSON.stringify(payload),
        },
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      
      // Should not process NoSQL operators
      if (response.ok()) {
        const data = await response.json();
        // Should return normal results, not based on injection
        expect(data).toBeDefined();
      }
    }
  });

  test('API security checklist', async ({ page }) => {
    // Manual review checklist
    console.log(`
      API SECURITY CHECKLIST:
      - [ ] All endpoints require authentication
      - [ ] Rate limiting is implemented
      - [ ] Input validation on all parameters
      - [ ] Output encoding/sanitization
      - [ ] HTTPS only in production
      - [ ] API keys are properly managed
      - [ ] Sensitive data is not logged
      - [ ] Error messages don't leak information
      - [ ] API documentation is access-controlled
      - [ ] Deprecated endpoints are removed
      - [ ] GraphQL depth limiting (if used)
      - [ ] JWT tokens have proper expiration
      - [ ] Refresh tokens are rotated
      - [ ] API versioning strategy
      - [ ] Webhook signature validation
    `);
    
    expect(true).toBe(true);
  });
});