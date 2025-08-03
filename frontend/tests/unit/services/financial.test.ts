import { describe, it, expect, vi, beforeEach } from 'vitest';
import { financialApi } from '@/services/api/financial';
import apiClient from '@/services/api/client';

// Mock dependencies
vi.mock('@/services/api/client');
const mockedApiClient = apiClient as any;

describe('Financial Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Commission Calculations', () => {
    describe('calculateCommission', () => {
      it('should calculate commission correctly', async () => {
        const mockResponse = {
          gross_amount: 1000,
          commission_rate: 0.2,
          commission_amount: 200,
          net_amount: 800
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

        const result = await financialApi.calculateCommission({
          gross_amount: 1000,
          model_id: 'model123',
          calculation_date: '2025-01-31'
        });

        expect(result.commission_amount).toBe(200);
        expect(result.net_amount).toBe(800);
      });
    });

    describe('getCommissionRules', () => {
      it('should fetch commission rules', async () => {
        const mockRules = [
          {
            id: 'rule1',
            agency_id: 'agency123',
            rate: 0.2,
            type: 'subscription'
          }
        ];
        mockedApiClient.get.mockResolvedValueOnce({ data: mockRules });

        const result = await financialApi.getCommissionRules({
          agency_id: 'agency123'
        });

        expect(result).toEqual(mockRules);
      });
    });
  });

  describe('Payout Management', () => {
    describe('createPayout', () => {
      it('should create a payout successfully', async () => {
        const mockPayout = {
          id: 'payout-123',
          amount: 4000,
          status: 'pending'
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockPayout });

        const result = await financialApi.createPayout({
          model_id: 'model123',
          amount: 4000,
          period: '2024-01'
        });

        expect(mockedApiClient.post).toHaveBeenCalledWith(
          '/financial/payouts',
          expect.any(Object)
        );
        expect(result.id).toBe('payout-123');
      });
    });

    describe('processPayout', () => {
      it('should process payout successfully', async () => {
        const mockResult = {
          id: 'payout-123',
          status: 'completed',
          processed_at: '2024-02-01T00:00:00Z'
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockResult });

        const result = await financialApi.processPayout('payout-123');

        expect(mockedApiClient.post).toHaveBeenCalledWith(
          '/financial/payouts/payout-123/process'
        );
        expect(result.status).toBe('completed');
      });
    });
  });

  describe('Billing Cycles', () => {
    describe('getBillingCycles', () => {
      it('should fetch billing cycles', async () => {
        const mockCycles = [
          {
            id: 'cycle1',
            start_date: '2024-01-01',
            end_date: '2024-01-31',
            status: 'closed'
          }
        ];
        mockedApiClient.get.mockResolvedValueOnce({ data: mockCycles });

        const result = await financialApi.getBillingCycles({
          status: 'closed'
        });

        expect(result).toEqual(mockCycles);
      });
    });
  });

  describe('Invoices', () => {
    describe('getInvoices', () => {
      it('should fetch invoices with filters', async () => {
        const mockInvoices = {
          items: [
            {
              id: 'inv1',
              amount: 1000,
              status: 'paid'
            }
          ],
          total: 1
        };
        mockedApiClient.get.mockResolvedValueOnce({ data: mockInvoices });

        const result = await financialApi.getInvoices({
          status: 'paid',
          page: 1,
          limit: 10
        });

        expect(result).toEqual(mockInvoices);
      });
    });
  });

  describe('Wallets', () => {
    describe('getWallets', () => {
      it('should fetch wallets', async () => {
        const mockWallets = [
          {
            id: 'wallet1',
            address: '0x123...',
            network: 'ethereum',
            is_active: true
          }
        ];
        mockedApiClient.get.mockResolvedValueOnce({ data: mockWallets });

        const result = await financialApi.getWallets({
          active_only: true
        });

        expect(result).toEqual(mockWallets);
      });
    });
  });
});