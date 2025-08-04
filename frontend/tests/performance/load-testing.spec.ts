import { test, expect } from '@playwright/test';
import { performance } from 'perf_hooks';

interface LoadTestResult {
  endpoint: string;
  method: string;
  averageResponseTime: number;
  maxResponseTime: number;
  minResponseTime: number;
  successRate: number;
  requestsPerSecond: number;
  totalRequests: number;
  failedRequests: number;
}

test.describe('Load Testing', () => {
  let authToken: string;
  const results: LoadTestResult[] = [];

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
    // Generate load test report
    console.log('\n=== LOAD TEST RESULTS ===\n');
    console.table(results);
    
    // Write results to file
    const fs = require('fs');
    const reportPath = 'test-results/performance/load-test-report.json';
    fs.mkdirSync('test-results/performance', { recursive: true });
    fs.writeFileSync(reportPath, JSON.stringify(results, null, 2));
  });

  test('load test - GET /api/v1/models', async ({ request }) => {
    const endpoint = '/api/v1/models';
    const method = 'GET';
    const totalRequests = 100;
    const concurrentRequests = 10;
    
    const result = await runLoadTest(
      request,
      endpoint,
      method,
      totalRequests,
      concurrentRequests,
      {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      }
    );
    
    results.push(result);
    
    // Assertions
    expect(result.successRate).toBeGreaterThan(0.95); // 95% success rate
    expect(result.averageResponseTime).toBeLessThan(500); // Average < 500ms
    expect(result.maxResponseTime).toBeLessThan(2000); // Max < 2s
  });

  test('load test - POST /api/v1/chat/messages', async ({ request }) => {
    const endpoint = '/api/v1/chat/messages';
    const method = 'POST';
    const totalRequests = 50;
    const concurrentRequests = 5;
    
    const result = await runLoadTest(
      request,
      endpoint,
      method,
      totalRequests,
      concurrentRequests,
      {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
        data: {
          conversation_id: 'test-conversation',
          content: 'Test message for load testing',
          type: 'text',
        },
      }
    );
    
    results.push(result);
    
    expect(result.successRate).toBeGreaterThan(0.90); // 90% success rate
    expect(result.averageResponseTime).toBeLessThan(1000); // Average < 1s
  });

  test('load test - GET /api/v1/financials/transactions', async ({ request }) => {
    const endpoint = '/api/v1/financials/transactions';
    const method = 'GET';
    const totalRequests = 75;
    const concurrentRequests = 5;
    
    const result = await runLoadTest(
      request,
      endpoint,
      method,
      totalRequests,
      concurrentRequests,
      {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      }
    );
    
    results.push(result);
    
    expect(result.successRate).toBeGreaterThan(0.95);
    expect(result.averageResponseTime).toBeLessThan(800);
  });

  test('load test - concurrent user simulation', async ({ request }) => {
    // Simulate multiple users accessing different endpoints
    const userScenarios = [
      { endpoint: '/api/v1/models', method: 'GET' },
      { endpoint: '/api/v1/financials/stats', method: 'GET' },
      { endpoint: '/api/v1/chat/conversations', method: 'GET' },
      { endpoint: '/api/v1/users/me', method: 'GET' },
    ];
    
    const concurrentUsers = 20;
    const requestsPerUser = 10;
    
    const startTime = performance.now();
    const promises = [];
    
    for (let i = 0; i < concurrentUsers; i++) {
      const scenario = userScenarios[i % userScenarios.length];
      
      for (let j = 0; j < requestsPerUser; j++) {
        promises.push(
          request[scenario.method.toLowerCase()](scenario.endpoint, {
            headers: {
              Authorization: `Bearer ${authToken}`,
            },
          }).then(response => ({
            status: response.status(),
            endpoint: scenario.endpoint,
            time: performance.now() - startTime,
          }))
        );
      }
    }
    
    const responses = await Promise.all(promises);
    const endTime = performance.now();
    const totalTime = endTime - startTime;
    
    // Analyze results
    const successfulRequests = responses.filter(r => r.status >= 200 && r.status < 300);
    const successRate = successfulRequests.length / responses.length;
    
    console.log(`Concurrent user test completed:
      - Total users: ${concurrentUsers}
      - Requests per user: ${requestsPerUser}
      - Total requests: ${responses.length}
      - Success rate: ${(successRate * 100).toFixed(2)}%
      - Total time: ${totalTime.toFixed(2)}ms
      - Requests per second: ${(responses.length / (totalTime / 1000)).toFixed(2)}
    `);
    
    expect(successRate).toBeGreaterThan(0.9);
    expect(totalTime).toBeLessThan(30000); // Complete within 30 seconds
  });

  test('load test - file upload performance', async ({ request }) => {
    const endpoint = '/api/v1/upload';
    const fileSizes = [
      { size: 100 * 1024, name: '100KB' },      // 100KB
      { size: 1 * 1024 * 1024, name: '1MB' },   // 1MB
      { size: 5 * 1024 * 1024, name: '5MB' },   // 5MB
    ];
    
    for (const fileSpec of fileSizes) {
      const buffer = Buffer.alloc(fileSpec.size);
      const startTime = performance.now();
      
      const response = await request.post(endpoint, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
        multipart: {
          file: {
            name: `test-${fileSpec.name}.jpg`,
            mimeType: 'image/jpeg',
            buffer: buffer,
          },
        },
      });
      
      const endTime = performance.now();
      const uploadTime = endTime - startTime;
      
      console.log(`File upload (${fileSpec.name}): ${uploadTime.toFixed(2)}ms`);
      
      // Assertions based on file size
      if (fileSpec.size <= 1024 * 1024) { // <= 1MB
        expect(uploadTime).toBeLessThan(2000); // < 2 seconds
      } else {
        expect(uploadTime).toBeLessThan(5000); // < 5 seconds
      }
    }
  });

  test('load test - database query performance', async ({ request }) => {
    // Test various database-intensive operations
    const queries = [
      {
        name: 'Search models',
        endpoint: '/api/v1/models?search=test&page=1&size=50',
      },
      {
        name: 'Financial aggregation',
        endpoint: '/api/v1/financials/stats?period=month',
      },
      {
        name: 'Chat history',
        endpoint: '/api/v1/chat/conversations?limit=100',
      },
    ];
    
    for (const query of queries) {
      const times: number[] = [];
      
      // Run each query multiple times
      for (let i = 0; i < 10; i++) {
        const startTime = performance.now();
        
        const response = await request.get(query.endpoint, {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        });
        
        const endTime = performance.now();
        times.push(endTime - startTime);
        
        expect(response.status()).toBe(200);
      }
      
      // Calculate statistics
      const avgTime = times.reduce((a, b) => a + b, 0) / times.length;
      const maxTime = Math.max(...times);
      const minTime = Math.min(...times);
      
      console.log(`${query.name}:
        - Average: ${avgTime.toFixed(2)}ms
        - Min: ${minTime.toFixed(2)}ms
        - Max: ${maxTime.toFixed(2)}ms
      `);
      
      // Database queries should be optimized
      expect(avgTime).toBeLessThan(1000); // < 1 second average
      expect(maxTime).toBeLessThan(2000); // < 2 seconds max
    }
  });
});

// Helper function to run load tests
async function runLoadTest(
  request: any,
  endpoint: string,
  method: string,
  totalRequests: number,
  concurrentRequests: number,
  options: any
): Promise<LoadTestResult> {
  const times: number[] = [];
  let failedRequests = 0;
  const startTime = performance.now();
  
  // Process requests in batches
  for (let i = 0; i < totalRequests; i += concurrentRequests) {
    const batch = Math.min(concurrentRequests, totalRequests - i);
    const promises = [];
    
    for (let j = 0; j < batch; j++) {
      const requestStartTime = performance.now();
      
      promises.push(
        request[method.toLowerCase()](endpoint, options)
          .then((response: any) => {
            const requestEndTime = performance.now();
            times.push(requestEndTime - requestStartTime);
            
            if (response.status() >= 400) {
              failedRequests++;
            }
            
            return response;
          })
          .catch(() => {
            failedRequests++;
            const requestEndTime = performance.now();
            times.push(requestEndTime - requestStartTime);
          })
      );
    }
    
    await Promise.all(promises);
  }
  
  const endTime = performance.now();
  const totalTime = (endTime - startTime) / 1000; // Convert to seconds
  
  return {
    endpoint,
    method,
    averageResponseTime: times.reduce((a, b) => a + b, 0) / times.length,
    maxResponseTime: Math.max(...times),
    minResponseTime: Math.min(...times),
    successRate: (totalRequests - failedRequests) / totalRequests,
    requestsPerSecond: totalRequests / totalTime,
    totalRequests,
    failedRequests,
  };
}