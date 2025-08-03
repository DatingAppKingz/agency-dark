import { analyticsService } from '@/services/api/analytics';
import { vi } from 'vitest';
import apiClient from '@/services/api/client';
import { logger } from '@/utils/logger';

// Mock the dependencies
vi.mock('@/services/api/client');
vi.mock('@/utils/logger', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

const mockedApiClient = apiClient as vi.Mocked<typeof apiClient>;

describe('Analytics Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getDashboardSummary', () => {
    it('fetches dashboard summary with default period', async () => {
      const mockData = {
        revenue: 1000,
        subscribers: 50,
        messages: 200,
      };
      
      mockedApiClient.get.mockResolvedValueOnce({ data: mockData });

      const result = await analyticsService.getDashboardSummary('model-1');

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        '/analytics/dashboard/model-1',
        { params: { period: 'today' } }
      );
      expect(result).toEqual(mockData);
    });

    it('fetches dashboard summary with custom period', async () => {
      const mockData = { revenue: 5000 };
      mockedApiClient.get.mockResolvedValueOnce({ data: mockData });

      const result = await analyticsService.getDashboardSummary('model-2', 'month');

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        '/analytics/dashboard/model-2',
        { params: { period: 'month' } }
      );
      expect(result).toEqual(mockData);
    });

    it('handles API errors', async () => {
      const error = new Error('Network error');
      mockedApiClient.get.mockRejectedValueOnce(error);

      await expect(analyticsService.getDashboardSummary('model-1')).rejects.toThrow('Network error');
    });
  });

  describe('getSubscriberGrowthChart', () => {
    it('fetches subscriber growth data', async () => {
      const mockChartData = {
        labels: ['2024-01-01', '2024-01-02'],
        datasets: [{ data: [10, 15] }],
      };
      
      mockedApiClient.post.mockResolvedValueOnce({ data: mockChartData });

      const result = await analyticsService.getSubscriberGrowthChart(
        'model-1',
        '2024-01-01',
        '2024-01-02'
      );

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/charts/subscriber-growth',
        null,
        {
          params: {
            model_id: 'model-1',
            period_start: '2024-01-01',
            period_end: '2024-01-02',
            granularity: 'day',
          },
        }
      );
      expect(result).toEqual(mockChartData);
    });

    it('supports different granularity options', async () => {
      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await analyticsService.getSubscriberGrowthChart(
        'model-1',
        '2024-01-01',
        '2024-01-02',
        'hour'
      );

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/charts/subscriber-growth',
        null,
        expect.objectContaining({
          params: expect.objectContaining({
            granularity: 'hour',
          }),
        })
      );
    });
  });

  describe('getRevenueTimelineChart', () => {
    it('fetches revenue timeline data', async () => {
      const mockData = {
        timeline: [
          { date: '2024-01-01', revenue: 100 },
          { date: '2024-01-02', revenue: 150 },
        ],
      };
      
      mockedApiClient.post.mockResolvedValueOnce({ data: mockData });

      const result = await analyticsService.getRevenueTimelineChart(
        'model-1',
        '2024-01-01',
        '2024-01-02',
        'week'
      );

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/charts/revenue-timeline',
        null,
        {
          params: {
            model_id: 'model-1',
            period_start: '2024-01-01',
            period_end: '2024-01-02',
            granularity: 'week',
          },
        }
      );
      expect(result).toEqual(mockData);
    });
  });

  describe('getFanRevenueChart', () => {
    it('fetches fan revenue data', async () => {
      const fanIds = ['fan-1', 'fan-2'];
      const mockData = {
        fans: [
          { id: 'fan-1', revenue: 500 },
          { id: 'fan-2', revenue: 300 },
        ],
      };
      
      mockedApiClient.post.mockResolvedValueOnce({ data: mockData });

      const result = await analyticsService.getFanRevenueChart(
        'model-1',
        fanIds,
        '2024-01-01',
        '2024-01-31'
      );

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/charts/fan-revenue',
        {
          entity_ids: fanIds,
          period_start: '2024-01-01',
          period_end: '2024-01-31',
          granularity: 'day',
          chart_type: 'fan_revenue',
        },
        { params: { model_id: 'model-1' } }
      );
      expect(result).toEqual(mockData);
    });
  });

  describe('getCategoryPopularity', () => {
    it('fetches category popularity data', async () => {
      const mockData = {
        categories: [
          { name: 'Photos', count: 100 },
          { name: 'Videos', count: 50 },
        ],
      };
      
      mockedApiClient.get.mockResolvedValueOnce({ data: mockData });

      const result = await analyticsService.getCategoryPopularity(
        'model-1',
        '2024-01-01',
        '2024-01-31'
      );

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        '/analytics/categories/model-1',
        {
          params: {
            period_start: '2024-01-01',
            period_end: '2024-01-31',
          },
        }
      );
      expect(result).toEqual(mockData);
    });
  });

  describe('getContentPerformance', () => {
    it('fetches content performance data', async () => {
      const contentIds = ['content-1', 'content-2'];
      const mockData = {
        content: [
          { id: 'content-1', views: 1000, revenue: 50 },
          { id: 'content-2', views: 500, revenue: 25 },
        ],
      };
      
      mockedApiClient.post.mockResolvedValueOnce({ data: mockData });

      const result = await analyticsService.getContentPerformance('model-1', contentIds);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/content/performance',
        null,
        {
          params: {
            model_id: 'model-1',
            content_ids: contentIds,
          },
        }
      );
      expect(result).toEqual(mockData);
    });
  });

  describe('exportAnalytics', () => {
    it('exports analytics data as CSV', async () => {
      const mockResponse = { export_id: 'export-123' };
      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await analyticsService.exportAnalytics(
        'model-1',
        'revenue',
        '2024-01-01',
        '2024-01-31'
      );

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/export',
        {
          export_type: 'revenue',
          period_start: '2024-01-01',
          period_end: '2024-01-31',
          format: 'csv',
        },
        { params: { model_id: 'model-1' } }
      );
      expect(result).toEqual(mockResponse);
    });

    it('exports analytics data as JSON', async () => {
      const mockResponse = { export_id: 'export-456' };
      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await analyticsService.exportAnalytics(
        'model-1',
        'subscribers',
        '2024-01-01',
        '2024-01-31',
        'json'
      );

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/export',
        expect.objectContaining({
          format: 'json',
        }),
        expect.any(Object)
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe('downloadExport', () => {
    it('downloads exported file', async () => {
      const mockBlob = new Blob(['data'], { type: 'text/csv' });
      mockedApiClient.get.mockResolvedValueOnce({ data: mockBlob });

      const result = await analyticsService.downloadExport('export-123');

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        '/analytics/exports/export-123/download',
        { responseType: 'blob' }
      );
      expect(result).toEqual(mockBlob);
    });
  });

  describe('getGenericChart', () => {
    it('fetches generic chart data', async () => {
      const mockData = { chart: 'data' };
      const options = { metric: 'engagement' };
      
      mockedApiClient.post.mockResolvedValueOnce({ data: mockData });

      const result = await analyticsService.getGenericChart(
        'model-1',
        'engagement_rate',
        '2024-01-01',
        '2024-01-31',
        options
      );

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/analytics/charts/generic',
        {
          chart_type: 'engagement_rate',
          period_start: '2024-01-01',
          period_end: '2024-01-31',
          metric: 'engagement',
        },
        { params: { model_id: 'model-1' } }
      );
      expect(result).toEqual(mockData);
    });
  });

  describe('Legacy Methods', () => {
    describe('getDashboardStats', () => {
      it('fetches dashboard stats successfully', async () => {
        const mockStats = {
          total_users: 100,
          active_models: 10,
          total_revenue: 5000,
          total_messages: 1000,
          new_users_today: 5,
          revenue_today: 250,
          messages_today: 50,
          active_chats: 15,
        };
        
        mockedApiClient.get.mockResolvedValueOnce({ data: mockStats });

        const result = await analyticsService.getDashboardStats();

        expect(logger.info).toHaveBeenCalledWith('📊 Fetching dashboard stats...');
        expect(mockedApiClient.get).toHaveBeenCalledWith('/analytics/agency/dashboard-stats');
        expect(logger.info).toHaveBeenCalledWith('✅ Dashboard stats received:', mockStats);
        expect(result).toEqual(mockStats);
      });

      it('returns default values on error', async () => {
        const error = new Error('API Error');
        mockedApiClient.get.mockRejectedValueOnce(error);

        const result = await analyticsService.getDashboardStats();

        expect(logger.error).toHaveBeenCalledWith('❌ Failed to fetch dashboard stats:', error);
        expect(result).toEqual({
          total_users: 0,
          active_models: 0,
          total_revenue: 0,
          total_messages: 0,
          new_users_today: 0,
          revenue_today: 0,
          messages_today: 0,
          active_chats: 0,
        });
      });
    });

    describe('getAgencyStats', () => {
      it('returns empty array with warning', async () => {
        const result = await analyticsService.getAgencyStats();

        expect(logger.warn).toHaveBeenCalledWith('Agency stats not directly available in analytics API');
        expect(result).toEqual([]);
      });
    });

    describe('getModelPerformance', () => {
      it('fetches model performance data', async () => {
        const mockPerformance = [
          {
            model_id: 'model-1',
            model_name: 'Model 1',
            revenue: 1000,
            messages: 500,
            fans: 50,
            conversion_rate: 0.15,
          },
        ];
        
        mockedApiClient.get.mockResolvedValueOnce({ data: mockPerformance });

        const result = await analyticsService.getModelPerformance('week');

        expect(logger.info).toHaveBeenCalledWith('📊 Fetching model performance...');
        expect(mockedApiClient.get).toHaveBeenCalledWith(
          '/analytics/agency/model-performance',
          { params: { period: 'week' } }
        );
        expect(logger.info).toHaveBeenCalledWith('✅ Model performance received:', mockPerformance);
        expect(result).toEqual(mockPerformance);
      });

      it('returns empty array on error', async () => {
        const error = new Error('Network error');
        mockedApiClient.get.mockRejectedValueOnce(error);

        const result = await analyticsService.getModelPerformance();

        expect(logger.error).toHaveBeenCalledWith('❌ Failed to fetch model performance:', error);
        expect(result).toEqual([]);
      });
    });

    describe('getRevenueChart', () => {
      it('fetches and transforms revenue chart data', async () => {
        const mockData = {
          data: [
            { date: '2024-01-01', revenue: 100, tips: 20 },
            { date: '2024-01-02', revenue: 150, tips: 30 },
          ],
        };
        
        mockedApiClient.get.mockResolvedValueOnce({ data: mockData });

        const result = await analyticsService.getRevenueChart('day');

        expect(mockedApiClient.get).toHaveBeenCalledWith(
          '/analytics/agency/revenue-chart',
          { params: { period: 'day' } }
        );
        
        expect(result).toEqual({
          labels: ['2024-01-01', '2024-01-02'],
          datasets: [
            {
              label: 'Total Revenue',
              data: [100, 150],
              borderColor: 'rgb(75, 192, 192)',
              backgroundColor: 'rgba(75, 192, 192, 0.1)',
            },
            {
              label: 'Tips',
              data: [20, 30],
              borderColor: 'rgb(255, 99, 132)',
              backgroundColor: 'rgba(255, 99, 132, 0.1)',
            },
          ],
        });
      });

      it('returns empty chart data on error', async () => {
        const error = new Error('Chart error');
        mockedApiClient.get.mockRejectedValueOnce(error);

        const result = await analyticsService.getRevenueChart();

        expect(logger.error).toHaveBeenCalledWith('Failed to fetch revenue chart:', error);
        expect(result).toEqual({
          labels: [],
          datasets: [],
        });
      });
    });

    describe('getMessageChart', () => {
      it('returns empty data with warning', async () => {
        const result = await analyticsService.getMessageChart('week');

        expect(logger.warn).toHaveBeenCalledWith('Message chart not directly available in analytics API');
        expect(result).toEqual({ labels: [], datasets: [] });
      });
    });
  });
});