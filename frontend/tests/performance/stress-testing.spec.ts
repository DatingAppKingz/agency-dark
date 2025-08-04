import { test, expect } from '@playwright/test';
import { performance } from 'perf_hooks';

interface StressTestResult {
  scenario: string;
  breakingPoint: number;
  maxThroughput: number;
  failureRate: number;
  errorTypes: Map<string, number>;
  performanceDegradation: number;
}

test.describe('Stress Testing', () => {
  let authToken: string;
  const results: StressTestResult[] = [];

  test.beforeAll(async ({ request }) => {
    // Get auth token
    const response = await request.post('/api/v1/auth/login', {
      data: {
        email: 'admin@agency.com',
        password: 'admin123',
      },
    });
    
    const data = await response.json();
    authToken = data.access_token;
  });

  test.afterAll(async () => {
    // Generate stress test report
    console.log('\n=== STRESS TEST RESULTS ===\n');
    results.forEach(result => {
      console.log(`\nScenario: ${result.scenario}`);
      console.log(`Breaking Point: ${result.breakingPoint} concurrent requests`);
      console.log(`Max Throughput: ${result.maxThroughput.toFixed(2)} req/s`);
      console.log(`Failure Rate at Breaking Point: ${(result.failureRate * 100).toFixed(2)}%`);
      console.log(`Performance Degradation: ${result.performanceDegradation.toFixed(2)}x slower`);
      console.log('Error Types:', Object.fromEntries(result.errorTypes));
    });
  });

  test('stress test - find breaking point for model listing', async ({ request }) => {
    const endpoint = '/api/v1/models';
    const baselineResponse = await measureBaseline(request, endpoint, authToken);
    
    let concurrentRequests = 10;
    let breakingPoint = 0;
    let maxThroughput = 0;
    let performanceDegradation = 1;
    const errorTypes = new Map<string, number>();
    
    // Gradually increase load until system breaks
    while (concurrentRequests <= 500) {
      const result = await sendConcurrentRequests(
        request,
        endpoint,
        concurrentRequests,
        authToken
      );
      
      const throughput = result.successCount / (result.totalTime / 1000);
      maxThroughput = Math.max(maxThroughput, throughput);
      
      // Track error types
      result.errors.forEach(error => {
        errorTypes.set(error.type, (errorTypes.get(error.type) || 0) + 1);
      });
      
      // Check if we've hit the breaking point (>50% failure rate or extreme slowdown)
      if (result.failureRate > 0.5 || result.avgResponseTime > baselineResponse * 10) {
        breakingPoint = concurrentRequests;
        performanceDegradation = result.avgResponseTime / baselineResponse;
        
        results.push({
          scenario: 'Model Listing Endpoint',
          breakingPoint,
          maxThroughput,
          failureRate: result.failureRate,
          errorTypes,
          performanceDegradation,
        });
        
        break;
      }
      
      // Increase load exponentially
      concurrentRequests = Math.min(concurrentRequests * 1.5, 500);
      
      // Brief pause between tests
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
    
    // System should handle at least 50 concurrent requests
    expect(breakingPoint).toBeGreaterThan(50);
  });

  test('stress test - chat message flooding', async ({ request }) => {
    const endpoint = '/api/v1/chat/messages';
    let messagesSent = 0;
    const startTime = performance.now();
    const testDuration = 30000; // 30 seconds
    const errors: any[] = [];
    
    // Create promises for continuous message sending
    const senders = Array(20).fill(null).map((_, index) => 
      (async () => {
        while (performance.now() - startTime < testDuration) {
          try {
            const response = await request.post(endpoint, {
              headers: {
                Authorization: `Bearer ${authToken}`,
              },
              data: {
                conversation_id: `stress-test-${index}`,
                content: `Stress test message ${messagesSent++}`,
                type: 'text',
              },
              timeout: 5000,
            });
            
            if (response.status() >= 400) {
              errors.push({
                status: response.status(),
                time: performance.now() - startTime,
              });
            }
          } catch (error: any) {
            errors.push({
              type: 'timeout',
              time: performance.now() - startTime,
            });
          }
        }
      })()
    );
    
    await Promise.all(senders);
    
    const totalTime = performance.now() - startTime;
    const messagesPerSecond = messagesSent / (totalTime / 1000);
    const errorRate = errors.length / messagesSent;
    
    console.log(`Chat Message Flooding Results:
      - Messages sent: ${messagesSent}
      - Messages per second: ${messagesPerSecond.toFixed(2)}
      - Error rate: ${(errorRate * 100).toFixed(2)}%
      - Total errors: ${errors.length}
    `);
    
    // System should handle at least 10 messages per second
    expect(messagesPerSecond).toBeGreaterThan(10);
    expect(errorRate).toBeLessThan(0.1); // Less than 10% error rate
  });

  test('stress test - database connection pool exhaustion', async ({ request }) => {
    // Test endpoints that require database connections
    const dbIntensiveEndpoints = [
      '/api/v1/models?page=1&size=100',
      '/api/v1/financials/transactions?limit=100',
      '/api/v1/chat/conversations?limit=100',
      '/api/v1/analytics/model-performance',
    ];
    
    const connectionPoolSize = 100; // Assumed pool size
    const requests = connectionPoolSize * 2; // Try to exceed pool
    
    const promises = [];
    const startTime = performance.now();
    
    for (let i = 0; i < requests; i++) {
      const endpoint = dbIntensiveEndpoints[i % dbIntensiveEndpoints.length];
      promises.push(
        request.get(endpoint, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
          timeout: 30000,
        }).then(response => ({
          status: response.status(),
          endpoint,
          time: performance.now() - startTime,
        })).catch(error => ({
          status: 'timeout',
          endpoint,
          time: performance.now() - startTime,
          error: error.message,
        }))
      );
    }
    
    const results = await Promise.all(promises);
    const timeouts = results.filter(r => r.status === 'timeout');
    const errors = results.filter(r => typeof r.status === 'number' && r.status >= 500);
    
    console.log(`Database Connection Pool Test:
      - Total requests: ${requests}
      - Timeouts: ${timeouts.length}
      - Server errors: ${errors.length}
      - Success rate: ${((requests - timeouts.length - errors.length) / requests * 100).toFixed(2)}%
    `);
    
    // Should handle connection pool properly
    expect(timeouts.length).toBeLessThan(requests * 0.2); // Less than 20% timeouts
  });

  test('stress test - memory leak detection', async ({ request, page }) => {
    // Monitor memory usage while performing repetitive operations
    const iterations = 100;
    const memorySnapshots: number[] = [];
    
    await page.goto('/dashboard');
    
    for (let i = 0; i < iterations; i++) {
      // Perform memory-intensive operations
      await page.goto('/models');
      await page.waitForLoadState('networkidle');
      
      // Navigate to different pages
      await page.goto('/financials');
      await page.waitForLoadState('networkidle');
      
      await page.goto('/chat');
      await page.waitForLoadState('networkidle');
      
      // Take memory snapshot every 10 iterations
      if (i % 10 === 0) {
        const metrics = await page.evaluate(() => {
          if ('memory' in performance) {
            return (performance as any).memory.usedJSHeapSize;
          }
          return 0;
        });
        
        memorySnapshots.push(metrics);
      }
    }
    
    // Analyze memory growth
    if (memorySnapshots.length > 2) {
      const initialMemory = memorySnapshots[0];
      const finalMemory = memorySnapshots[memorySnapshots.length - 1];
      const memoryGrowth = finalMemory / initialMemory;
      
      console.log(`Memory Usage Analysis:
        - Initial: ${(initialMemory / 1024 / 1024).toFixed(2)} MB
        - Final: ${(finalMemory / 1024 / 1024).toFixed(2)} MB
        - Growth: ${memoryGrowth.toFixed(2)}x
      `);
      
      // Memory growth should be reasonable
      expect(memoryGrowth).toBeLessThan(2); // Less than 2x growth
    }
  });

  test('stress test - file upload under load', async ({ request }) => {
    const endpoint = '/api/v1/upload';
    const fileSize = 5 * 1024 * 1024; // 5MB
    const concurrentUploads = 10;
    
    const buffer = Buffer.alloc(fileSize);
    const promises = [];
    
    for (let i = 0; i < concurrentUploads; i++) {
      promises.push(
        request.post(endpoint, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
          multipart: {
            file: {
              name: `stress-test-${i}.jpg`,
              mimeType: 'image/jpeg',
              buffer: buffer,
            },
          },
          timeout: 60000,
        }).then(response => ({
          status: response.status(),
          success: response.ok(),
        })).catch(() => ({
          status: 'timeout',
          success: false,
        }))
      );
    }
    
    const startTime = performance.now();
    const results = await Promise.all(promises);
    const totalTime = performance.now() - startTime;
    
    const successCount = results.filter(r => r.success).length;
    const successRate = successCount / concurrentUploads;
    
    console.log(`File Upload Stress Test:
      - Concurrent uploads: ${concurrentUploads}
      - File size: ${(fileSize / 1024 / 1024).toFixed(2)} MB each
      - Success rate: ${(successRate * 100).toFixed(2)}%
      - Total time: ${(totalTime / 1000).toFixed(2)}s
    `);
    
    // Should handle multiple large file uploads
    expect(successRate).toBeGreaterThan(0.8); // 80% success rate
    expect(totalTime).toBeLessThan(120000); // Complete within 2 minutes
  });

  test('stress test - API rate limiting effectiveness', async ({ request }) => {
    const endpoint = '/api/v1/models';
    const requestsPerSecond = 100;
    const duration = 10; // seconds
    
    const results: any[] = [];
    const startTime = performance.now();
    
    // Send bursts of requests
    for (let second = 0; second < duration; second++) {
      const burstPromises = [];
      
      for (let i = 0; i < requestsPerSecond; i++) {
        burstPromises.push(
          request.get(endpoint, {
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
          }).then(response => ({
            status: response.status(),
            headers: response.headers(),
          }))
        );
      }
      
      const burstResults = await Promise.all(burstPromises);
      results.push(...burstResults);
      
      // Wait for the rest of the second
      const elapsed = performance.now() - startTime - (second * 1000);
      if (elapsed < 1000) {
        await new Promise(resolve => setTimeout(resolve, 1000 - elapsed));
      }
    }
    
    // Analyze rate limiting
    const rateLimited = results.filter(r => r.status === 429);
    const rateLimitedPercentage = (rateLimited.length / results.length) * 100;
    
    console.log(`Rate Limiting Test:
      - Total requests: ${results.length}
      - Rate limited: ${rateLimited.length} (${rateLimitedPercentage.toFixed(2)}%)
      - Requests per second attempted: ${requestsPerSecond}
    `);
    
    // Rate limiting should be working
    expect(rateLimited.length).toBeGreaterThan(0);
    
    // Check rate limit headers
    const limitedResponse = rateLimited[0];
    if (limitedResponse) {
      expect(limitedResponse.headers['x-ratelimit-limit']).toBeDefined();
      expect(limitedResponse.headers['x-ratelimit-remaining']).toBeDefined();
    }
  });

  test('stress test - recovery after overload', async ({ request }) => {
    const endpoint = '/api/v1/models';
    
    // Phase 1: Baseline performance
    const baselineStart = performance.now();
    const baselineResponse = await request.get(endpoint, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    const baselineTime = performance.now() - baselineStart;
    
    // Phase 2: Overload the system
    console.log('Overloading system...');
    const overloadPromises = [];
    for (let i = 0; i < 200; i++) {
      overloadPromises.push(
        request.get(endpoint, {
          headers: { Authorization: `Bearer ${authToken}` },
          timeout: 5000,
        }).catch(() => null)
      );
    }
    await Promise.all(overloadPromises);
    
    // Phase 3: Wait for recovery
    console.log('Waiting for recovery...');
    await new Promise(resolve => setTimeout(resolve, 5000));
    
    // Phase 4: Test recovery
    const recoveryTimes: number[] = [];
    for (let i = 0; i < 10; i++) {
      const start = performance.now();
      const response = await request.get(endpoint, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      const time = performance.now() - start;
      recoveryTimes.push(time);
      
      expect(response.status()).toBe(200);
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    const avgRecoveryTime = recoveryTimes.reduce((a, b) => a + b, 0) / recoveryTimes.length;
    const recoveryRatio = avgRecoveryTime / baselineTime;
    
    console.log(`Recovery Test:
      - Baseline response time: ${baselineTime.toFixed(2)}ms
      - Average recovery time: ${avgRecoveryTime.toFixed(2)}ms
      - Recovery ratio: ${recoveryRatio.toFixed(2)}x
    `);
    
    // System should recover to near-baseline performance
    expect(recoveryRatio).toBeLessThan(2); // Less than 2x slower after recovery
  });
});

// Helper functions
async function measureBaseline(request: any, endpoint: string, authToken: string): Promise<number> {
  const times: number[] = [];
  
  for (let i = 0; i < 5; i++) {
    const start = performance.now();
    await request.get(endpoint, {
      headers: { Authorization: `Bearer ${authToken}` },
    });
    times.push(performance.now() - start);
  }
  
  return times.reduce((a, b) => a + b, 0) / times.length;
}

async function sendConcurrentRequests(
  request: any,
  endpoint: string,
  count: number,
  authToken: string
): Promise<{
  successCount: number;
  failureCount: number;
  failureRate: number;
  avgResponseTime: number;
  totalTime: number;
  errors: Array<{ type: string; status?: number }>;
}> {
  const promises = [];
  const times: number[] = [];
  const errors: Array<{ type: string; status?: number }> = [];
  const startTime = performance.now();
  
  for (let i = 0; i < count; i++) {
    const requestStart = performance.now();
    
    promises.push(
      request.get(endpoint, {
        headers: { Authorization: `Bearer ${authToken}` },
        timeout: 10000,
      }).then((response: any) => {
        times.push(performance.now() - requestStart);
        if (response.status() >= 400) {
          errors.push({ type: 'http_error', status: response.status() });
          return { success: false };
        }
        return { success: true };
      }).catch((error: any) => {
        times.push(performance.now() - requestStart);
        errors.push({ type: error.name || 'unknown' });
        return { success: false };
      })
    );
  }
  
  const results = await Promise.all(promises);
  const totalTime = performance.now() - startTime;
  
  const successCount = results.filter(r => r.success).length;
  const failureCount = count - successCount;
  
  return {
    successCount,
    failureCount,
    failureRate: failureCount / count,
    avgResponseTime: times.reduce((a, b) => a + b, 0) / times.length,
    totalTime,
    errors,
  };
}