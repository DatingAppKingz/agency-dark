import { apiClient } from './client';
import type { PaginatedResponse, QueryParams } from '@/types/api';
import type {
  Transaction,
  Payout,
  PaymentMethod,
  Revenue,
  Commission,
  Invoice,
  FinancialReport,
  FinancialSummary,
} from '@/types/financial';

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
  // Transactions
  getTransactions: (filters?: TransactionFilters) =>
    apiClient.get<PaginatedResponse<Transaction>>('/financial/transactions', { params: filters }),

  getTransaction: (id: string) =>
    apiClient.get<Transaction>(`/financial/transactions/${id}`),

  // Payouts
  getPayouts: (filters?: PayoutFilters) =>
    apiClient.get<PaginatedResponse<Payout>>('/financial/payouts', { params: filters }),

  getPayout: (id: string) =>
    apiClient.get<Payout>(`/financial/payouts/${id}`),

  requestPayout: (data: {
    amount: number;
    payment_method_id: string;
    model_id?: string;
  }) =>
    apiClient.post<Payout>('/financial/payouts', data),

  cancelPayout: (id: string) =>
    apiClient.post<Payout>(`/financial/payouts/${id}/cancel`),

  // Payment Methods
  getPaymentMethods: () =>
    apiClient.get<PaymentMethod[]>('/financial/payment-methods'),

  getPaymentMethod: (id: string) =>
    apiClient.get<PaymentMethod>(`/financial/payment-methods/${id}`),

  createPaymentMethod: (data: Partial<PaymentMethod>) =>
    apiClient.post<PaymentMethod>('/financial/payment-methods', data),

  updatePaymentMethod: (id: string, data: Partial<PaymentMethod>) =>
    apiClient.put<PaymentMethod>(`/financial/payment-methods/${id}`, data),

  deletePaymentMethod: (id: string) =>
    apiClient.delete(`/financial/payment-methods/${id}`),

  setDefaultPaymentMethod: (id: string) =>
    apiClient.post<PaymentMethod>(`/financial/payment-methods/${id}/set-default`),

  // Revenue
  getRevenue: (params: RevenueParams) =>
    apiClient.get<Revenue>('/financial/revenue', { params }),

  getRevenueHistory: (params: {
    period: Revenue['period'];
    count: number;
    model_id?: string;
    agency_id?: string;
  }) =>
    apiClient.get<Revenue[]>('/financial/revenue/history', { params }),

  // Commission
  getCommissionRates: (params?: { model_id?: string; agency_id?: string }) =>
    apiClient.get<Commission[]>('/financial/commission', { params }),

  calculateCommission: (data: {
    amount: number;
    model_id?: string;
    agency_id?: string;
    date?: string;
  }) =>
    apiClient.post<{ commission: number; rate: number }>('/financial/commission/calculate', data),

  // Invoices
  getInvoices: (filters?: InvoiceFilters) =>
    apiClient.get<PaginatedResponse<Invoice>>('/financial/invoices', { params: filters }),

  getInvoice: (id: string) =>
    apiClient.get<Invoice>(`/financial/invoices/${id}`),

  createInvoice: (data: Partial<Invoice>) =>
    apiClient.post<Invoice>('/financial/invoices', data),

  updateInvoice: (id: string, data: Partial<Invoice>) =>
    apiClient.put<Invoice>(`/financial/invoices/${id}`, data),

  sendInvoice: (id: string) =>
    apiClient.post<Invoice>(`/financial/invoices/${id}/send`),

  markInvoiceAsPaid: (id: string) =>
    apiClient.post<Invoice>(`/financial/invoices/${id}/mark-paid`),

  downloadInvoice: (id: string) =>
    apiClient.get(`/financial/invoices/${id}/download`, { responseType: 'blob' }),

  // Reports
  getReports: (filters?: QueryParams) =>
    apiClient.get<PaginatedResponse<FinancialReport>>('/financial/reports', { params: filters }),

  generateReport: (data: {
    type: FinancialReport['type'];
    period_start: string;
    period_end: string;
    model_id?: string;
    agency_id?: string;
  }) =>
    apiClient.post<FinancialReport>('/financial/reports/generate', data),

  downloadReport: (id: string, format: 'pdf' | 'csv' = 'pdf') =>
    apiClient.get(`/financial/reports/${id}/download`, { 
      params: { format },
      responseType: 'blob' 
    }),

  // Summary
  getFinancialSummary: (params?: { model_id?: string; agency_id?: string }) =>
    apiClient.get<FinancialSummary>('/financial/summary', { params }),

  // Export
  exportTransactions: (filters: TransactionFilters & { format: 'csv' | 'pdf' }) =>
    apiClient.get('/financial/transactions/export', {
      params: filters,
      responseType: 'blob'
    }),
};