import { apiClient as api } from '@/services/api';
import {
  Transaction,
  TransactionType,
  TransactionStatus,
  PaymentMethod,
  PayoutRequest,
  PayoutStatus,
  CreateTransactionData,
  CreatePayoutData,
  TaxInformation,
  FinancialReport,
} from '@/types/financial';

interface GetTransactionsParams {
  page?: number;
  size?: number;
  model_id?: string;
  type?: TransactionType;
  status?: TransactionStatus;
  start_date?: string;
  end_date?: string;
}

interface TransactionResponse {
  items: Transaction[];
  total: number;
  page: number;
  size: number;
}

interface GetPayoutsParams {
  page?: number;
  size?: number;
  model_id?: string;
  status?: PayoutStatus;
  start_date?: string;
  end_date?: string;
}

interface PayoutResponse {
  items: PayoutRequest[];
  total: number;
  page: number;
  size: number;
}

interface DateRangeParams {
  start_date: string;
  end_date: string;
}

interface EarningsSummary {
  total_earnings: number;
  current_month: number;
  pending_payouts: number;
  available_balance: number;
}

interface RevenueBreakdown {
  subscriptions: number;
  tips: number;
  ppv_content: number;
  messages?: number;
  total: number;
}

interface CommissionCalculation {
  gross_amount: number;
  commission_rate: number;
  commission_amount: number;
  net_amount: number;
}

interface CommissionHistory {
  date: string;
  rate: number;
  reason: string;
}

interface TaxDocument {
  id: string;
  type: string;
  year: number;
  status: string;
  url?: string;
  created_at?: string;
}

class FinancialService {
  // Transaction Management
  async getTransactions(params: GetTransactionsParams = {}): Promise<TransactionResponse> {
    const response = await api.get<TransactionResponse>('/financial/transactions', {
      params,
    });
    return response.data;
  }

  async getTransaction(transactionId: string): Promise<Transaction> {
    const response = await api.get<Transaction>(`/financial/transactions/${transactionId}`);
    return response.data;
  }

  async createTransaction(data: CreateTransactionData): Promise<Transaction> {
    const response = await api.post<Transaction>('/financial/transactions', data);
    return response.data;
  }

  async refundTransaction(
    transactionId: string,
    amount: number,
    reason: string
  ): Promise<Transaction> {
    const response = await api.post<Transaction>(
      `/financial/transactions/${transactionId}/refund`,
      { amount, reason }
    );
    return response.data;
  }

  // Payout Management
  async getPayouts(params: GetPayoutsParams = {}): Promise<PayoutResponse> {
    const response = await api.get<PayoutResponse>('/financial/payouts', {
      params,
    });
    return response.data;
  }

  async requestPayout(data: CreatePayoutData): Promise<PayoutRequest> {
    const response = await api.post<PayoutRequest>('/financial/payouts', data);
    return response.data;
  }

  async processPayout(payoutId: string): Promise<PayoutRequest> {
    const response = await api.post<PayoutRequest>(`/financial/payouts/${payoutId}/process`);
    return response.data;
  }

  async cancelPayout(payoutId: string, reason: string): Promise<PayoutRequest> {
    const response = await api.post<PayoutRequest>(`/financial/payouts/${payoutId}/cancel`, {
      reason,
    });
    return response.data;
  }

  // Payment Methods
  async getPaymentMethods(modelId: string): Promise<PaymentMethod[]> {
    const response = await api.get<PaymentMethod[]>('/financial/payment-methods', {
      params: { model_id: modelId },
    });
    return response.data;
  }

  async addPaymentMethod(
    modelId: string,
    method: { type: string; details: Record<string, any> }
  ): Promise<PaymentMethod> {
    const response = await api.post<PaymentMethod>('/financial/payment-methods', {
      model_id: modelId,
      ...method,
    });
    return response.data;
  }

  async setDefaultPaymentMethod(paymentMethodId: string): Promise<{ success: boolean }> {
    const response = await api.put<{ success: boolean }>(
      `/financial/payment-methods/${paymentMethodId}/default`
    );
    return response.data;
  }

  async deletePaymentMethod(paymentMethodId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(
      `/financial/payment-methods/${paymentMethodId}`
    );
    return response.data;
  }

  // Financial Analytics
  async getEarningsSummary(
    modelId: string,
    params: DateRangeParams
  ): Promise<EarningsSummary> {
    const response = await api.get<EarningsSummary>('/financial/analytics/earnings', {
      params: {
        model_id: modelId,
        ...params,
      },
    });
    return response.data;
  }

  async getRevenueBreakdown(
    modelId: string,
    params: DateRangeParams
  ): Promise<RevenueBreakdown> {
    const response = await api.get<RevenueBreakdown>('/financial/analytics/revenue-breakdown', {
      params: {
        model_id: modelId,
        ...params,
      },
    });
    return response.data;
  }

  async getFinancialReport(modelId: string, period: string): Promise<FinancialReport> {
    const response = await api.get<FinancialReport>('/financial/reports', {
      params: { model_id: modelId, period },
    });
    return response.data;
  }

  // Commission Management
  async calculateCommission(modelId: string, amount: number): Promise<CommissionCalculation> {
    const response = await api.post<CommissionCalculation>('/financial/commission/calculate', {
      model_id: modelId,
      amount,
    });
    return response.data;
  }

  async getCommissionHistory(modelId: string): Promise<CommissionHistory[]> {
    const response = await api.get<CommissionHistory[]>('/financial/commission/history', {
      params: { model_id: modelId },
    });
    return response.data;
  }

  // Tax Documentation
  async getTaxDocuments(modelId: string): Promise<TaxDocument[]> {
    const response = await api.get<TaxDocument[]>('/financial/tax-documents', {
      params: { model_id: modelId },
    });
    return response.data;
  }

  async submitTaxInformation(
    modelId: string,
    taxInfo: TaxInformation
  ): Promise<{ success: boolean }> {
    const response = await api.post<{ success: boolean }>('/financial/tax-information', {
      model_id: modelId,
      ...taxInfo,
    });
    return response.data;
  }

  // Utility Methods
  async exportTransactions(
    modelId: string,
    format: 'csv' | 'pdf',
    params: DateRangeParams
  ): Promise<Blob> {
    const response = await api.get<Blob>('/financial/transactions/export', {
      params: {
        model_id: modelId,
        format,
        ...params,
      },
      responseType: 'blob',
    });
    return response.data;
  }

  async getPaymentGateways(): Promise<any[]> {
    const response = await api.get<any[]>('/financial/payment-gateways');
    return response.data;
  }

  async validateBankAccount(accountNumber: string, routingNumber: string): Promise<{
    valid: boolean;
    bank_name?: string;
  }> {
    const response = await api.post<{ valid: boolean; bank_name?: string }>(
      '/financial/validate-bank-account',
      {
        account_number: accountNumber,
        routing_number: routingNumber,
      }
    );
    return response.data;
  }

  async getExchangeRates(fromCurrency: string, toCurrency: string): Promise<{
    rate: number;
    timestamp: string;
  }> {
    const response = await api.get<{ rate: number; timestamp: string }>(
      '/financial/exchange-rates',
      {
        params: {
          from: fromCurrency,
          to: toCurrency,
        },
      }
    );
    return response.data;
  }
}

export const financialService = new FinancialService();