// Test login functionality
const API_URL = 'http://localhost:8000/api/v1';

async function testLogin() {
  console.log('Testing login functionality...\n');
  
  // Test credentials
  const credentials = [
    { email: 'admin@agencydark.com', password: 'admin123', expected: 'success' },
    { email: 'owner@premiumcreators.com', password: 'password123', expected: 'success' },
    { email: 'wrong@email.com', password: 'wrongpass', expected: 'fail' }
  ];
  
  for (const cred of credentials) {
    console.log(`Testing login for: ${cred.email}`);
    
    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: cred.email,
          password: cred.password
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        console.log(`✅ Login successful!`);
        console.log(`   User: ${data.user.email} (${data.user.role})`);
        console.log(`   Token: ${data.access_token.substring(0, 50)}...`);
      } else {
        console.log(`❌ Login failed: ${data.detail}`);
      }
      
      // Test protected endpoint with token
      if (response.ok) {
        const meResponse = await fetch(`${API_URL}/users/me`, {
          headers: {
            'Authorization': `Bearer ${data.access_token}`
          }
        });
        
        if (meResponse.ok) {
          const userData = await meResponse.json();
          console.log(`✅ Protected endpoint accessible`);
          console.log(`   User ID: ${userData.id}`);
        } else {
          console.log(`❌ Protected endpoint failed`);
        }
      }
      
    } catch (error) {
      console.log(`❌ Error: ${error.message}`);
    }
    
    console.log('---\n');
  }
}

testLogin();