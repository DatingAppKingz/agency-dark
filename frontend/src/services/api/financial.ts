import apiClient from './client';
import type { PaginatedResponse, QueryParams } from '@/types/api';
import type {
  Transaction,
  Payout,
  PaymentMethod,
  Revenue,
  Commission,
  Invoice,
  FinancialReport,
  FinancialSummary } from '@/types/financial';

export interface TransactionFilters extends QueryParams {
  type?: Transaction['type'];
  status?: Transaction['status'];
  start_date?: string;
  end_date?: string;
  user_id?: string;
  model_id?: string;
  agency_id?: string;
}

export interface PayoutFilters extends QueryParams {
  status?: Payout['status'];
  method?: Payout['method'];
  start_date?: string;
  end_date?: string;
  user_id?: string;
  model_id?: string;
  agency_id?: string;
}

export interface RevenueParams {
  period: Revenue['period'];
  start_date?: string;
  end_date?: string;
  model_id?: string;
  agency_id?: string;
}

export interface InvoiceFilters extends QueryParams {
  status?: Invoice['status'];
  start_date?: string;
  end_date?: string;
}

export const financialApi = {
  // Commission Rules
  async getCommissionRules(params?: { agency_id?: string; model_id?: string; include_historical?: boolean }) {
    const { data } = await apiClient.get('/financial/commission/rules', { params });
    return data;
  },

  async createCommissionRule(ruleData: any) {
    const { data } = await apiClient.post('/financial/commission/rules', ruleData);
    return data;
  },

  async updateCommissionRule(ruleId: string, updateData: any) {
    const { data } = await apiClient.put(`/financial/commission/rules/${ruleId}`, updateData);
    return data;
  },

  async calculateCommission(params: {
    gross_amount: number;
    model_id: string;
    calculation_date?: string;
  }) {
    const { data } = await apiClient.post('/financial/commission/calculate', null, { params });
    return data;
  },

  async overrideCommission(agencyId: string, modelId: string | null, overrideData: any) {
    const { data } = await apiClient.post(
      '/financial/commission/override',
      overrideData,
      { params: { agency_id: agencyId, model_id: modelId } }
    );
    return data;
  },

  // Billing Cycles
  async getBillingCycles(params?: {
    agency_id?: string;
    include_open?: boolean;
    include_closed?: boolean;
    limit?: number;
    offset?: number;
  }) {
    const { data } = await apiClient.get('/financial/billing-cycles', { params });
    return data;
  },

  async createBillingCycle(params: {
    agency_id: string;
    cycle_start: string;
    cycle_end: string;
  }) {
    const { data } = await apiClient.post('/financial/billing-cycles', null, { params });
    return data;
  },

  async closeBillingCycle(cycleId: string) {
    const { data } = await apiClient.post(`/financial/billing-cycles/${cycleId}/close`);
    return data;
  },

  // Payouts
  async getPayouts(filters?: PayoutFilters) {
    const { data } = await apiClient.get('/financial/payouts', { 
      params: {
        billing_cycle_id: filters?.billing_cycle_id,
        recipient_id: filters?.user_id || filters?.model_id,
        status: filters?.status,
        limit: filters?.limit,
        offset: filters?.offset }
    });
    return data;
  },

  async getPayout(payoutId: string) {
    // Not available in backend yet
    throw new Error('Get single payout not implemented');
  },

  async createPayout(payoutData: any) {
    const { data: response } = await apiClient.post('/financial/payouts', payoutData);
    return response;
  },

  async processPayout(payoutId: string) {
    const { data } = await apiClient.post(`/financial/payouts/${payoutId}/process`);
    return data;
  },

  // Crypto Wallets
  async getWallets(params?: { network?: string; active_only?: boolean }) {
    const { data } = await apiClient.get('/financial/wallets', { params });
    return data;
  },

  async createWallet(walletData: any) {
    const { data } = await apiClient.post('/financial/wallets', walletData);
    return data;
  },

  async verifyWallet(walletId: string, verification: any) {
    const { data } = await apiClient.post(`/financial/wallets/${walletId}/verify`, verification);
    return data;
  },

  // Invoices
  async getInvoices(filters?: InvoiceFilters) {
    const { data } = await apiClient.get('/financial/invoices', {
      params: {
        agency_id: filters?.agency_id,
        model_id: filters?.model_id,
        status: filters?.status,
        due_date_start: filters?.start_date,
        due_date_end: filters?.end_date,
        page: filters?.page,
        size: filters?.size }
    });
    return data;
  },

  async getInvoice(invoiceId: string) {
    // Not directly available, use getInvoices with filtering
    const invoices = await this.getInvoices();
    return invoices.find((inv: any) => inv.id === invoiceId);
  },

  async createInvoice(invoiceData: Partial<Invoice>) {
    const { data: response } = await apiClient.post('/financial/invoices', invoiceData);
    return response;
  },

  async updateInvoice(invoiceId: string, updateData: Partial<Invoice>) {
    const { data: response } = await apiClient.put(`/financial/invoices/${invoiceId}`, updateData);
    return response;
  },

  async sendInvoice(invoiceId: string) {
    const { data } = await apiClient.post(`/financial/invoices/${invoiceId}/send`);
    return data;
  },

  async downloadInvoice(invoiceId: string) {
    return apiClient.get(`/financial/invoices/${invoiceId}/pdf`, { responseType: 'blob' });
  },

  // Legacy methods that aren't directly available in backend
  async getTransactions(filters?: TransactionFilters): Promise<PaginatedResponse<Transaction>> {
    console.warn('Transaction listing not directly available, use billing cycles');
    return {
      items: [],
      total: 0,
      page: filters?.page || 1,
      size: filters?.size || 20,
      pages: 0 };
  },

  async getTransaction(_transactionId: string): Promise<Transaction> {
    throw new Error('Transaction detail not implemented');
  },

  async cancelPayout(_payoutId: string): Promise<Payout> {
    throw new Error('Payout cancellation not implemented');
  },

  // Payment methods not in backend
  async getPaymentMethods(): Promise<PaymentMethod[]> { // Use wallets as payment methods
    return this.getWallets({ active_only: true                                                                                                                                     });
  },

  async getPaymentMethod(_methodId: string): Promise<PaymentMethod> {
    throw new Error('Payment method detail not implemented');
  },

  async createPaymentMethod(_event: Partial<PaymentMethod>): Promise<PaymentMethod> {
    // Map to wallet creation
    return this.createWallet();
  },

  async updatePaymentMethod(_methodId: string, _updateData: Partial<PaymentMethod>): Promise<PaymentMethod> {
    throw new Error('Payment method update not implemented');
  },

  async deletePaymentMethod(_methodId: string): Promise<void> {
    throw new Error('Payment method deletion not implemented');
  },

  async setDefaultPaymentMethod(_methodId: string): Promise<PaymentMethod> {
    throw new Error('Default payment method not implemented');
  },

  // Revenue - use analytics
  async getRevenue(params: RevenueParams): Promise<Revenue> {
    const { data: analytics } = await apiClient.get(`/orchestration/analytics/${params.model_id}`, {
      params: {
        start_date: params.start_date,
        end_date: params.end_date }
    });
    return analytics.data;
  },

  async getRevenueHistory(_params: any): Promise<Revenue[]> {
    console.warn('Revenue history not directly available');
    return [];
  },

  // Reports
  async getReports(params?: QueryParams): Promise<PaginatedResponse<FinancialReport>> {
    console.warn('Financial reports not directly available');
    return {
      items: [],
      total: 0,
      page: params?.page || 1,
      size: params?.size || 20,
      pages: 0 };
  },

  async generateReport(_event: any): Promise<FinancialReport> {
    throw new Error('Report generation not implemented');
  },

  async downloadReport(_reportId: string, _format: 'pdf' | 'csv' = 'pdf'): Promise<any> {
    throw new Error('Report download not implemented');
  },

  async getFinancialSummary(params?: any): Promise<FinancialSummary> {
    // Combine from various endpoints
    const [billingCycles, payouts, invoices] = await Promise.all([
      this.getBillingCycles({ ...params, limit: 1 }),
      this.getPayouts({ ...params, limit: 10 }),
      this.getInvoices({ ...params, limit: 10 }),
    ]);

    return {
      total_revenue: 0,
      total_payouts: 0,
      pending_payouts: 0,
      available_balance: 0,
      currency: 'USD',
      last_payout: payouts[0],
      next_payout_date: undefined };
  },

  async exportTransactions(_filters: TransactionFilters & { format: 'csv' | 'pdf' }): Promise<any> {
    throw new Error('Transaction export not implemented');
  } };
