/**
 * Global Setup for E2E Tests
 * Runs once before all tests
 */

import { chromium, FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs/promises';

async function globalSetup(config: FullConfig) {
  console.log('🚀 Starting global setup for E2E tests...');
  
  // Create test data directory if it doesn't exist
  const testDataDir = path.join(__dirname, 'test-data');
  try {
    await fs.mkdir(testDataDir, { recursive: true });
  } catch (error) {
    console.log('Test data directory already exists');
  }
  
  // Set up test database (if needed)
  if (process.env.SETUP_TEST_DB === 'true') {
    console.log('📦 Setting up test database...');
    // Database setup would go here
  }
  
  // Create test users and OAuth clients
  if (!process.env.SKIP_SEED_DATA) {
    console.log('🌱 Seeding test data...');
    
    const browser = await chromium.launch();
    const context = await browser.newContext();
    const page = await context.newPage();
    
    try {
      // Create test agency
      const testAgency = {
        id: 'test-agency-id',
        name: 'Test Agency',
        subdomain: 'test',
      };
      
      // Create test users
      const testUsers = [
        {
          email: 'admin@test.com',
          password: 'Admin123!',
          role: 'agency_admin',
          agency_id: testAgency.id,
        },
        {
          email: 'model@test.com',
          password: 'Model123!',
          role: 'model',
          agency_id: testAgency.id,
        },
        {
          email: 'chatter@test.com',
          password: 'Chatter123!',
          role: 'chatter',
          agency_id: testAgency.id,
        },
      ];
      
      // Create OAuth test clients
      const testOAuthClients = [
        {
          client_id: 'test_client_public',
          client_name: 'Test Public Client',
          client_type: 'public',
          redirect_uris: ['http://localhost:3000/callback'],
          grant_types: ['authorization_code', 'refresh_token'],
          scope: 'read write',
          agency_id: testAgency.id,
        },
        {
          client_id: 'test_client_confidential',
          client_secret: 'test_secret_123',
          client_name: 'Test Confidential Client',
          client_type: 'confidential',
          redirect_uris: ['http://localhost:3000/callback'],
          grant_types: ['authorization_code', 'refresh_token', 'client_credentials'],
          scope: 'read write admin',
          agency_id: testAgency.id,
        },
      ];
      
      // Save test data to files for use in tests
      await fs.writeFile(
        path.join(testDataDir, 'test-agency.json'),
        JSON.stringify(testAgency, null, 2)
      );
      
      await fs.writeFile(
        path.join(testDataDir, 'test-users.json'),
        JSON.stringify(testUsers, null, 2)
      );
      
      await fs.writeFile(
        path.join(testDataDir, 'test-oauth-clients.json'),
        JSON.stringify(testOAuthClients, null, 2)
      );
      
      console.log('✅ Test data seeded successfully');
    } catch (error) {
      console.error('❌ Failed to seed test data:', error);
      throw error;
    } finally {
      await browser.close();
    }
  }
  
  // Set up environment variables
  process.env.TEST_RUN_ID = Date.now().toString();
  process.env.BASE_URL = config.projects[0].use?.baseURL || 'http://localhost:3000';
  process.env.API_URL = process.env.API_URL || 'http://localhost:8000';
  
  // Create authentication state (for reuse across tests)
  if (!process.env.SKIP_AUTH_SETUP) {
    console.log('🔐 Setting up authentication state...');
    
    const browser = await chromium.launch();
    const context = await browser.newContext();
    const page = await context.newPage();
    
    try {
      // Login as admin user
      await page.goto(`${process.env.BASE_URL}/login`);
      await page.fill('input[name="email"]', 'admin@test.com');
      await page.fill('input[name="password"]', 'Admin123!');
      await page.click('button[type="submit"]');
      await page.waitForURL('**/dashboard');
      
      // Save authentication state
      await context.storageState({ 
        path: path.join(testDataDir, 'auth-state-admin.json') 
      });
      
      console.log('✅ Authentication state saved');
    } catch (error) {
      console.error('❌ Failed to set up authentication:', error);
      // Continue anyway - tests can handle unauthenticated state
    } finally {
      await browser.close();
    }
  }
  
  // Set up mock OAuth providers (if needed)
  if (process.env.USE_MOCK_OAUTH === 'true') {
    console.log('🎭 Setting up mock OAuth providers...');
    // Mock OAuth provider setup would go here
  }
  
  // Clear any previous test artifacts
  const artifactsDir = path.join(__dirname, '../../playwright-report');
  try {
    await fs.rm(artifactsDir, { recursive: true, force: true });
    console.log('🧹 Cleared previous test artifacts');
  } catch (error) {
    // Directory might not exist, that's okay
  }
  
  console.log('✨ Global setup completed successfully');
  console.log(`📊 Test run ID: ${process.env.TEST_RUN_ID}`);
  console.log(`🌐 Base URL: ${process.env.BASE_URL}`);
  console.log(`🔌 API URL: ${process.env.API_URL}`);
  
  return async () => {
    // This function will be called as global teardown
    console.log('🧹 Running global teardown...');
  };
}

export default globalSetup;