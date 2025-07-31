// Test API endpoints
const API_URL = 'http://localhost:8000/api/v1';

// First, get a fresh token
async function getAuthToken() {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'admin@agencydark.com',
      password: 'admin123'
    })
  });
  const data = await response.json();
  return data.access_token;
}

async function testEndpoint(name, method, path, token, body = null) {
  console.log(`\n📍 Testing ${name}:`);
  console.log(`   ${method} ${API_URL}${path}`);
  
  try {
    const options = {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    };
    
    if (body) {
      options.body = JSON.stringify(body);
    }
    
    const response = await fetch(`${API_URL}${path}`, options);
    const data = await response.json();
    
    if (response.ok) {
      console.log(`   ✅ Success (${response.status})`);
      
      // Log summary of response
      if (Array.isArray(data)) {
        console.log(`   📊 Returned ${data.length} items`);
      } else if (data.items && Array.isArray(data.items)) {
        console.log(`   📊 Returned ${data.items.length} items (paginated)`);
      } else if (data.id) {
        console.log(`   📊 Returned object with ID: ${data.id}`);
      } else {
        console.log(`   📊 Response keys: ${Object.keys(data).join(', ')}`);
      }
    } else {
      console.log(`   ❌ Failed (${response.status}): ${data.detail || JSON.stringify(data)}`);
    }
    
    return { success: response.ok, data };
  } catch (error) {
    console.log(`   ❌ Error: ${error.message}`);
    return { success: false, error };
  }
}

async function runTests() {
  console.log('🚀 Starting API endpoint tests...\n');
  
  // Get auth token
  const token = await getAuthToken();
  console.log(`🔑 Got auth token: ${token.substring(0, 50)}...`);
  
  // Test endpoints
  const tests = [
    // Auth endpoints
    ['Current User', 'GET', '/auth/me'],
    
    // Analytics endpoints
    ['Dashboard Analytics', 'GET', '/analytics/dashboard'],
    ['Revenue Analytics', 'GET', '/analytics/revenue'],
    ['Chatter Performance', 'GET', '/analytics/chatters/performance'],
    
    // Models endpoints
    ['List Models', 'GET', '/models/'],
    
    // Conversations endpoints
    ['Active Conversations', 'GET', '/conversations/active'],
    ['Conversation Stats', 'GET', '/conversations/stats'],
    
    // Financial endpoints
    ['Financial Summary', 'GET', '/financial/summary'],
    ['Transactions', 'GET', '/financial/transactions'],
    ['Invoices', 'GET', '/financial/invoices'],
    ['Payouts', 'GET', '/financial/payouts'],
    
    // Tasks endpoints
    ['Active Tasks', 'GET', '/tasks/active'],
    ['Scheduled Tasks', 'GET', '/tasks/scheduled'],
  ];
  
  const results = {
    total: tests.length,
    successful: 0,
    failed: 0
  };
  
  for (const [name, method, path, body] of tests) {
    const result = await testEndpoint(name, method, path, token, body);
    if (result.success) {
      results.successful++;
    } else {
      results.failed++;
    }
  }
  
  console.log('\n📊 Test Summary:');
  console.log(`   Total: ${results.total}`);
  console.log(`   ✅ Successful: ${results.successful}`);
  console.log(`   ❌ Failed: ${results.failed}`);
  console.log(`   Success Rate: ${((results.successful / results.total) * 100).toFixed(1)}%`);
}

runTests().catch(console.error);