import { Page, Locator } from '@playwright/test';

export class FinancialPage {
  readonly page: Page;
  readonly transactionsTab: Locator;
  readonly payoutsTab: Locator;
  readonly reportsTab: Locator;
  readonly settingsTab: Locator;
  
  // Transaction elements
  readonly transactionTable: Locator;
  readonly searchTransactions: Locator;
  readonly dateRangePicker: Locator;
  readonly exportButton: Locator;
  
  // Payout elements
  readonly requestPayoutButton: Locator;
  readonly payoutAmountInput: Locator;
  readonly payoutMethodSelect: Locator;
  readonly confirmPayoutButton: Locator;
  readonly pendingPayouts: Locator;
  
  // Financial summary
  readonly totalEarnings: Locator;
  readonly availableBalance: Locator;
  readonly pendingBalance: Locator;
  readonly lastPayout: Locator;

  constructor(page: Page) {
    this.page = page;
    
    // Tabs
    this.transactionsTab = page.getByRole('tab', { name: /transactions/i });
    this.payoutsTab = page.getByRole('tab', { name: /payouts/i });
    this.reportsTab = page.getByRole('tab', { name: /reports/i });
    this.settingsTab = page.getByRole('tab', { name: /settings/i });
    
    // Transaction elements
    this.transactionTable = page.getByRole('table', { name: /transactions/i });
    this.searchTransactions = page.getByPlaceholder(/search transactions/i);
    this.dateRangePicker = page.getByTestId('date-range-picker');
    this.exportButton = page.getByRole('button', { name: /export/i });
    
    // Payout elements
    this.requestPayoutButton = page.getByRole('button', { name: /request payout/i });
    this.payoutAmountInput = page.getByLabel('Payout Amount');
    this.payoutMethodSelect = page.getByLabel('Payment Method');
    this.confirmPayoutButton = page.getByRole('button', { name: /confirm payout/i });
    this.pendingPayouts = page.getByTestId('pending-payouts');
    
    // Summary
    this.totalEarnings = page.getByTestId('total-earnings');
    this.availableBalance = page.getByTestId('available-balance');
    this.pendingBalance = page.getByTestId('pending-balance');
    this.lastPayout = page.getByTestId('last-payout');
  }

  async goto() {
    await this.page.goto('/financials');
  }

  async navigateToTransactions() {
    await this.transactionsTab.click();
  }

  async navigateToPayouts() {
    await this.payoutsTab.click();
  }

  async navigateToReports() {
    await this.reportsTab.click();
  }

  async navigateToSettings() {
    await this.settingsTab.click();
  }

  async requestPayout(amount: string, method: string) {
    await this.requestPayoutButton.click();
    await this.payoutAmountInput.fill(amount);
    await this.payoutMethodSelect.selectOption(method);
    await this.confirmPayoutButton.click();
  }

  async filterTransactionsByDate(startDate: string, endDate: string) {
    await this.dateRangePicker.click();
    
    // Select start date
    const startDateInput = this.page.getByLabel('Start Date');
    await startDateInput.fill(startDate);
    
    // Select end date
    const endDateInput = this.page.getByLabel('End Date');
    await endDateInput.fill(endDate);
    
    // Apply filter
    await this.page.getByRole('button', { name: /apply/i }).click();
  }

  async searchTransaction(query: string) {
    await this.searchTransactions.fill(query);
    await this.page.waitForTimeout(500); // Debounce
  }

  async getTransactionCount() {
    const rows = this.transactionTable.getByRole('row');
    // Subtract 1 for header row
    return (await rows.count()) - 1;
  }

  async getFinancialSummary() {
    const earnings = await this.totalEarnings.textContent();
    const available = await this.availableBalance.textContent();
    const pending = await this.pendingBalance.textContent();
    const lastPayout = await this.lastPayout.textContent();

    return {
      totalEarnings: earnings || '$0',
      availableBalance: available || '$0',
      pendingBalance: pending || '$0',
      lastPayout: lastPayout || 'N/A',
    };
  }

  async downloadReport(reportType: 'monthly' | 'yearly' | 'tax') {
    await this.navigateToReports();
    
    const reportButton = this.page.getByRole('button', { 
      name: new RegExp(`download ${reportType}`, 'i') 
    });
    
    const downloadPromise = this.page.waitForEvent('download');
    await reportButton.click();
    
    return await downloadPromise;
  }

  async addPaymentMethod(type: 'bank' | 'paypal', details: any) {
    await this.navigateToSettings();
    
    const addMethodButton = this.page.getByRole('button', { 
      name: /add payment method/i 
    });
    await addMethodButton.click();
    
    // Select method type
    await this.page.getByLabel('Payment Method Type').selectOption(type);
    
    if (type === 'bank') {
      await this.page.getByLabel('Account Holder').fill(details.accountHolder);
      await this.page.getByLabel('Account Number').fill(details.accountNumber);
      await this.page.getByLabel('Routing Number').fill(details.routingNumber);
    } else if (type === 'paypal') {
      await this.page.getByLabel('PayPal Email').fill(details.email);
    }
    
    await this.page.getByRole('button', { name: /save/i }).click();
  }
}