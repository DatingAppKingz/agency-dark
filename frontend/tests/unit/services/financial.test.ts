import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
      it('should calculate standard commission correctly', async () => {
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

      it('should handle platform fees in commission calculation', async () => {
        const mockResponse = {
          data: {
            gross_amount: 1000,
            platform_fee: 100,
            amount_after_fees: 900,
            commission_rate: 0.2,
            commission_amount: 180,
            net_amount: 720
          }
        };
        mockedApiClient.post.mockResolvedValueOnce(mockResponse);

        const result = await financialApi.calculateCommission({
          amount: 1000,
          platformFeeRate: 0.1,
          commissionRate: 0.2,
          type: 'subscription'
        });

        expect(result.platform_fee).toBe(100);
        expect(result.commission_amount).toBe(180);
        expect(result.net_amount).toBe(720);
      });

      it('should handle tips with different commission rates', async () => {
        const mockResponse = {
          data: {
            gross_amount: 50,
            commission_rate: 0.15,
            commission_amount: 7.5,
            net_amount: 42.5
          }
        };
        mockedApiClient.post.mockResolvedValueOnce(mockResponse);

        const result = await financialApi.calculateCommission({
          amount: 50,
          commissionRate: 0.15,
          type: 'tip'
        });

        expect(result.commission_amount).toBe(7.5);
      });

      it('should handle currency conversion in calculations', async () => {
        const mockResponse = {
          data: {
            original_amount: 100,
            original_currency: 'EUR',
            exchange_rate: 1.1,
            usd_amount: 110,
            commission_amount: 22,
            net_amount: 88
          }
        };
        mockedApiClient.post.mockResolvedValueOnce(mockResponse);

        const result = await financialApi.calculateCommission({
          amount: 100,
          currency: 'EUR',
          commissionRate: 0.2,
          type: 'subscription'
        });

        expect(result.usd_amount).toBe(110);
        expect(result.commission_amount).toBe(22);
      });

      it('should validate commission rate boundaries', async () => {
        await expect(
          financialApi.calculateCommission({
            amount: 1000,
            commissionRate: 1.5, // Invalid: > 100%
            type: 'subscription'
          })
        ).rejects.toThrow('Invalid commission rate');

        await expect(
          financialApi.calculateCommission({
            amount: 1000,
            commissionRate: -0.1, // Invalid: negative
            type: 'subscription'
          })
        ).rejects.toThrow('Invalid commission rate');
      });
    });
  });

  describe('Payout Management', () => {
    describe('createPayout', () => {
      it('should create a payout request successfully', async () => {
        const mockPayout = {
          id: 'payout-123',
          model_id: 'model-123',
          period_start: '2024-01-01',
          period_end: '2024-01-31',
          gross_earnings: 5000,
          commission_amount: 1000,
          net_amount: 4000,
          status: 'pending',
          created_at: '2024-02-01T00:00:00Z'
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockPayout });

        const result = await financialApi.createPayout({
          modelId: 'model-123',
          periodStart: '2024-01-01',
          periodEnd: '2024-01-31'
        });

        expect(result.id).toBe('payout-123');
        expect(result.net_amount).toBe(4000);
        expect(result.status).toBe('pending');
        
        expect(mockedApiClient.post).toHaveBeenCalledWith(
          '/financial/payouts',
          expect.objectContaining({
            model_id: 'model-123',
            period_start: '2024-01-01',
            period_end: '2024-01-31'
          })
        );
      });

      it('should handle minimum payout threshold', async () => {
        mockedApiClient.post.mockRejectedValueOnce({
          response: {
            status: 400,
            data: {
              detail: 'Minimum payout amount not met. Required: $100, Available: $50'
            }
          }
        });

        await expect(
          financialApi.createPayout({
            modelId: 'model-123',
            periodStart: '2024-01-01',
            periodEnd: '2024-01-31'
          })
        ).rejects.toThrow('Minimum payout amount not met');
      });

      it('should handle duplicate payout period', async () => {
        mockedApiClient.post.mockRejectedValueOnce({
          response: {
            status: 409,
            data: {
              detail: 'Payout already exists for this period'
            }
          }
        });

        await expect(
          financialApi.createPayout({
            modelId: 'model-123',
            periodStart: '2024-01-01',
            periodEnd: '2024-01-31'
          })
        ).rejects.toThrow('Payout already exists');
      });
    });

    describe('processPayout', () => {
      it('should process approved payout successfully', async () => {
        const mockProcessedPayout = {
          id: 'payout-123',
          status: 'processing',
          processor_reference: 'stripe_123',
          processed_at: '2024-02-02T00:00:00Z'
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockProcessedPayout });

        const result = await financialApi.processPayout('payout-123', {
          method: 'bank_transfer',
          accountDetails: { accountNumber: '****1234' }
        });

        expect(result.status).toBe('processing');
        expect(result.processor_reference).toBe('stripe_123');
      });

      it('should handle insufficient funds error', async () => {
        mockedApiClient.post.mockRejectedValueOnce({
          response: {
            status: 402,
            data: {
              detail: 'Insufficient funds in agency account'
            }
          }
        });

        await expect(
          financialApi.processPayout('payout-123', {
            method: 'bank_transfer'
          })
        ).rejects.toThrow('Insufficient funds');
      });
    });
  });

  describe('Earnings Tracking', () => {
    describe('getEarningsSummary', () => {
      it('should retrieve earnings summary with all metrics', async () => {
        const mockSummary = {
          total_earnings: 10000,
          total_commission: 2000,
          net_earnings: 8000,
          breakdown: {
            subscriptions: 7000,
            tips: 2000,
            ppv: 1000
          },
          currency: 'USD',
          period: {
            start: '2024-01-01',
            end: '2024-01-31'
          }
        };
        mockedApiClient.get.mockResolvedValueOnce({ data: mockSummary });

        const result = await financialApi.getEarningsSummary({
          modelId: 'model-123',
          startDate: '2024-01-01',
          endDate: '2024-01-31'
        });

        expect(result.total_earnings).toBe(10000);
        expect(result.breakdown.subscriptions).toBe(7000);
        expect(result.net_earnings).toBe(8000);
      });

      it('should handle empty earnings period', async () => {
        const mockEmptySummary = {
          total_earnings: 0,
          total_commission: 0,
          net_earnings: 0,
          breakdown: {
            subscriptions: 0,
            tips: 0,
            ppv: 0
          }
        };
        mockedApiClient.get.mockResolvedValueOnce({ data: mockEmptySummary });

        const result = await financialApi.getEarningsSummary({
          modelId: 'model-123',
          startDate: '2024-01-01',
          endDate: '2024-01-31'
        });

        expect(result.total_earnings).toBe(0);
      });
    });

    describe('trackEarning', () => {
      it('should track new earning successfully', async () => {
        const mockEarning = {
          id: 'earning-123',
          model_id: 'model-123',
          type: 'tip',
          amount: 50,
          currency: 'USD',
          platform: 'onlyfans',
          recorded_at: '2024-01-15T10:00:00Z'
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockEarning });

        const result = await financialApi.trackEarning({
          modelId: 'model-123',
          type: 'tip',
          amount: 50,
          currency: 'USD',
          platform: 'onlyfans',
          metadata: {
            fan_id: 'fan-123',
            message: 'Great content!'
          }
        });

        expect(result.id).toBe('earning-123');
        expect(result.amount).toBe(50);
      });

      it('should validate earning amount', async () => {
        await expect(
          financialApi.trackEarning({
            modelId: 'model-123',
            type: 'tip',
            amount: -10, // Invalid: negative
            currency: 'USD'
          })
        ).rejects.toThrow('Invalid earning amount');

        await expect(
          financialApi.trackEarning({
            modelId: 'model-123',
            type: 'tip',
            amount: 0, // Invalid: zero
            currency: 'USD'
          })
        ).rejects.toThrow('Invalid earning amount');
      });
    });
  });

  describe('Financial Reports', () => {
    describe('generateFinancialReport', () => {
      it('should generate comprehensive financial report', async () => {
        const mockReport = {
          report_id: 'report-123',
          period: {
            start: '2024-01-01',
            end: '2024-01-31'
          },
          summary: {
            gross_revenue: 50000,
            total_commission: 10000,
            net_payouts: 40000,
            pending_payouts: 5000
          },
          model_breakdown: [
            {
              model_id: 'model-1',
              earnings: 25000,
              commission: 5000,
              payout: 20000
            }
          ],
          platform_breakdown: {
            onlyfans: 40000,
            fansly: 10000
          }
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockReport });

        const result = await financialApi.generateFinancialReport({
          agencyId: 'agency-123',
          startDate: '2024-01-01',
          endDate: '2024-01-31',
          includeDetails: true
        });

        expect(result.summary.gross_revenue).toBe(50000);
        expect(result.model_breakdown).toHaveLength(1);
        expect(result.platform_breakdown.onlyfans).toBe(40000);
      });

      it('should export report in requested format', async () => {
        const mockExport = {
          download_url: 'https://example.com/reports/report-123.xlsx',
          expires_at: '2024-02-01T12:00:00Z'
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockExport });

        const result = await financialApi.exportFinancialReport({
          reportId: 'report-123',
          format: 'xlsx'
        });

        expect(result.download_url).toContain('.xlsx');
      });
    });
  });

  describe('Currency Operations', () => {
    describe('convertCurrency', () => {
      it('should convert currency with current rates', async () => {
        const mockConversion = {
          from_currency: 'EUR',
          to_currency: 'USD',
          amount: 100,
          rate: 1.1,
          converted_amount: 110,
          rate_date: '2024-01-31'
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockConversion });

        const result = await financialApi.convertCurrency({
          amount: 100,
          from: 'EUR',
          to: 'USD'
        });

        expect(result.converted_amount).toBe(110);
        expect(result.rate).toBe(1.1);
      });

      it('should cache exchange rates for performance', async () => {
        const mockConversion = {
          converted_amount: 110,
          rate: 1.1,
          cached: true
        };
        mockedApiClient.post.mockResolvedValueOnce({ data: mockConversion });

        // First call
        await financialApi.convertCurrency({
          amount: 100,
          from: 'EUR',
          to: 'USD'
        });

        // Second call should use cache
        const result = await financialApi.convertCurrency({
          amount: 200,
          from: 'EUR',
          to: 'USD'
        });

        expect(mockedApiClient.post).toHaveBeenCalledTimes(1);
        expect(result.converted_amount).toBe(220); // 200 * 1.1
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors gracefully', async () => {
      mockedApiClient.get.mockRejectedValueOnce(new Error('Network error'));

      await expect(
        financialApi.getEarningsSummary({
          modelId: 'model-123',
          startDate: '2024-01-01',
          endDate: '2024-01-31'
        })
      ).rejects.toThrow('Network error');
    });

    it('should handle API validation errors', async () => {
      mockedApiClient.post.mockRejectedValueOnce({
        response: {
          status: 422,
          data: {
            detail: [
              {
                loc: ['body', 'amount'],
                msg: 'ensure this value is greater than 0',
                type: 'value_error'
              }
            ]
          }
        }
      });

      await expect(
        financialApi.createPayout({
          modelId: 'model-123',
          periodStart: '2024-01-01',
          periodEnd: '2024-01-31'
        })
      ).rejects.toThrow('Validation error');
    });
  });
});