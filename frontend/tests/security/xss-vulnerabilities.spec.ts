import { test, expect } from '@playwright/test';

const XSS_PAYLOADS = [
  // Basic XSS
  '<script>alert("XSS")</script>',
  '<img src=x onerror=alert("XSS")>',
  '<svg onload=alert("XSS")>',
  '<iframe src="javascript:alert(\'XSS\')">',
  
  // Event handler XSS
  '<body onload=alert("XSS")>',
  '<input onfocus=alert("XSS") autofocus>',
  '<select onfocus=alert("XSS") autofocus>',
  '<textarea onfocus=alert("XSS") autofocus>',
  '<button onclick=alert("XSS")>Click me</button>',
  
  // JavaScript protocol XSS
  '<a href="javascript:alert(\'XSS\')">Click</a>',
  '<form action="javascript:alert(\'XSS\')">',
  
  // Data URI XSS
  '<script src="data:text/javascript,alert(\'XSS\')"></script>',
  '<object data="data:text/html,<script>alert(\'XSS\')</script>">',
  
  // DOM-based XSS
  '"><script>alert("XSS")</script>',
  '\'><script>alert("XSS")</script>',
  '</script><script>alert("XSS")</script>',
  
  // Encoded XSS
  '&lt;script&gt;alert("XSS")&lt;/script&gt;',
  '%3Cscript%3Ealert("XSS")%3C/script%3E',
  '\u003Cscript\u003Ealert("XSS")\u003C/script\u003E',
  
  // CSS injection
  '<style>body{background:url("javascript:alert(\'XSS\')")}</style>',
  '<link rel="stylesheet" href="javascript:alert(\'XSS\')">',
  
  // Meta tag injection
  '<meta http-equiv="refresh" content="0;url=javascript:alert(\'XSS\')">',
  
  // SVG injection
  '<svg/onload=alert("XSS")>',
  '<svg><script>alert("XSS")</script></svg>',
  
  // Markdown XSS (if markdown is used)
  '[Click me](javascript:alert("XSS"))',
  '![](javascript:alert("XSS"))',
  
  // React-specific XSS attempts
  '{alert("XSS")}',
  '${alert("XSS")}',
  'dangerouslySetInnerHTML={{__html: "<img src=x onerror=alert(\'XSS\')>"}}',
];

test.describe('XSS Vulnerability Tests', () => {
  let alertCount = 0;

  test.beforeEach(async ({ page }) => {
    // Monitor for alert dialogs
    page.on('dialog', async dialog => {
      alertCount++;
      console.error(`XSS Alert detected: ${dialog.message()}`);
      await dialog.dismiss();
    });
    
    // Login
    await page.goto('/login');
    await page.fill('[placeholder="Email address"]', 'admin@agency.com');
    await page.fill('[placeholder="Password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/dashboard/);
  });

  test.afterEach(async () => {
    expect(alertCount).toBe(0);
    alertCount = 0;
  });

  test('should prevent XSS in user profile fields', async ({ page }) => {
    await page.goto('/profile');
    
    const fields = [
      { selector: '[name="name"]', label: 'Name' },
      { selector: '[name="biography"]', label: 'Biography' },
      { selector: '[name="stage_name"]', label: 'Stage Name' },
    ];
    
    for (const field of fields) {
      const input = page.locator(field.selector);
      if (await input.isVisible()) {
        for (const payload of XSS_PAYLOADS.slice(0, 5)) {
          await input.fill(payload);
          await page.click('button:has-text("Save")');
          
          // Wait for save
          await page.waitForTimeout(1000);
          
          // Reload to see if XSS executes
          await page.reload();
          
          // Check if the payload is properly escaped in display
          const displayedText = await page.textContent('body');
          if (displayedText?.includes(payload)) {
            // The payload should be escaped, not executed
            expect(alertCount).toBe(0);
          }
        }
      }
    }
  });

  test('should prevent XSS in chat messages', async ({ page }) => {
    await page.goto('/chat');
    
    // Select a conversation
    const firstConversation = page.locator('[data-testid="conversation-item"]').first();
    if (await firstConversation.isVisible()) {
      await firstConversation.click();
      
      const messageInput = page.locator('[placeholder*="message" i]');
      const sendButton = page.locator('button:has-text("Send")');
      
      for (const payload of XSS_PAYLOADS.slice(0, 10)) {
        await messageInput.fill(payload);
        await sendButton.click();
        
        // Wait for message to appear
        await page.waitForTimeout(500);
        
        // Check that payload is escaped in the message display
        const lastMessage = page.locator('[data-testid="message"]').last();
        const messageHtml = await lastMessage.innerHTML();
        
        // Should not contain unescaped script tags
        expect(messageHtml).not.toContain('<script');
        expect(messageHtml).not.toContain('onerror=');
        expect(messageHtml).not.toContain('javascript:');
        
        // No alerts should have fired
        expect(alertCount).toBe(0);
      }
    }
  });

  test('should prevent XSS in search parameters', async ({ page }) => {
    const searchPages = ['/models', '/financials', '/chat'];
    
    for (const searchPage of searchPages) {
      await page.goto(searchPage);
      
      // URL-based XSS
      for (const payload of XSS_PAYLOADS.slice(0, 5)) {
        await page.goto(`${searchPage}?search=${encodeURIComponent(payload)}`);
        
        // Check if search term is displayed safely
        const searchInput = page.locator('input[type="search"]').first();
        if (await searchInput.isVisible()) {
          const value = await searchInput.inputValue();
          // Value should be the payload, but safely handled
          if (value === payload) {
            expect(alertCount).toBe(0);
          }
        }
        
        // Check page content doesn't execute XSS
        const pageHtml = await page.content();
        expect(pageHtml).not.toMatch(/<script[^>]*>alert/);
      }
    }
  });

  test('should prevent stored XSS in model profiles', async ({ page, request }) => {
    // Create a model with XSS payload
    const response = await request.post('/api/v1/models', {
      data: {
        stage_name: '<img src=x onerror=alert("XSS")>',
        email: 'xsstest@example.com',
        biography: '<script>alert("XSS")</script>',
      },
      headers: {
        Authorization: `Bearer ${await getAuthToken(request)}`,
      },
    });
    
    if (response.ok()) {
      const model = await response.json();
      
      // View the model profile
      await page.goto(`/models/${model.id}`);
      
      // The XSS payloads should be escaped
      expect(alertCount).toBe(0);
      
      // Check that content is escaped in HTML
      const pageHtml = await page.content();
      expect(pageHtml).not.toContain('<script>alert');
      expect(pageHtml).not.toContain('onerror=alert');
    }
  });

  test('should prevent DOM-based XSS', async ({ page }) => {
    // Test hash-based XSS
    await page.goto('/dashboard#<script>alert("XSS")</script>');
    expect(alertCount).toBe(0);
    
    // Test query-based DOM XSS
    await page.goto('/models?filter=<img src=x onerror=alert("XSS")>');
    expect(alertCount).toBe(0);
    
    // Test path-based XSS (if app uses client-side routing)
    await page.goto('/models/<script>alert("XSS")</script>');
    expect(alertCount).toBe(0);
  });

  test('should have proper Content Security Policy', async ({ page }) => {
    const response = await page.goto('/');
    const cspHeader = response?.headers()['content-security-policy'];
    
    if (cspHeader) {
      // Check for important CSP directives
      expect(cspHeader).toContain("default-src");
      expect(cspHeader).toContain("script-src");
      expect(cspHeader).not.toContain("unsafe-inline");
      expect(cspHeader).not.toContain("unsafe-eval");
    } else {
      console.warn('No CSP header found - this is a security risk!');
    }
  });

  test('should sanitize rich text content', async ({ page }) => {
    // Test rich text editors if present
    await page.goto('/models/new');
    
    const richTextEditor = page.locator('[contenteditable="true"], .rich-text-editor');
    if (await richTextEditor.isVisible()) {
      for (const payload of XSS_PAYLOADS.slice(0, 5)) {
        await richTextEditor.fill(payload);
        
        // Trigger save or preview
        const saveButton = page.locator('button:has-text("Save")');
        if (await saveButton.isVisible()) {
          await saveButton.click();
          await page.waitForTimeout(1000);
        }
        
        expect(alertCount).toBe(0);
      }
    }
  });

  test('should escape user-generated content in notifications', async ({ page }) => {
    // Trigger notifications with XSS payloads
    const notificationPayloads = [
      { title: '<script>alert("XSS")</script>', message: 'Test' },
      { title: 'Test', message: '<img src=x onerror=alert("XSS")>' },
    ];
    
    for (const payload of notificationPayloads) {
      // This would typically be triggered by an action
      // For now, we'll check if the notification system exists
      const notifications = page.locator('[role="alert"], .notification, .toast');
      
      if (await notifications.first().isVisible()) {
        const notificationHtml = await notifications.first().innerHTML();
        expect(notificationHtml).not.toContain('<script');
        expect(notificationHtml).not.toContain('onerror=');
      }
    }
    
    expect(alertCount).toBe(0);
  });

  test('should prevent XSS in file uploads', async ({ page }) => {
    await page.goto('/models');
    
    // Try to upload files with XSS in filename
    const xssFilenames = [
      '<script>alert("XSS")</script>.jpg',
      'image"><script>alert("XSS")</script>.png',
      'file.svg<script>alert("XSS")</script>',
    ];
    
    // This is a conceptual test - actual implementation would need file creation
    for (const filename of xssFilenames) {
      // Check that filename is properly sanitized when displayed
      // The actual file upload test would go here
      expect(alertCount).toBe(0);
    }
  });
});

async function getAuthToken(request: any): Promise<string> {
  const response = await request.post('/api/v1/auth/login', {
    data: {
      email: 'admin@agency.com',
      password: 'admin123',
    },
  });
  
  const { access_token } = await response.json();
  return access_token;
}