import api from './api';
import { 
  Transaction, 
  Earning, 
  Payout, 
  PaymentMethod, 
  Invoice,
  FinancialSummary 
} from '@/types/financial';

// Transactions
export const transactionService = {
  async getTransactions(params?: {
    modelId?: number;
    type?: string;
    status?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
    offset?: number;
  }) {
    const response = await api.get<Transaction[]>('/transactions', { params });
    return response.data;
  },

  async getTransaction(id: number) {
    const response = await api.get<Transaction>(`/transactions/${id}`);
    return response.data;
  },

  async createTransaction(data: Partial<Transaction>) {
    const response = await api.post<Transaction>('/transactions', data);
    return response.data;
  },
};

// Earnings
export const earningService = {
  async getEarnings(params?: {
    modelId?: number;
    isPaid?: boolean;
    periodYear?: number;
    periodMonth?: number;
    limit?: number;
    offset?: number;
  }) {
    const response = await api.get<Earning[]>('/earnings', { params });
    return response.data;
  },

  async getEarningSummary(modelId: number, year?: number, month?: number) {
    const response = await api.get<any>(`/earnings/summary`, {
      params: { modelId, year, month }
    });
    return response.data;
  },
};

// Payouts
export const payoutService = {
  async getPayouts(params?: {
    status?: string;
    modelId?: number;
    startDate?: string;
    endDate?: string;
    limit?: number;
    offset?: number;
  }) {
    const response = await api.get<Payout[]>('/payouts', { params });
    return response.data;
  },

  async getPayout(id: number) {
    const response = await api.get<Payout>(`/payouts/${id}`);
    return response.data;
  },

  async createPayout(data: {
    model_id: number;
    period_start: string;
    period_end: string;
    payment_method_id: number;
    adjustments?: number;
    notes?: string;
    scheduled_date?: string;
  }) {
    const response = await api.post<Payout>('/payouts', data);
    return response.data;
  },

  async updatePayout(id: number, data: Partial<Payout>) {
    const response = await api.patch<Payout>(`/payouts/${id}`, data);
    return response.data;
  },

  async approvePayout(id: number, approved: boolean, notes?: string) {
    const response = await api.post<any>(`/payouts/${id}/approve`, {
      approved,
      notes
    });
    return response.data;
  },

  async bulkPayoutAction(payoutIds: number[], action: 'approve' | 'process' | 'cancel', notes?: string) {
    const response = await api.post<any>('/payouts/bulk-action', {
      payout_ids: payoutIds,
      action,
      notes
    });
    return response.data;
  },

  async getPayoutEarnings(payoutId: number) {
    const response = await api.get<any[]>(`/payouts/${payoutId}/earnings`);
    return response.data;
  },
};

// Payment Methods
export const paymentMethodService = {
  async getPaymentMethods(modelId?: number, agencyId?: number) {
    const params: any = {};
    if (modelId) params.model_id = modelId;
    if (agencyId) params.agency_id = agencyId;
    
    const response = await api.get<PaymentMethod[]>('/payment-methods', { params });
    return response.data;
  },

  async getPaymentMethod(id: number) {
    const response = await api.get<PaymentMethod>(`/payment-methods/${id}`);
    return response.data;
  },

  async createPaymentMethod(data: Partial<PaymentMethod>) {
    const response = await api.post<PaymentMethod>('/payment-methods', data);
    return response.data;
  },

  async updatePaymentMethod(id: number, data: Partial<PaymentMethod>) {
    const response = await api.patch<PaymentMethod>(`/payment-methods/${id}`, data);
    return response.data;
  },

  async deletePaymentMethod(id: number) {
    const response = await api.delete(`/payment-methods/${id}`);
    return response.data;
  },

  async setPrimaryPaymentMethod(id: number) {
    const response = await api.post<PaymentMethod>(`/payment-methods/${id}/set-primary`);
    return response.data;
  },

  async verifyPaymentMethod(id: number, verified: boolean, notes?: string) {
    const response = await api.post<PaymentMethod>(`/payment-methods/${id}/verify`, {
      verified,
      notes
    });
    return response.data;
  },
};

// Invoices
export const invoiceService = {
  async getInvoices(params?: {
    agencyId?: number;
    status?: string;
    startDate?: string;
    endDate?: string;
    limit?: number;
    offset?: number;
  }) {
    const response = await api.get<Invoice[]>('/invoices', { params });
    return response.data;
  },

  async getInvoice(id: number) {
    const response = await api.get<Invoice>(`/invoices/${id}`);
    return response.data;
  },

  async createInvoice(data: Partial<Invoice>) {
    const response = await api.post<Invoice>('/invoices', data);
    return response.data;
  },

  async updateInvoice(id: number, data: Partial<Invoice>) {
    const response = await api.patch<Invoice>(`/invoices/${id}`, data);
    return response.data;
  },

  async sendInvoice(id: number) {
    const response = await api.post<any>(`/invoices/${id}/send`);
    return response.data;
  },

  async markInvoiceAsPaid(id: number, paymentMethod: string, paidDate: string) {
    const response = await api.post<Invoice>(`/invoices/${id}/mark-paid`, {
      payment_method: paymentMethod,
      paid_date: paidDate
    });
    return response.data;
  },

  async downloadInvoice(id: number) {
    const response = await api.get(`/invoices/${id}/download`, {
      responseType: 'blob'
    });
    return response.data;
  },
};

// Financial Summary
export const financialService = {
  async getFinancialSummary(modelId?: number, agencyId?: number) {
    const params: any = {};
    if (modelId) params.model_id = modelId;
    if (agencyId) params.agency_id = agencyId;
    
    const response = await api.get<FinancialSummary>('/financial/summary', { params });
    return response.data;
  },

  async getRevenueReport(params: {
    modelId?: number;
    agencyId?: number;
    startDate: string;
    endDate: string;
    groupBy?: 'day' | 'week' | 'month';
  }) {
    const response = await api.get<any>('/financial/revenue-report', { params });
    return response.data;
  },

  async getCommissionReport(params: {
    agencyId: number;
    startDate: string;
    endDate: string;
  }) {
    const response = await api.get<any>('/financial/commission-report', { params });
    return response.data;
  },

  async exportTransactions(params: {
    modelId?: number;
    agencyId?: number;
    startDate: string;
    endDate: string;
    format?: 'csv' | 'xlsx' | 'pdf';
  }) {
    const response = await api.get('/financial/export', {
      params,
      responseType: 'blob'
    });
    return response.data;
  },
};