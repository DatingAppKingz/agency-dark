/**
 * Global Teardown for E2E Tests
 * Runs once after all tests complete
 */

import { FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs/promises';

async function globalTeardown(config: FullConfig) {
  console.log('🏁 Starting global teardown...');
  
  const testDataDir = path.join(__dirname, 'test-data');
  
  // Clean up test data (if configured)
  if (process.env.CLEANUP_TEST_DATA === 'true') {
    console.log('🧹 Cleaning up test data...');
    
    try {
      // Remove test data files
      await fs.rm(testDataDir, { recursive: true, force: true });
      console.log('✅ Test data cleaned up');
    } catch (error) {
      console.error('❌ Failed to clean up test data:', error);
    }
  }
  
  // Clean up test database (if configured)
  if (process.env.CLEANUP_TEST_DB === 'true') {
    console.log('🗑️ Cleaning up test database...');
    
    try {
      // Database cleanup would go here
      // For example: DROP test tables, remove test users, etc.
      console.log('✅ Test database cleaned up');
    } catch (error) {
      console.error('❌ Failed to clean up test database:', error);
    }
  }
  
  // Generate test report summary
  if (process.env.GENERATE_SUMMARY === 'true') {
    console.log('📊 Generating test summary...');
    
    try {
      const reportDir = path.join(__dirname, '../../playwright-report');
      const summaryPath = path.join(reportDir, 'summary.json');
      
      // Check if report exists
      const reportExists = await fs.access(reportDir).then(() => true).catch(() => false);
      
      if (reportExists) {
        // Read test results
        const resultsPath = path.join(__dirname, '../../test-results.json');
        const resultsExist = await fs.access(resultsPath).then(() => true).catch(() => false);
        
        if (resultsExist) {
          const results = JSON.parse(await fs.readFile(resultsPath, 'utf-8'));
          
          // Create summary
          const summary = {
            testRunId: process.env.TEST_RUN_ID,
            timestamp: new Date().toISOString(),
            totalTests: results.tests?.length || 0,
            passed: results.tests?.filter((t: any) => t.status === 'passed').length || 0,
            failed: results.tests?.filter((t: any) => t.status === 'failed').length || 0,
            skipped: results.tests?.filter((t: any) => t.status === 'skipped').length || 0,
            duration: results.duration || 0,
            baseUrl: process.env.BASE_URL,
            apiUrl: process.env.API_URL,
          };
          
          await fs.writeFile(summaryPath, JSON.stringify(summary, null, 2));
          
          console.log('📈 Test Summary:');
          console.log(`   Total: ${summary.totalTests}`);
          console.log(`   ✅ Passed: ${summary.passed}`);
          console.log(`   ❌ Failed: ${summary.failed}`);
          console.log(`   ⏭️ Skipped: ${summary.skipped}`);
          console.log(`   ⏱️ Duration: ${(summary.duration / 1000).toFixed(2)}s`);
        }
      }
    } catch (error) {
      console.error('❌ Failed to generate summary:', error);
    }
  }
  
  // Archive test artifacts (if configured)
  if (process.env.ARCHIVE_ARTIFACTS === 'true') {
    console.log('📦 Archiving test artifacts...');
    
    try {
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      const archiveDir = path.join(__dirname, '../../test-archives', timestamp);
      
      await fs.mkdir(archiveDir, { recursive: true });
      
      // Copy playwright report
      const reportDir = path.join(__dirname, '../../playwright-report');
      const reportExists = await fs.access(reportDir).then(() => true).catch(() => false);
      
      if (reportExists) {
        await fs.cp(reportDir, path.join(archiveDir, 'playwright-report'), { recursive: true });
      }
      
      // Copy screenshots and videos
      const testResultsDir = path.join(__dirname, '../../test-results');
      const testResultsExist = await fs.access(testResultsDir).then(() => true).catch(() => false);
      
      if (testResultsExist) {
        await fs.cp(testResultsDir, path.join(archiveDir, 'test-results'), { recursive: true });
      }
      
      console.log(`✅ Test artifacts archived to: ${archiveDir}`);
    } catch (error) {
      console.error('❌ Failed to archive artifacts:', error);
    }
  }
  
  // Stop any remaining services
  if (process.env.STOP_SERVICES === 'true') {
    console.log('🛑 Stopping test services...');
    
    try {
      // Service shutdown would go here
      // For example: stop mock servers, close database connections, etc.
      console.log('✅ Test services stopped');
    } catch (error) {
      console.error('❌ Failed to stop services:', error);
    }
  }
  
  // Clean up environment variables
  delete process.env.TEST_RUN_ID;
  
  console.log('✨ Global teardown completed');
}

export default globalTeardown;