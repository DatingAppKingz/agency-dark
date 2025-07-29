/**
 * k6 Load Testing Script for Agency API
 * 
 * Usage:
 * k6 run k6_load_test.js
 * k6 run --vus 100 --duration 5m k6_load_test.js
 * k6 cloud k6_load_test.js  # For cloud execution
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import { randomString, randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const errorRate = new Rate('errors');
const apiLatency = new Trend('api_latency');
const successfulRequests = new Counter('successful_requests');
const activeUsers = new Gauge('active_users');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95% of requests under 500ms
    http_req_failed: ['rate<0.1'],                   // Error rate under 10%
    errors: ['rate<0.1'],                            // Custom error rate under 10%
  },
  ext: {
    loadimpact: {
      projectID: 123456,
      name: 'Agency API Load Test',
      distribution: {
        'amazon:us:ashburn': { loadZone: 'amazon:us:ashburn', percent: 60 },
        'amazon:eu:dublin': { loadZone: 'amazon:eu:dublin', percent: 40 },
      },
    },
  },
};

// Test data
const BASE_URL = __ENV.BASE_URL || 'https://api.agency.com';
const TEST_USER = __ENV.TEST_USER || 'loadtest';
const TEST_PASSWORD = __ENV.TEST_PASSWORD || 'loadtest123';

// Helper functions
function authenticateUser() {
  const loginRes = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    {
      username: TEST_USER,
      password: TEST_PASSWORD,
      grant_type: 'password',
    },
    {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }
  );

  check(loginRes, {
    'login successful': (r) => r.status === 200,
    'token received': (r) => r.json('access_token') !== undefined,
  });

  if (loginRes.status !== 200) {
    errorRate.add(1);
    return null;
  }

  errorRate.add(0);
  return loginRes.json('access_token');
}

function makeAuthHeaders(token) {
  return {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
}

// Test scenarios
export function setup() {
  // Setup code - create test data if needed
  console.log('Setting up test data...');
  
  const token = authenticateUser();
  if (!token) {
    throw new Error('Failed to authenticate during setup');
  }

  return { token };
}

export default function (data) {
  const token = data.token;
  const authHeaders = makeAuthHeaders(token);

  activeUsers.add(1);

  group('User Dashboard Flow', function () {
    // Load dashboard
    const dashboardRes = http.get(`${BASE_URL}/api/v1/dashboard`, authHeaders);
    apiLatency.add(dashboardRes.timings.duration);
    
    check(dashboardRes, {
      'dashboard loaded': (r) => r.status === 200,
    });

    if (dashboardRes.status === 200) {
      successfulRequests.add(1);
    } else {
      errorRate.add(1);
    }

    sleep(randomIntBetween(1, 3));

    // Get user profile
    const profileRes = http.get(`${BASE_URL}/api/v1/users/me`, authHeaders);
    
    check(profileRes, {
      'profile loaded': (r) => r.status === 200,
      'has user data': (r) => r.json('id') !== undefined,
    });

    sleep(randomIntBetween(1, 2));
  });

  group('Content Management Flow', function () {
    // List content
    const page = randomIntBetween(1, 10);
    const contentListRes = http.get(
      `${BASE_URL}/api/v1/content?page=${page}&limit=20`,
      authHeaders
    );
    
    check(contentListRes, {
      'content list loaded': (r) => r.status === 200,
      'has items': (r) => r.json('items') !== undefined,
    });

    // Create content (10% chance)
    if (Math.random() < 0.1) {
      const contentData = {
        title: `Load Test Content ${randomString(8)}`,
        body: 'This is content created during load testing',
        status: 'draft',
        tags: ['loadtest', 'k6'],
      };

      const createRes = http.post(
        `${BASE_URL}/api/v1/content`,
        JSON.stringify(contentData),
        authHeaders
      );

      check(createRes, {
        'content created': (r) => r.status === 201,
        'has content id': (r) => r.json('id') !== undefined,
      });

      if (createRes.status === 201) {
        const contentId = createRes.json('id');
        
        // View created content
        sleep(1);
        const viewRes = http.get(
          `${BASE_URL}/api/v1/content/${contentId}`,
          authHeaders
        );

        check(viewRes, {
          'content retrieved': (r) => r.status === 200,
        });
      }
    }

    sleep(randomIntBetween(2, 4));
  });

  group('Analytics Flow', function () {
    // Get analytics overview
    const analyticsRes = http.get(
      `${BASE_URL}/api/v1/analytics/overview?period=7d`,
      authHeaders
    );

    check(analyticsRes, {
      'analytics loaded': (r) => r.status === 200,
    });

    // Get detailed metrics (20% chance)
    if (Math.random() < 0.2) {
      const metricsRes = http.get(
        `${BASE_URL}/api/v1/analytics/metrics?metric=revenue&granularity=day&days=30`,
        authHeaders
      );

      check(metricsRes, {
        'metrics loaded': (r) => r.status === 200,
        'has data points': (r) => r.json('data') !== undefined,
      });
    }

    sleep(randomIntBetween(1, 3));
  });

  group('Search Operations', function () {
    const searchTerms = ['test', 'demo', 'example', 'guide', 'tutorial'];
    const searchTerm = randomItem(searchTerms);

    const searchRes = http.get(
      `${BASE_URL}/api/v1/content/search?q=${searchTerm}`,
      authHeaders
    );

    check(searchRes, {
      'search completed': (r) => r.status === 200,
      'has results': (r) => r.json('results') !== undefined,
    });

    apiLatency.add(searchRes.timings.duration);
    sleep(randomIntBetween(1, 2));
  });

  // Simulate think time between flows
  sleep(randomIntBetween(3, 7));

  activeUsers.add(-1);
}

export function teardown(data) {
  // Cleanup code - remove test data if needed
  console.log('Cleaning up test data...');
  
  const authHeaders = makeAuthHeaders(data.token);
  
  // Logout
  http.post(`${BASE_URL}/api/v1/auth/logout`, null, authHeaders);
}

// Advanced scenarios for different load patterns

/**
 * Spike Test - Sudden traffic increase
 */
export function spikeTest() {
  options.stages = [
    { duration: '30s', target: 10 },
    { duration: '10s', target: 200 },  // Spike!
    { duration: '1m', target: 200 },
    { duration: '10s', target: 10 },
    { duration: '30s', target: 10 },
  ];
}

/**
 * Stress Test - Find breaking point
 */
export function stressTest() {
  options.stages = [
    { duration: '2m', target: 100 },
    { duration: '2m', target: 200 },
    { duration: '2m', target: 300 },
    { duration: '2m', target: 400 },
    { duration: '2m', target: 500 },
    { duration: '5m', target: 500 },   // Stay at peak
  ];
}

/**
 * Soak Test - Extended duration
 */
export function soakTest() {
  options.stages = [
    { duration: '5m', target: 100 },
    { duration: '4h', target: 100 },   // Sustained load
    { duration: '5m', target: 0 },
  ];
}

// Custom scenario for API-heavy operations
export function apiScenario() {
  const token = authenticateUser();
  if (!token) return;

  const authHeaders = makeAuthHeaders(token);

  // Batch operations
  const batchRequests = {
    requests: [
      { method: 'GET', path: '/api/v1/users/me' },
      { method: 'GET', path: '/api/v1/content?limit=10' },
      { method: 'GET', path: '/api/v1/analytics/summary' },
    ],
  };

  const batchRes = http.post(
    `${BASE_URL}/api/v1/batch`,
    JSON.stringify(batchRequests),
    authHeaders
  );

  check(batchRes, {
    'batch request successful': (r) => r.status === 200,
    'all requests completed': (r) => {
      const responses = r.json('responses');
      return responses && responses.length === 3;
    },
  });

  // GraphQL query
  const graphqlQuery = {
    query: `
      query LoadTest {
        user(id: "me") {
          id
          username
          content(limit: 5) {
            id
            title
          }
        }
      }
    `,
  };

  const graphqlRes = http.post(
    `${BASE_URL}/api/v1/graphql`,
    JSON.stringify(graphqlQuery),
    authHeaders
  );

  check(graphqlRes, {
    'graphql query successful': (r) => r.status === 200,
    'has data': (r) => r.json('data') !== undefined,
  });

  sleep(1);
}

// WebSocket scenario (requires k6 WebSocket support)
export function websocketScenario() {
  // Note: This is a simplified example
  // Actual WebSocket testing requires the k6/ws module
  
  /*
  import ws from 'k6/ws';
  
  const url = 'wss://api.agency.com/ws';
  const params = { tags: { my_tag: 'websocket' } };

  const res = ws.connect(url, params, function (socket) {
    socket.on('open', () => {
      console.log('WebSocket connected');
      socket.send(JSON.stringify({ type: 'subscribe', channel: 'updates' }));
    });

    socket.on('message', (data) => {
      console.log('Message received: ', data);
    });

    socket.on('close', () => {
      console.log('WebSocket disconnected');
    });

    socket.setTimeout(() => {
      socket.close();
    }, 30000); // Close after 30 seconds
  });

  check(res, { 'status is 101': (r) => r && r.status === 101 });
  */
}