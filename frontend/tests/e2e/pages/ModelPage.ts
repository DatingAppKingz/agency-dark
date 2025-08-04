import { Page, Locator } from '@playwright/test';

export class ModelPage {
  readonly page: Page;
  readonly addModelButton: Locator;
  readonly modelGrid: Locator;
  readonly searchInput: Locator;
  readonly filterButton: Locator;
  readonly statusFilter: Locator;
  readonly modelCards: Locator;

  // Add Model Form
  readonly stageNameInput: Locator;
  readonly emailInput: Locator;
  readonly commissionRateInput: Locator;
  readonly submitButton: Locator;
  readonly cancelButton: Locator;

  constructor(page: Page) {
    this.page = page;
    this.addModelButton = page.getByRole('button', { name: /add model/i });
    this.modelGrid = page.getByTestId('models-grid');
    this.searchInput = page.getByPlaceholder(/search models/i);
    this.filterButton = page.getByRole('button', { name: /filter/i });
    this.statusFilter = page.getByRole('combobox', { name: /status/i });
    this.modelCards = page.getByTestId('model-card');

    // Form elements
    this.stageNameInput = page.getByLabel('Stage Name');
    this.emailInput = page.getByLabel('Email');
    this.commissionRateInput = page.getByLabel('Commission Rate');
    this.submitButton = page.getByRole('button', { name: /save|create/i });
    this.cancelButton = page.getByRole('button', { name: /cancel/i });
  }

  async goto() {
    await this.page.goto('/models');
  }

  async openAddModelForm() {
    await this.addModelButton.click();
    // Wait for modal/form to appear
    await this.stageNameInput.waitFor({ state: 'visible' });
  }

  async fillModelForm(data: {
    stageName: string;
    email: string;
    commissionRate: string;
  }) {
    await this.stageNameInput.fill(data.stageName);
    await this.emailInput.fill(data.email);
    await this.commissionRateInput.fill(data.commissionRate);
  }

  async submitForm() {
    await this.submitButton.click();
  }

  async searchModels(query: string) {
    await this.searchInput.fill(query);
    // Wait for search results
    await this.page.waitForTimeout(500); // Debounce delay
  }

  async filterByStatus(status: 'active' | 'inactive' | 'suspended' | 'all') {
    await this.filterButton.click();
    await this.statusFilter.selectOption(status);
  }

  async getModelCount() {
    await this.page.waitForLoadState('networkidle');
    return await this.modelCards.count();
  }

  async getModelByName(name: string) {
    return this.page.getByTestId('model-card').filter({ hasText: name });
  }

  async editModel(name: string) {
    const modelCard = await this.getModelByName(name);
    await modelCard.getByRole('button', { name: /edit/i }).click();
  }

  async viewModelDetails(name: string) {
    const modelCard = await this.getModelByName(name);
    await modelCard.click();
  }

  async toggleModelStatus(name: string) {
    const modelCard = await this.getModelByName(name);
    await modelCard.getByRole('switch').click();
  }
}