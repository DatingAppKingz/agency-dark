import { describe, it, expect, vi, beforeEach } from 'vitest';
import { financialService } from '@/services/financial/financialService';
import { apiClient as api } from '@/services/api';
import { 
  Transaction, 
  TransactionType, 
  TransactionStatus,
  PaymentMethod,
  PayoutRequest,
  PayoutStatus 
} from '@/types/financial';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('FinancialService', () => {
  const mockTransaction: Transaction = {
    id: 'txn-1',
    model_id: 'model-1',
    amount: 100.00,
    currency: 'USD',
    type: TransactionType.SUBSCRIPTION,
    status: TransactionStatus.COMPLETED,
    description: 'Monthly subscription',
    metadata: {},
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockPayout: PayoutRequest = {
    id: 'payout-1',
    model_id: 'model-1',
    amount: 500.00,
    currency: 'USD',
    status: PayoutStatus.PENDING,
    method: 'bank_transfer',
    destination: { account_number: '****1234' },
    requested_at: '2024-01-01T00:00:00Z',
    processed_at: null,
    metadata: {},
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Transaction Management', () => {
    it('should get transactions list', async () => {
      const mockResponse = {
        data: {
          items: [mockTransaction],
          total: 1,
          page: 1,
          size: 20,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getTransactions({
        page: 1,
        size: 20,
        model_id: 'model-1',
      });

      expect(api.get).toHaveBeenCalledWith('/financial/transactions', {
        params: { page: 1, size: 20, model_id: 'model-1' },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should get transaction details', async () => {
      const mockResponse = { data: mockTransaction };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getTransaction('txn-1');

      expect(api.get).toHaveBeenCalledWith('/financial/transactions/txn-1');
      expect(result).toEqual(mockTransaction);
    });

    it('should create a transaction', async () => {
      const newTransaction = {
        model_id: 'model-1',
        amount: 50.00,
        type: TransactionType.TIP,
        description: 'Fan tip',
      };
      const mockResponse = { data: { ...mockTransaction, ...newTransaction } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.createTransaction(newTransaction);

      expect(api.post).toHaveBeenCalledWith('/financial/transactions', newTransaction);
      expect(result).toEqual(mockResponse.data);
    });

    it('should refund a transaction', async () => {
      const mockResponse = { 
        data: { 
          ...mockTransaction, 
          status: TransactionStatus.REFUNDED,
          refunded_amount: 100.00,
        } 
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.refundTransaction('txn-1', 100.00, 'Customer request');

      expect(api.post).toHaveBeenCalledWith('/financial/transactions/txn-1/refund', {
        amount: 100.00,
        reason: 'Customer request',
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Payout Management', () => {
    it('should get payouts list', async () => {
      const mockResponse = {
        data: {
          items: [mockPayout],
          total: 1,
          page: 1,
          size: 20,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getPayouts({
        page: 1,
        size: 20,
        status: PayoutStatus.PENDING,
      });

      expect(api.get).toHaveBeenCalledWith('/financial/payouts', {
        params: { page: 1, size: 20, status: PayoutStatus.PENDING },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should request a payout', async () => {
      const payoutRequest = {
        model_id: 'model-1',
        amount: 500.00,
        method: 'bank_transfer',
      };
      const mockResponse = { data: mockPayout };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.requestPayout(payoutRequest);

      expect(api.post).toHaveBeenCalledWith('/financial/payouts', payoutRequest);
      expect(result).toEqual(mockPayout);
    });

    it('should process a payout', async () => {
      const mockResponse = { 
        data: { 
          ...mockPayout, 
          status: PayoutStatus.PROCESSING,
        } 
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.processPayout('payout-1');

      expect(api.post).toHaveBeenCalledWith('/financial/payouts/payout-1/process');
      expect(result).toEqual(mockResponse.data);
    });

    it('should cancel a payout', async () => {
      const mockResponse = { 
        data: { 
          ...mockPayout, 
          status: PayoutStatus.CANCELLED,
        } 
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.cancelPayout('payout-1', 'Model request');

      expect(api.post).toHaveBeenCalledWith('/financial/payouts/payout-1/cancel', {
        reason: 'Model request',
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Payment Methods', () => {
    it('should get payment methods', async () => {
      const mockMethods: PaymentMethod[] = [
        {
          id: 'pm-1',
          type: 'card',
          last4: '4242',
          brand: 'visa',
          is_default: true,
          created_at: '2024-01-01T00:00:00Z',
        },
      ];
      const mockResponse = { data: mockMethods };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getPaymentMethods('model-1');

      expect(api.get).toHaveBeenCalledWith('/financial/payment-methods', {
        params: { model_id: 'model-1' },
      });
      expect(result).toEqual(mockMethods);
    });

    it('should add a payment method', async () => {
      const newMethod = {
        type: 'bank_account',
        details: {
          account_number: '123456789',
          routing_number: '021000021',
        },
      };
      const mockResponse = { 
        data: {
          id: 'pm-2',
          type: 'bank_account',
          last4: '6789',
          is_default: false,
          created_at: '2024-01-01T00:00:00Z',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.addPaymentMethod('model-1', newMethod);

      expect(api.post).toHaveBeenCalledWith('/financial/payment-methods', {
        model_id: 'model-1',
        ...newMethod,
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should set default payment method', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await financialService.setDefaultPaymentMethod('pm-1');

      expect(api.put).toHaveBeenCalledWith('/financial/payment-methods/pm-1/default');
      expect(result).toEqual(mockResponse.data);
    });

    it('should delete a payment method', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.delete).mockResolvedValue(mockResponse);

      const result = await financialService.deletePaymentMethod('pm-1');

      expect(api.delete).toHaveBeenCalledWith('/financial/payment-methods/pm-1');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Financial Analytics', () => {
    it('should get earnings summary', async () => {
      const mockSummary = {
        total_earnings: 10000,
        current_month: 2000,
        pending_payouts: 500,
        available_balance: 1500,
      };
      const mockResponse = { data: mockSummary };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getEarningsSummary('model-1', {
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      });

      expect(api.get).toHaveBeenCalledWith('/financial/analytics/earnings', {
        params: {
          model_id: 'model-1',
          start_date: '2024-01-01',
          end_date: '2024-01-31',
        },
      });
      expect(result).toEqual(mockSummary);
    });

    it('should get revenue breakdown', async () => {
      const mockBreakdown = {
        subscriptions: 7000,
        tips: 2000,
        ppv_content: 1000,
        total: 10000,
      };
      const mockResponse = { data: mockBreakdown };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getRevenueBreakdown('model-1', {
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      });

      expect(api.get).toHaveBeenCalledWith('/financial/analytics/revenue-breakdown', {
        params: {
          model_id: 'model-1',
          start_date: '2024-01-01',
          end_date: '2024-01-31',
        },
      });
      expect(result).toEqual(mockBreakdown);
    });

    it('should get financial reports', async () => {
      const mockReport = {
        period: '2024-01',
        gross_revenue: 10000,
        commission: 2000,
        net_revenue: 8000,
        transactions: [],
      };
      const mockResponse = { data: mockReport };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getFinancialReport('model-1', '2024-01');

      expect(api.get).toHaveBeenCalledWith('/financial/reports', {
        params: { model_id: 'model-1', period: '2024-01' },
      });
      expect(result).toEqual(mockReport);
    });
  });

  describe('Commission Management', () => {
    it('should calculate commission', async () => {
      const mockResponse = {
        data: {
          gross_amount: 100,
          commission_rate: 20,
          commission_amount: 20,
          net_amount: 80,
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.calculateCommission('model-1', 100);

      expect(api.post).toHaveBeenCalledWith('/financial/commission/calculate', {
        model_id: 'model-1',
        amount: 100,
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should get commission history', async () => {
      const mockHistory = [
        { date: '2024-01-01', rate: 20, reason: 'Initial rate' },
        { date: '2024-02-01', rate: 15, reason: 'Performance bonus' },
      ];
      const mockResponse = { data: mockHistory };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getCommissionHistory('model-1');

      expect(api.get).toHaveBeenCalledWith('/financial/commission/history', {
        params: { model_id: 'model-1' },
      });
      expect(result).toEqual(mockHistory);
    });
  });

  describe('Tax Documentation', () => {
    it('should get tax documents', async () => {
      const mockDocuments = [
        {
          id: 'tax-1',
          type: '1099',
          year: 2023,
          status: 'available',
          url: 'https://example.com/tax/1099-2023.pdf',
        },
      ];
      const mockResponse = { data: mockDocuments };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await financialService.getTaxDocuments('model-1');

      expect(api.get).toHaveBeenCalledWith('/financial/tax-documents', {
        params: { model_id: 'model-1' },
      });
      expect(result).toEqual(mockDocuments);
    });

    it('should submit tax information', async () => {
      const taxInfo = {
        tax_id: '123-45-6789',
        tax_classification: 'individual',
        address: {
          street: '123 Main St',
          city: 'New York',
          state: 'NY',
          zip: '10001',
        },
      };
      const mockResponse = { data: { success: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await financialService.submitTaxInformation('model-1', taxInfo);

      expect(api.post).toHaveBeenCalledWith('/financial/tax-information', {
        model_id: 'model-1',
        ...taxInfo,
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Error Handling', () => {
    it('should handle insufficient funds error', async () => {
      const error = {
        response: {
          status: 400,
          data: {
            error_code: 'INSUFFICIENT_FUNDS',
            message: 'Insufficient funds for payout',
          },
        },
      };
      vi.mocked(api.post).mockRejectedValue(error);

      await expect(
        financialService.requestPayout({
          model_id: 'model-1',
          amount: 10000,
          method: 'bank_transfer',
        })
      ).rejects.toMatchObject(error);
    });

    it('should handle payment processing error', async () => {
      const error = {
        response: {
          status: 500,
          data: {
            error_code: 'PAYMENT_PROCESSING_ERROR',
            message: 'Payment gateway error',
          },
        },
      };
      vi.mocked(api.post).mockRejectedValue(error);

      await expect(
        financialService.createTransaction({
          model_id: 'model-1',
          amount: 100,
          type: TransactionType.SUBSCRIPTION,
        })
      ).rejects.toMatchObject(error);
    });
  });
});