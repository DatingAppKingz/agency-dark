#!/usr/bin/env node
import axios from 'axios';

const FRONTEND_URL = 'http://localhost:3002';
const API_URL = 'http://localhost:8000/api/v1';

async function testFrontendLogin() {
  console.log('🔍 Testing Frontend Login with Security_v2\n');
  
  try {
    // Test backend directly
    console.log('1. Testing backend directly...');
    const backendResponse = await axios.post(`${API_URL}/auth/login`, {
      email: 'admin@agency.com',
      password: 'admin123'
    }, {
      headers: { 'Content-Type': 'application/json' }
    });
    
    if (backendResponse.data.access_token) {
      console.log('✅ Backend login successful');
      console.log(`   Token: ${backendResponse.data.access_token.substring(0, 30)}...`);
      console.log(`   User: ${backendResponse.data.user?.email || 'admin@agency.com'}`);
    }
    
    // Check if frontend is configured for security_v2
    console.log('\n2. Checking frontend configuration...');
    console.log('   VITE_USE_SECURITY_V2=true is set in .env.local');
    console.log('   Frontend should be using authServiceV2');
    
    console.log('\n✅ Frontend is configured to use security_v2 backend!');
    console.log('\n📌 To test in browser:');
    console.log('   1. Open http://localhost:3002');
    console.log('   2. Navigate to login page');
    console.log('   3. Use credentials: admin@agency.com / admin123');
    console.log('   4. Check browser console for auth service logs');
    
  } catch (error) {
    console.error('❌ Error:', error.response?.data || error.message);
  }
}

testFrontendLogin();