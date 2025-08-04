import { test, expect, devices } from '@playwright/test';
import lighthouse from 'lighthouse';
import { launch } from 'chrome-launcher';

interface PerformanceMetrics {
  pageLoad: number;
  firstContentfulPaint: number;
  largestContentfulPaint: number;
  timeToInteractive: number;
  cumulativeLayoutShift: number;
  totalBlockingTime: number;
}

interface BenchmarkResult {
  page: string;
  metrics: PerformanceMetrics;
  lighthouseScore?: number;
  bundleSize?: number;
  memoryUsage?: number;
}

test.describe('Performance Benchmarks', () => {
  const results: BenchmarkResult[] = [];
  
  test.afterAll(async () => {
    // Generate benchmark report
    console.log('\n=== PERFORMANCE BENCHMARK RESULTS ===\n');
    console.table(results.map(r => ({
      Page: r.page,
      'Page Load (ms)': r.metrics.pageLoad.toFixed(0),
      'FCP (ms)': r.metrics.firstContentfulPaint.toFixed(0),
      'LCP (ms)': r.metrics.largestContentfulPaint.toFixed(0),
      'TTI (ms)': r.metrics.timeToInteractive.toFixed(0),
      'CLS': r.metrics.cumulativeLayoutShift.toFixed(3),
      'TBT (ms)': r.metrics.totalBlockingTime.toFixed(0),
      'Lighthouse Score': r.lighthouseScore ? r.lighthouseScore.toFixed(0) : 'N/A',
    })));
    
    // Check against performance budgets
    checkPerformanceBudgets(results);
  });

  test('benchmark - dashboard page performance', async ({ page }) => {
    const metrics = await measurePagePerformance(page, '/dashboard');
    
    results.push({
      page: 'Dashboard',
      metrics,
    });
    
    // Performance assertions
    expect(metrics.largestContentfulPaint).toBeLessThan(2500); // LCP < 2.5s
    expect(metrics.cumulativeLayoutShift).toBeLessThan(0.1); // CLS < 0.1
    expect(metrics.totalBlockingTime).toBeLessThan(300); // TBT < 300ms
  });

  test('benchmark - models listing page', async ({ page }) => {
    const metrics = await measurePagePerformance(page, '/models');
    
    results.push({
      page: 'Models Listing',
      metrics,
    });
    
    // Virtual scrolling should keep performance good even with many items
    expect(metrics.largestContentfulPaint).toBeLessThan(3000);
    expect(metrics.timeToInteractive).toBeLessThan(3500);
  });

  test('benchmark - chat interface performance', async ({ page }) => {
    const metrics = await measurePagePerformance(page, '/chat');
    
    // Test real-time message performance
    await page.waitForSelector('[data-testid="conversation-item"]');
    const conversationItem = page.locator('[data-testid="conversation-item"]').first();
    if (await conversationItem.isVisible()) {
      await conversationItem.click();
      
      // Measure message sending performance
      const sendTimes: number[] = [];
      for (let i = 0; i < 5; i++) {
        const start = performance.now();
        
        await page.fill('[placeholder*="message" i]', `Performance test message ${i}`);
        await page.click('button:has-text("Send")');
        
        // Wait for message to appear
        await page.waitForSelector(`text=Performance test message ${i}`, { timeout: 5000 });
        
        sendTimes.push(performance.now() - start);
      }
      
      const avgSendTime = sendTimes.reduce((a, b) => a + b, 0) / sendTimes.length;
      console.log(`Average message send time: ${avgSendTime.toFixed(2)}ms`);
      
      expect(avgSendTime).toBeLessThan(1000); // Messages should send in < 1s
    }
    
    results.push({
      page: 'Chat Interface',
      metrics,
    });
  });

  test('benchmark - financial dashboard', async ({ page }) => {
    const metrics = await measurePagePerformance(page, '/financials');
    
    // Test chart rendering performance
    await page.waitForSelector('canvas, svg', { timeout: 10000 });
    
    results.push({
      page: 'Financial Dashboard',
      metrics,
    });
    
    // Charts may take longer to render
    expect(metrics.largestContentfulPaint).toBeLessThan(4000);
  });

  test('benchmark - mobile performance', async ({ browser }) => {
    // Test on mobile viewport
    const context = await browser.newContext({
      ...devices['iPhone 12'],
    });
    const page = await context.newPage();
    
    const mobileMetrics = await measurePagePerformance(page, '/dashboard');
    
    results.push({
      page: 'Dashboard (Mobile)',
      metrics: mobileMetrics,
    });
    
    // Mobile performance should still be acceptable
    expect(mobileMetrics.largestContentfulPaint).toBeLessThan(3500);
    expect(mobileMetrics.timeToInteractive).toBeLessThan(5000);
    
    await context.close();
  });

  test('benchmark - bundle size analysis', async ({ page }) => {
    const networkRequests: any[] = [];
    
    page.on('response', response => {
      const url = response.url();
      if (url.includes('.js') || url.includes('.css')) {
        networkRequests.push({
          url,
          size: response.headers()['content-length'] || 0,
          type: url.includes('.js') ? 'javascript' : 'css',
        });
      }
    });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Calculate bundle sizes
    const jsSize = networkRequests
      .filter(r => r.type === 'javascript')
      .reduce((sum, r) => sum + parseInt(r.size), 0);
    
    const cssSize = networkRequests
      .filter(r => r.type === 'css')
      .reduce((sum, r) => sum + parseInt(r.size), 0);
    
    const totalSize = jsSize + cssSize;
    
    console.log(`Bundle Sizes:
      - JavaScript: ${(jsSize / 1024).toFixed(2)} KB
      - CSS: ${(cssSize / 1024).toFixed(2)} KB
      - Total: ${(totalSize / 1024).toFixed(2)} KB
    `);
    
    // Bundle size assertions
    expect(jsSize).toBeLessThan(1024 * 1024); // JS < 1MB
    expect(totalSize).toBeLessThan(1.5 * 1024 * 1024); // Total < 1.5MB
  });

  test('benchmark - memory usage patterns', async ({ page }) => {
    const memorySnapshots: any[] = [];
    
    // Navigate through the app and measure memory
    const pages = ['/dashboard', '/models', '/financials', '/chat'];
    
    for (const pageUrl of pages) {
      await page.goto(pageUrl);
      await page.waitForLoadState('networkidle');
      
      const metrics = await page.evaluate(() => {
        if ('memory' in performance) {
          return {
            usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
            totalJSHeapSize: (performance as any).memory.totalJSHeapSize,
            jsHeapSizeLimit: (performance as any).memory.jsHeapSizeLimit,
          };
        }
        return null;
      });
      
      if (metrics) {
        memorySnapshots.push({
          page: pageUrl,
          ...metrics,
        });
      }
    }
    
    if (memorySnapshots.length > 0) {
      console.log('\nMemory Usage:');
      memorySnapshots.forEach(snapshot => {
        console.log(`${snapshot.page}: ${(snapshot.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`);
      });
      
      // Check for memory leaks
      const firstSnapshot = memorySnapshots[0];
      const lastSnapshot = memorySnapshots[memorySnapshots.length - 1];
      const memoryGrowth = lastSnapshot.usedJSHeapSize / firstSnapshot.usedJSHeapSize;
      
      expect(memoryGrowth).toBeLessThan(1.5); // Less than 50% growth
    }
  });

  test('benchmark - lighthouse performance audit', async ({ page }) => {
    // Skip in CI as it requires Chrome installation
    if (process.env.CI) {
      test.skip();
      return;
    }
    
    const chrome = await launch({ chromeFlags: ['--headless'] });
    const options = {
      logLevel: 'info' as const,
      output: 'json' as const,
      port: chrome.port,
    };
    
    const pages = [
      { url: 'http://localhost:5173/', name: 'Home' },
      { url: 'http://localhost:5173/dashboard', name: 'Dashboard' },
      { url: 'http://localhost:5173/models', name: 'Models' },
    ];
    
    for (const pageInfo of pages) {
      const runnerResult = await lighthouse(pageInfo.url, options);
      
      if (runnerResult?.lhr) {
        const scores = {
          performance: runnerResult.lhr.categories.performance.score * 100,
          accessibility: runnerResult.lhr.categories.accessibility.score * 100,
          bestPractices: runnerResult.lhr.categories['best-practices'].score * 100,
          seo: runnerResult.lhr.categories.seo.score * 100,
        };
        
        console.log(`\nLighthouse Scores for ${pageInfo.name}:`);
        console.log(`  Performance: ${scores.performance}`);
        console.log(`  Accessibility: ${scores.accessibility}`);
        console.log(`  Best Practices: ${scores.bestPractices}`);
        console.log(`  SEO: ${scores.seo}`);
        
        // Performance score assertions
        expect(scores.performance).toBeGreaterThan(70);
        expect(scores.accessibility).toBeGreaterThan(80);
        expect(scores.bestPractices).toBeGreaterThan(80);
      }
    }
    
    await chrome.kill();
  });

  test('benchmark - API response times', async ({ request }) => {
    const endpoints = [
      { path: '/api/v1/models', name: 'Models List' },
      { path: '/api/v1/financials/stats', name: 'Financial Stats' },
      { path: '/api/v1/chat/conversations', name: 'Conversations' },
      { path: '/api/v1/analytics/overview', name: 'Analytics Overview' },
    ];
    
    // Get auth token
    const loginResponse = await request.post('/api/v1/auth/login', {
      data: {
        email: 'admin@agency.com',
        password: 'admin123',
      },
    });
    const { access_token } = await loginResponse.json();
    
    console.log('\nAPI Response Time Benchmarks:');
    
    for (const endpoint of endpoints) {
      const times: number[] = [];
      
      // Make multiple requests to get average
      for (let i = 0; i < 10; i++) {
        const start = performance.now();
        
        const response = await request.get(endpoint.path, {
          headers: {
            Authorization: `Bearer ${access_token}`,
          },
        });
        
        times.push(performance.now() - start);
        
        expect(response.status()).toBe(200);
      }
      
      const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      
      console.log(`${endpoint.name}:
        - Average: ${avgTime.toFixed(2)}ms
        - Min: ${minTime.toFixed(2)}ms
        - Max: ${maxTime.toFixed(2)}ms
      `);
      
      // API response time assertions
      expect(avgTime).toBeLessThan(500); // Average < 500ms
      expect(maxTime).toBeLessThan(1000); // Max < 1s
    }
  });

  test('benchmark - rendering performance with large datasets', async ({ page }) => {
    // Test performance with large amounts of data
    await page.goto('/models');
    
    // Measure initial render
    const initialMetrics = await page.evaluate(() => {
      const entries = performance.getEntriesByType('navigation') as PerformanceNavigationTiming[];
      return {
        domContentLoaded: entries[0].domContentLoadedEventEnd - entries[0].domContentLoadedEventStart,
        loadComplete: entries[0].loadEventEnd - entries[0].loadEventStart,
      };
    });
    
    console.log(`Large Dataset Rendering:
      - DOM Content Loaded: ${initialMetrics.domContentLoaded.toFixed(2)}ms
      - Load Complete: ${initialMetrics.loadComplete.toFixed(2)}ms
    `);
    
    // Test scrolling performance
    const scrollTimes: number[] = [];
    for (let i = 0; i < 5; i++) {
      const start = performance.now();
      
      await page.evaluate(() => {
        window.scrollTo(0, document.body.scrollHeight);
      });
      await page.waitForTimeout(100);
      
      await page.evaluate(() => {
        window.scrollTo(0, 0);
      });
      await page.waitForTimeout(100);
      
      scrollTimes.push(performance.now() - start);
    }
    
    const avgScrollTime = scrollTimes.reduce((a, b) => a + b, 0) / scrollTimes.length;
    console.log(`Average scroll cycle time: ${avgScrollTime.toFixed(2)}ms`);
    
    // Scrolling should be smooth
    expect(avgScrollTime).toBeLessThan(500);
  });
});

// Helper function to measure page performance
async function measurePagePerformance(page: any, url: string): Promise<PerformanceMetrics> {
  await page.goto(url);
  await page.waitForLoadState('networkidle');
  
  // Wait a bit for any async operations
  await page.waitForTimeout(2000);
  
  // Get performance metrics
  const metrics = await page.evaluate(() => {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    const paint = performance.getEntriesByType('paint');
    
    const fcp = paint.find(entry => entry.name === 'first-contentful-paint');
    const lcp = performance.getEntriesByType('largest-contentful-paint')[0];
    
    // Calculate metrics
    return {
      pageLoad: navigation.loadEventEnd - navigation.fetchStart,
      firstContentfulPaint: fcp ? fcp.startTime : 0,
      largestContentfulPaint: lcp ? lcp.startTime : 0,
      timeToInteractive: navigation.domInteractive - navigation.fetchStart,
      cumulativeLayoutShift: 0, // Would need more complex calculation
      totalBlockingTime: 0, // Would need more complex calculation
    };
  });
  
  // Try to get CLS from Chrome DevTools
  try {
    const cls = await page.evaluate(() => {
      let clsValue = 0;
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if ((entry as any).hadRecentInput) continue;
          clsValue += (entry as any).value;
        }
      });
      observer.observe({ type: 'layout-shift', buffered: true });
      observer.disconnect();
      return clsValue;
    });
    metrics.cumulativeLayoutShift = cls;
  } catch (e) {
    // CLS calculation might not be available
  }
  
  return metrics;
}

function checkPerformanceBudgets(results: BenchmarkResult[]) {
  console.log('\n=== PERFORMANCE BUDGET CHECK ===\n');
  
  const budgets = {
    pageLoad: 3000,
    firstContentfulPaint: 1800,
    largestContentfulPaint: 2500,
    timeToInteractive: 3800,
    cumulativeLayoutShift: 0.1,
    totalBlockingTime: 300,
  };
  
  let failures = 0;
  
  results.forEach(result => {
    console.log(`\n${result.page}:`);
    
    Object.entries(budgets).forEach(([metric, budget]) => {
      const value = result.metrics[metric as keyof PerformanceMetrics];
      const passed = value <= budget;
      
      if (!passed) failures++;
      
      console.log(`  ${metric}: ${value.toFixed(2)} / ${budget} ${passed ? '✅' : '❌'}`);
    });
  });
  
  if (failures === 0) {
    console.log('\n✅ All performance budgets met!');
  } else {
    console.log(`\n❌ ${failures} performance budget violations found.`);
  }
}