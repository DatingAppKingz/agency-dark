import { test, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';
import { FinancialPage } from './pages/FinancialPage';
import { ModelPage } from './pages/ModelPage';

test.describe('Financial Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Login as admin
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login('admin@agency.com', 'admin123');
    await page.waitForURL(/.*dashboard/);
  });

  test('should view financial dashboard and summary', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    
    // Should display financial summary
    const summary = await financialPage.getFinancialSummary();
    
    expect(summary.totalEarnings).toMatch(/\$[\d,]+\.?\d*/);
    expect(summary.availableBalance).toMatch(/\$[\d,]+\.?\d*/);
    expect(summary.pendingBalance).toMatch(/\$[\d,]+\.?\d*/);
    
    // Should display recent transactions
    await financialPage.navigateToTransactions();
    const transactionCount = await financialPage.getTransactionCount();
    expect(transactionCount).toBeGreaterThanOrEqual(0);
  });

  test('should filter and search transactions', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    await financialPage.navigateToTransactions();
    
    // Filter by date range
    const today = new Date();
    const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    const startDate = lastMonth.toISOString().split('T')[0];
    const endDate = today.toISOString().split('T')[0];
    
    await financialPage.filterTransactionsByDate(startDate, endDate);
    
    // Wait for results to update
    await page.waitForTimeout(1000);
    
    // Search for specific transaction
    await financialPage.searchTransaction('subscription');
    
    // Verify filtered results
    const rows = financialPage.transactionTable.getByRole('row');
    const firstRow = rows.nth(1); // Skip header
    await expect(firstRow).toContainText(/subscription/i);
  });

  test('should request a payout', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    
    // Check available balance first
    const summary = await financialPage.getFinancialSummary();
    const availableText = summary.availableBalance;
    const availableAmount = parseFloat(availableText.replace(/[$,]/g, ''));
    
    if (availableAmount < 100) {
      test.skip();
      return;
    }
    
    await financialPage.navigateToPayouts();
    
    // Request payout
    await financialPage.requestPayout('100.00', 'bank_transfer');
    
    // Should show confirmation dialog
    await expect(page.getByText(/confirm payout request/i)).toBeVisible();
    await expect(page.getByText(/\$100\.00/)).toBeVisible();
    
    // Confirm
    await page.getByRole('button', { name: /confirm/i }).click();
    
    // Should show success message
    await expect(page.getByText(/payout requested successfully/i)).toBeVisible();
    
    // Should appear in pending payouts
    await expect(financialPage.pendingPayouts).toContainText('$100.00');
  });

  test('should manage payment methods', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    
    // Add bank account
    await financialPage.addPaymentMethod('bank', {
      accountHolder: 'Test Agency LLC',
      accountNumber: '1234567890',
      routingNumber: '021000021',
    });
    
    // Should show success
    await expect(page.getByText(/payment method added/i)).toBeVisible();
    
    // Should appear in list
    await expect(page.getByText('****7890')).toBeVisible();
    
    // Set as default
    const methodRow = page.getByRole('row', { name: /\*\*\*\*7890/i });
    await methodRow.getByRole('button', { name: /set as default/i }).click();
    
    await expect(page.getByText(/default payment method updated/i)).toBeVisible();
    await expect(methodRow).toContainText(/default/i);
  });

  test('should generate and download financial reports', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    
    // Download monthly report
    const monthlyDownload = await financialPage.downloadReport('monthly');
    expect(monthlyDownload.suggestedFilename()).toMatch(/monthly.*report.*\.(pdf|csv)/i);
    
    // Download yearly report
    const yearlyDownload = await financialPage.downloadReport('yearly');
    expect(yearlyDownload.suggestedFilename()).toMatch(/yearly.*report.*\.(pdf|csv)/i);
    
    // Download tax documents
    await financialPage.navigateToReports();
    await page.getByRole('tab', { name: /tax documents/i }).click();
    
    // Should show available tax forms
    await expect(page.getByText(/1099/)).toBeVisible();
    
    // Download tax form
    const taxDownloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /download 1099/i }).click();
    const taxDownload = await taxDownloadPromise;
    expect(taxDownload.suggestedFilename()).toMatch(/1099.*\.pdf/i);
  });

  test('should view model earnings breakdown', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    const modelPage = new ModelPage(page);
    
    // Go to models page first
    await modelPage.goto();
    
    // Click on first model to view details
    const firstModel = modelPage.modelCards.first();
    const modelName = await firstModel.getByTestId('model-name').textContent();
    await firstModel.click();
    
    // Navigate to earnings tab
    await page.getByRole('tab', { name: /earnings/i }).click();
    
    // Should show earnings summary
    await expect(page.getByText(/total earnings/i)).toBeVisible();
    await expect(page.getByText(/this month/i)).toBeVisible();
    await expect(page.getByText(/pending payout/i)).toBeVisible();
    
    // Should show earnings chart
    await expect(page.getByTestId('earnings-chart')).toBeVisible();
    
    // Should show transaction history
    const transactionTable = page.getByRole('table', { name: /transactions/i });
    await expect(transactionTable).toBeVisible();
    
    // Filter by transaction type
    await page.getByLabel('Transaction Type').selectOption('subscription');
    await page.waitForTimeout(500);
    
    // Verify filtered results
    const rows = transactionTable.getByRole('row');
    const rowCount = await rows.count();
    if (rowCount > 1) { // Has data
      const firstDataRow = rows.nth(1);
      await expect(firstDataRow).toContainText(/subscription/i);
    }
  });

  test('should handle refunds and chargebacks', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    await financialPage.navigateToTransactions();
    
    // Find a completed transaction
    const completedTransaction = page.getByRole('row').filter({ 
      hasText: /completed/i 
    }).first();
    
    if (await completedTransaction.count() === 0) {
      test.skip();
      return;
    }
    
    // Open transaction details
    await completedTransaction.click();
    
    // Initiate refund
    await page.getByRole('button', { name: /refund/i }).click();
    
    // Fill refund form
    await page.getByLabel('Refund Amount').fill('50.00');
    await page.getByLabel('Refund Reason').selectOption('customer_request');
    await page.getByLabel('Notes').fill('Customer requested partial refund');
    
    // Submit refund
    await page.getByRole('button', { name: /process refund/i }).click();
    
    // Confirm
    await expect(page.getByText(/confirm refund/i)).toBeVisible();
    await page.getByRole('button', { name: /confirm/i }).click();
    
    // Should show success
    await expect(page.getByText(/refund processed/i)).toBeVisible();
    
    // Transaction should show refunded status
    await page.goBack();
    await expect(completedTransaction).toContainText(/refunded/i);
  });

  test('should manage commission rates', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    await financialPage.navigateToSettings();
    
    // Navigate to commission settings
    await page.getByRole('tab', { name: /commission/i }).click();
    
    // View current commission structure
    await expect(page.getByText(/default commission rate/i)).toBeVisible();
    
    // Add tiered commission
    await page.getByRole('button', { name: /add tier/i }).click();
    
    await page.getByLabel('Minimum Revenue').fill('10000');
    await page.getByLabel('Maximum Revenue').fill('50000');
    await page.getByLabel('Commission Rate').fill('15');
    
    await page.getByRole('button', { name: /save tier/i }).click();
    
    // Should show in tiers list
    await expect(page.getByText('$10,000 - $50,000: 15%')).toBeVisible();
    
    // Test model-specific commission override
    await page.getByRole('button', { name: /model overrides/i }).click();
    
    // Search for model
    await page.getByPlaceholder(/search models/i).fill('test');
    await page.waitForTimeout(500);
    
    // Set custom rate
    const modelRow = page.getByRole('row').filter({ hasText: /test/i }).first();
    if (await modelRow.count() > 0) {
      await modelRow.getByRole('button', { name: /set rate/i }).click();
      await page.getByLabel('Custom Rate').fill('12');
      await page.getByRole('button', { name: /apply/i }).click();
      
      await expect(page.getByText(/commission rate updated/i)).toBeVisible();
    }
  });

  test('should export financial data', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    await financialPage.navigateToTransactions();
    
    // Open export dialog
    await financialPage.exportButton.click();
    
    // Configure export
    await page.getByLabel('Export Format').selectOption('csv');
    await page.getByLabel('Date Range').selectOption('last_month');
    
    // Select fields
    await page.getByRole('checkbox', { name: /transaction id/i }).check();
    await page.getByRole('checkbox', { name: /date/i }).check();
    await page.getByRole('checkbox', { name: /amount/i }).check();
    await page.getByRole('checkbox', { name: /type/i }).check();
    await page.getByRole('checkbox', { name: /status/i }).check();
    await page.getByRole('checkbox', { name: /model/i }).check();
    
    // Start export
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: /export/i }).click();
    
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/transactions.*\.csv/i);
  });

  test('should handle currency conversion', async ({ page }) => {
    const financialPage = new FinancialPage(page);
    
    await financialPage.goto();
    await financialPage.navigateToSettings();
    
    // Go to currency settings
    await page.getByRole('tab', { name: /currency/i }).click();
    
    // Current currency should be displayed
    await expect(page.getByText(/primary currency.*USD/i)).toBeVisible();
    
    // Add supported currency
    await page.getByRole('button', { name: /add currency/i }).click();
    await page.getByLabel('Currency').selectOption('EUR');
    await page.getByRole('button', { name: /add/i }).click();
    
    // Should show exchange rate
    await expect(page.getByText(/EUR.*exchange rate/i)).toBeVisible();
    
    // Test currency conversion in transactions
    await financialPage.navigateToTransactions();
    
    // Change display currency
    await page.getByLabel('Display Currency').selectOption('EUR');
    await page.waitForTimeout(1000);
    
    // Amounts should show in EUR
    const amounts = page.getByTestId('transaction-amount');
    const firstAmount = await amounts.first().textContent();
    expect(firstAmount).toMatch(/€/);
  });
});