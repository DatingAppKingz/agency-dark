import { test, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';
import { ModelPage } from './pages/ModelPage';
import { DashboardPage } from './pages/DashboardPage';

test.describe('Model Onboarding Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin before each test
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('admin@agency.com', 'admin123');
    
    // Wait for dashboard to load
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.waitForDashboardLoad();
  });

  test('should create a new model successfully', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    const initialCount = await modelPage.getModelCount();
    
    // Open add model form
    await modelPage.openAddModelForm();
    
    // Fill in model details
    await modelPage.fillModelForm({
      stageName: 'TestModel123',
      email: 'testmodel@example.com',
      commissionRate: '20',
    });
    
    // Submit form
    await modelPage.submitForm();
    
    // Should show success message
    await expect(page.getByText(/model created successfully/i)).toBeVisible();
    
    // Should add model to the list
    const newCount = await modelPage.getModelCount();
    expect(newCount).toBe(initialCount + 1);
    
    // Should display the new model
    const newModel = await modelPage.getModelByName('TestModel123');
    await expect(newModel).toBeVisible();
  });

  test('should validate model form inputs', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    await modelPage.openAddModelForm();
    
    // Try to submit empty form
    await modelPage.submitButton.click();
    
    // Should show validation errors
    await expect(page.getByText('Stage name is required')).toBeVisible();
    await expect(page.getByText('Email is required')).toBeVisible();
    
    // Test email validation
    await modelPage.emailInput.fill('invalid-email');
    await modelPage.submitButton.click();
    await expect(page.getByText('Invalid email format')).toBeVisible();
    
    // Test commission rate validation
    await modelPage.commissionRateInput.fill('150');
    await modelPage.submitButton.click();
    await expect(page.getByText('Commission rate must be between 0 and 100')).toBeVisible();
  });

  test('should complete full model onboarding flow', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    await modelPage.openAddModelForm();
    
    // Step 1: Basic Information
    await modelPage.fillModelForm({
      stageName: 'OnboardingTestModel',
      email: 'onboarding@example.com',
      commissionRate: '25',
    });
    
    // Add additional details
    await page.getByLabel('Biography').fill('Professional model with 5 years experience');
    await page.getByLabel('Phone').fill('+1234567890');
    
    // Continue to next step
    await page.getByRole('button', { name: /next|continue/i }).click();
    
    // Step 2: Document Upload
    await expect(page.getByText(/upload documents/i)).toBeVisible();
    
    // Upload ID verification
    const idFileInput = page.locator('input[type="file"]').first();
    await idFileInput.setInputFiles('./tests/fixtures/sample-id.jpg');
    
    // Upload proof of age
    const ageFileInput = page.locator('input[type="file"]').nth(1);
    await ageFileInput.setInputFiles('./tests/fixtures/sample-age-proof.pdf');
    
    await page.getByRole('button', { name: /next|continue/i }).click();
    
    // Step 3: Platform Integration
    await expect(page.getByText(/connect platforms/i)).toBeVisible();
    
    // Connect OnlyFans
    await page.getByRole('button', { name: /connect onlyfans/i }).click();
    await page.getByLabel('OnlyFans Username').fill('testmodel123');
    await page.getByRole('button', { name: /verify|connect/i }).click();
    
    // Wait for verification
    await expect(page.getByText(/connected successfully/i)).toBeVisible();
    
    await page.getByRole('button', { name: /next|continue/i }).click();
    
    // Step 4: Payment Setup
    await expect(page.getByText(/payment information/i)).toBeVisible();
    
    // Add bank account
    await page.getByLabel('Account Holder Name').fill('Test Model');
    await page.getByLabel('Account Number').fill('1234567890');
    await page.getByLabel('Routing Number').fill('021000021');
    
    // Complete onboarding
    await page.getByRole('button', { name: /complete|finish/i }).click();
    
    // Should show success
    await expect(page.getByText(/onboarding completed/i)).toBeVisible();
    
    // Should redirect to model dashboard
    await expect(page).toHaveURL(/.*models.*onboarding.*success/);
  });

  test('should edit existing model information', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    
    // Find and edit first model
    const firstModel = modelPage.modelCards.first();
    const modelName = await firstModel.getByTestId('model-name').textContent();
    
    await modelPage.editModel(modelName!);
    
    // Update commission rate
    await modelPage.commissionRateInput.clear();
    await modelPage.commissionRateInput.fill('30');
    
    // Update biography
    const bioField = page.getByLabel('Biography');
    await bioField.clear();
    await bioField.fill('Updated biography text');
    
    // Save changes
    await page.getByRole('button', { name: /save|update/i }).click();
    
    // Should show success message
    await expect(page.getByText(/updated successfully/i)).toBeVisible();
    
    // Verify changes persisted
    await page.reload();
    await modelPage.editModel(modelName!);
    
    const updatedRate = await modelPage.commissionRateInput.inputValue();
    expect(updatedRate).toBe('30');
  });

  test('should manage model status', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    
    // Create a test model first
    await modelPage.openAddModelForm();
    await modelPage.fillModelForm({
      stageName: 'StatusTestModel',
      email: 'status@example.com',
      commissionRate: '20',
    });
    await modelPage.submitForm();
    
    // Wait for model to appear
    await page.waitForTimeout(1000);
    
    // Toggle model status
    await modelPage.toggleModelStatus('StatusTestModel');
    
    // Should show confirmation dialog
    await expect(page.getByText(/confirm status change/i)).toBeVisible();
    await page.getByRole('button', { name: /confirm/i }).click();
    
    // Status should be updated
    const modelCard = await modelPage.getModelByName('StatusTestModel');
    await expect(modelCard.getByText(/inactive/i)).toBeVisible();
    
    // Toggle back to active
    await modelPage.toggleModelStatus('StatusTestModel');
    await page.getByRole('button', { name: /confirm/i }).click();
    await expect(modelCard.getByText(/active/i)).toBeVisible();
  });

  test('should upload and verify model documents', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    
    // Navigate to first model's details
    const firstModel = modelPage.modelCards.first();
    await firstModel.click();
    
    // Go to documents tab
    await page.getByRole('tab', { name: /documents/i }).click();
    
    // Upload new document
    await page.getByRole('button', { name: /upload document/i }).click();
    
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles('./tests/fixtures/sample-contract.pdf');
    
    // Select document type
    await page.getByLabel('Document Type').selectOption('contract');
    
    // Add description
    await page.getByLabel('Description').fill('Model contract for 2024');
    
    // Upload
    await page.getByRole('button', { name: /upload/i }).click();
    
    // Should show success
    await expect(page.getByText(/document uploaded/i)).toBeVisible();
    
    // Document should appear in list
    await expect(page.getByText('sample-contract.pdf')).toBeVisible();
    
    // Admin can verify document
    const documentRow = page.getByRole('row', { name: /sample-contract.pdf/i });
    await documentRow.getByRole('button', { name: /verify/i }).click();
    
    // Add verification note
    await page.getByLabel('Verification Note').fill('Document verified and approved');
    await page.getByRole('button', { name: /approve/i }).click();
    
    // Should show verified status
    await expect(documentRow.getByText(/verified/i)).toBeVisible();
  });

  test('should handle bulk model operations', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    
    // Select multiple models
    const checkboxes = page.getByRole('checkbox', { name: /select model/i });
    await checkboxes.first().check();
    await checkboxes.nth(1).check();
    await checkboxes.nth(2).check();
    
    // Bulk actions should appear
    const bulkActions = page.getByTestId('bulk-actions');
    await expect(bulkActions).toBeVisible();
    
    // Bulk update commission rate
    await bulkActions.getByRole('button', { name: /update commission/i }).click();
    
    const bulkCommissionInput = page.getByLabel('New Commission Rate');
    await bulkCommissionInput.fill('18');
    
    await page.getByRole('button', { name: /apply to selected/i }).click();
    
    // Confirm bulk update
    await expect(page.getByText(/update 3 models/i)).toBeVisible();
    await page.getByRole('button', { name: /confirm/i }).click();
    
    // Should show success
    await expect(page.getByText(/3 models updated/i)).toBeVisible();
  });

  test('should export model data', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    
    // Open export dialog
    await page.getByRole('button', { name: /export/i }).click();
    
    // Select export format
    await page.getByLabel('Export Format').selectOption('csv');
    
    // Select fields to export
    await page.getByRole('checkbox', { name: /stage name/i }).check();
    await page.getByRole('checkbox', { name: /email/i }).check();
    await page.getByRole('checkbox', { name: /commission rate/i }).check();
    await page.getByRole('checkbox', { name: /status/i }).check();
    
    // Apply filters
    await page.getByRole('checkbox', { name: /active models only/i }).check();
    
    // Start export
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /download/i }).click();
    
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/models.*\.csv/);
  });

  test('should search and filter models', async ({ page }) => {
    const modelPage = new ModelPage(page);
    
    await modelPage.goto();
    
    // Search by name
    await modelPage.searchModels('test');
    
    // Should filter results
    const visibleModels = await modelPage.modelCards.count();
    const allText = await page.getByTestId('model-card').allTextContents();
    
    // All visible models should contain 'test' (case insensitive)
    allText.forEach(text => {
      expect(text.toLowerCase()).toContain('test');
    });
    
    // Clear search
    await modelPage.searchInput.clear();
    
    // Filter by status
    await modelPage.filterByStatus('active');
    
    // All models should be active
    const statusBadges = page.getByTestId('model-status');
    const statuses = await statusBadges.allTextContents();
    statuses.forEach(status => {
      expect(status.toLowerCase()).toBe('active');
    });
    
    // Apply multiple filters
    await page.getByRole('button', { name: /more filters/i }).click();
    
    await page.getByLabel('Min Earnings').fill('1000');
    await page.getByLabel('Max Earnings').fill('10000');
    await page.getByLabel('Has Documents').check();
    
    await page.getByRole('button', { name: /apply filters/i }).click();
    
    // Results should be filtered
    const filteredCount = await modelPage.getModelCount();
    expect(filteredCount).toBeLessThanOrEqual(visibleModels);
  });
});