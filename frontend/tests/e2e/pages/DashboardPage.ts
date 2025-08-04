import { Page, Locator } from '@playwright/test';

export class DashboardPage {
  readonly page: Page;
  readonly profileMenu: Locator;
  readonly logoutButton: Locator;
  readonly welcomeMessage: Locator;
  readonly totalEarnings: Locator;
  readonly activeModels: Locator;
  readonly totalFans: Locator;
  readonly navigationMenu: Locator;

  constructor(page: Page) {
    this.page = page;
    this.profileMenu = page.getByRole('button', { name: /profile|avatar/i });
    this.logoutButton = page.getByRole('menuitem', { name: /logout|sign out/i });
    this.welcomeMessage = page.getByText(/welcome|dashboard/i);
    this.totalEarnings = page.getByTestId('total-earnings');
    this.activeModels = page.getByTestId('active-models');
    this.totalFans = page.getByTestId('total-fans');
    this.navigationMenu = page.getByRole('navigation');
  }

  async goto() {
    await this.page.goto('/dashboard');
  }

  async logout() {
    await this.profileMenu.click();
    await this.logoutButton.click();
  }

  async navigateToModels() {
    await this.navigationMenu.getByText('Models').click();
  }

  async navigateToFinancials() {
    await this.navigationMenu.getByText('Financials').click();
  }

  async navigateToChat() {
    await this.navigationMenu.getByText('Messages').click();
  }

  async waitForDashboardLoad() {
    await this.welcomeMessage.waitFor({ state: 'visible' });
    // Wait for data to load
    await this.page.waitForLoadState('networkidle');
  }

  async getStats() {
    await this.waitForDashboardLoad();
    
    const earnings = await this.totalEarnings.textContent();
    const models = await this.activeModels.textContent();
    const fans = await this.totalFans.textContent();

    return {
      earnings: earnings || '0',
      models: models || '0',
      fans: fans || '0',
    };
  }
}