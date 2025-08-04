import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { syncService } from '@/services/api/sync';
import apiClient from '@/services/api/client';
import {
  SyncRequest,
  SyncPlatform,
  SyncScheduleRequest
} from '@/types/sync';

// Mock dependencies
vi.mock('@/services/api/client');
const mockedApiClient = apiClient as any;

describe('Sync Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('syncNow', () => {
    it('should trigger immediate sync', async () => {
      const request: SyncRequest = {
        model_id: 'model123',
        platforms: [SyncPlatform.ONLYFANS, SyncPlatform.INFLOW],
        force: true
      };

      const mockResponse = {
        job_id: 'job123',
        status: 'started',
        platforms: request.platforms,
        started_at: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await syncService.syncNow(request);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/sync/sync-now', request);
      expect(result).toEqual(mockResponse);
    });

    it('should handle sync errors', async () => {
      const request: SyncRequest = {
        model_id: 'model123',
        platforms: [SyncPlatform.ALL]
      };

      const error = new Error('Sync failed');
      mockedApiClient.post.mockRejectedValueOnce(error);

      await expect(syncService.syncNow(request)).rejects.toThrow('Sync failed');
    });
  });

  describe('getStatus', () => {
    it('should fetch sync status for a model', async () => {
      const modelId = 'model123';
      const mockStatus = {
        model_id: modelId,
        last_sync: {
          onlyfans: {
            status: 'completed',
            last_sync_at: '2025-01-31T10:00:00Z',
            records_synced: 150
          },
          inflow: {
            status: 'in_progress',
            last_sync_at: '2025-01-31T10:30:00Z',
            progress: 0.65
          }
        },
        next_scheduled_sync: '2025-01-31T16:00:00Z'
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockStatus });

      const result = await syncService.getStatus(modelId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(`/api/v1/sync/status/${modelId}`);
      expect(result).toEqual(mockStatus);
    });
  });

  describe('getHistory', () => {
    it('should fetch sync history with default limit', async () => {
      const modelId = 'model123';
      const mockHistory = [
        {
          id: 'history1',
          model_id: modelId,
          platform: SyncPlatform.ONLYFANS,
          status: 'completed',
          started_at: '2025-01-31T10:00:00Z',
          completed_at: '2025-01-31T10:15:00Z',
          records_synced: 100
        },
        {
          id: 'history2',
          model_id: modelId,
          platform: SyncPlatform.INFLOW,
          status: 'failed',
          started_at: '2025-01-31T09:00:00Z',
          error: 'Connection timeout'
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockHistory });

      const result = await syncService.getHistory(modelId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(`/api/v1/sync/history/${modelId}?limit=10`);
      expect(result).toEqual(mockHistory);
    });

    it('should fetch sync history with custom limit', async () => {
      const modelId = 'model123';
      const limit = 25;

      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await syncService.getHistory(modelId, limit);

      expect(mockedApiClient.get).toHaveBeenCalledWith(`/api/v1/sync/history/${modelId}?limit=${limit}`);
    });
  });

  describe('scheduleSync', () => {
    it('should schedule a sync', async () => {
      const request: SyncScheduleRequest = {
        model_id: 'model123',
        platforms: [SyncPlatform.ALL],
        schedule_type: 'recurring',
        cron_expression: '0 */6 * * *',
        timezone: 'America/New_York'
      };

      const mockResponse = {
        job_id: 'schedule123',
        model_id: request.model_id,
        schedule_type: request.schedule_type,
        next_run: '2025-01-31T18:00:00Z',
        status: 'scheduled'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await syncService.scheduleSync(request);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/sync/schedule', request);
      expect(result).toEqual(mockResponse);
    });

    it('should schedule one-time sync', async () => {
      const request: SyncScheduleRequest = {
        model_id: 'model123',
        platforms: [SyncPlatform.ONLYFANS],
        schedule_type: 'once',
        scheduled_at: '2025-02-01T10:00:00Z'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await syncService.scheduleSync(request);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/sync/schedule', request);
    });
  });

  describe('cancelScheduledSync', () => {
    it('should cancel a scheduled sync', async () => {
      const jobId = 'job123';
      mockedApiClient.delete.mockResolvedValueOnce({});

      await syncService.cancelScheduledSync(jobId);

      expect(mockedApiClient.delete).toHaveBeenCalledWith(`/api/v1/sync/schedule/${jobId}`);
    });
  });

  describe('getStats', () => {
    it('should fetch sync statistics without agency filter', async () => {
      const mockStats = {
        total_syncs: 1500,
        successful_syncs: 1400,
        failed_syncs: 100,
        average_sync_duration: 300,
        syncs_by_platform: {
          onlyfans: 800,
          inflow: 700
        },
        syncs_by_hour: Array(24).fill(0).map((_, i) => ({ hour: i, count: Math.floor(Math.random() * 100) }))
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockStats });

      const result = await syncService.getStats();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/sync/stats');
      expect(result).toEqual(mockStats);
    });

    it('should fetch sync statistics with agency filter', async () => {
      const agencyId = 'agency123';
      mockedApiClient.get.mockResolvedValueOnce({ data: {} });

      await syncService.getStats(agencyId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(`/api/v1/sync/stats?agency_id=${agencyId}`);
    });
  });

  describe('syncAll', () => {
    it('should sync all models for all platforms by default', async () => {
      const mockResponse = {
        job_ids: ['job1', 'job2', 'job3'],
        models_count: 3,
        platform: SyncPlatform.ALL,
        status: 'initiated'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await syncService.syncAll();

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/sync/sync-all', {
        platform: SyncPlatform.ALL,
        agency_id: undefined
      });
      expect(result).toEqual(mockResponse);
    });

    it('should sync all models for specific platform and agency', async () => {
      const platform = SyncPlatform.ONLYFANS;
      const agencyId = 'agency123';

      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await syncService.syncAll(platform, agencyId);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/sync/sync-all', {
        platform,
        agency_id: agencyId
      });
    });
  });

  describe('getDashboardOverview', () => {
    it('should fetch dashboard overview', async () => {
      const mockOverview = {
        total_api_keys: 25,
        active_syncs: 5,
        failed_syncs_24h: 3,
        success_rate: 0.92,
        platforms: {
          onlyfans: { active: 15, total: 18 },
          inflow: { active: 10, total: 12 }
        }
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockOverview });

      const result = await syncService.getDashboardOverview();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/sync/dashboard/overview');
      expect(result).toEqual(mockOverview);
    });
  });

  describe('getApiKeysSyncStatus', () => {
    it('should fetch API keys sync status without filters', async () => {
      const mockApiKeys = [
        {
          api_key_id: 'key1',
          provider: 'onlyfans',
          sync_enabled: true,
          last_sync: '2025-01-31T10:00:00Z',
          status: 'success'
        },
        {
          api_key_id: 'key2',
          provider: 'inflow',
          sync_enabled: false,
          last_sync: null,
          status: 'disabled'
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockApiKeys });

      const result = await syncService.getApiKeysSyncStatus();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/sync/dashboard/api-keys?');
      expect(result).toEqual(mockApiKeys);
    });

    it('should fetch API keys sync status with filters', async () => {
      const filters = {
        provider: 'onlyfans',
        syncEnabled: true,
        hasErrors: false
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await syncService.getApiKeysSyncStatus(filters);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        '/api/v1/sync/dashboard/api-keys?provider=onlyfans&sync_enabled=true&has_errors=false'
      );
    });
  });

  describe('getDashboardHistory', () => {
    it('should fetch dashboard history without filters', async () => {
      const mockHistory = [
        {
          id: 'hist1',
          api_key_id: 'key1',
          status: 'completed',
          started_at: '2025-01-31T10:00:00Z',
          completed_at: '2025-01-31T10:05:00Z'
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockHistory });

      const result = await syncService.getDashboardHistory();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/sync/dashboard/history?');
      expect(result).toEqual(mockHistory);
    });

    it('should fetch dashboard history with all filters', async () => {
      const filters = {
        apiKeyId: 'key123',
        status: 'failed',
        startDate: new Date('2025-01-01'),
        endDate: new Date('2025-01-31'),
        limit: 50
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await syncService.getDashboardHistory(filters);

      // URLSearchParams encodes the colons in ISO date strings
      const expectedUrl = '/api/v1/sync/dashboard/history?' +
        'api_key_id=key123&' +
        'status=failed&' +
        `start_date=${encodeURIComponent(filters.startDate.toISOString())}&` +
        `end_date=${encodeURIComponent(filters.endDate.toISOString())}&` +
        'limit=50';

      expect(mockedApiClient.get).toHaveBeenCalledWith(expectedUrl);
    });
  });

  describe('getSyncHealth', () => {
    it('should fetch sync health status', async () => {
      const mockHealth = {
        status: 'healthy',
        queue_depth: 15,
        error_rate: 0.02,
        average_processing_time: 250,
        warnings: [],
        last_check: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockHealth });

      const result = await syncService.getSyncHealth();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/sync/dashboard/health');
      expect(result).toEqual(mockHealth);
    });
  });

  describe('getDeltaSyncState', () => {
    it('should fetch delta sync state for a service', async () => {
      const serviceName = 'onlyfans';
      const mockDeltaState = {
        service: serviceName,
        last_sync_timestamp: '2025-01-31T10:00:00Z',
        checkpoint: 'checkpoint-123',
        records_processed: 5000,
        is_active: true
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockDeltaState });

      const result = await syncService.getDeltaSyncState(serviceName);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/api/v1/sync/dashboard/delta-sync/${serviceName}`
      );
      expect(result).toEqual(mockDeltaState);
    });
  });

  describe('triggerManualSync', () => {
    it('should trigger manual sync with default priority', async () => {
      const apiKeyId = 'key123';
      const mockResponse = {
        job_id: 'job456',
        api_key_id: apiKeyId,
        priority: 'normal',
        status: 'queued'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await syncService.triggerManualSync(apiKeyId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        `/api/v1/sync/dashboard/trigger-sync/${apiKeyId}?priority=normal`
      );
      expect(result).toEqual(mockResponse);
    });

    it('should trigger manual sync with custom priority', async () => {
      const apiKeyId = 'key123';
      const priority = 'high';

      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await syncService.triggerManualSync(apiKeyId, priority);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        `/api/v1/sync/dashboard/trigger-sync/${apiKeyId}?priority=${priority}`
      );
    });
  });

  describe('resetSyncState', () => {
    it('should reset sync state for an API key', async () => {
      const apiKeyId = 'key123';
      const mockResponse = {
        api_key_id: apiKeyId,
        status: 'reset_complete',
        message: 'Sync state has been reset'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await syncService.resetSyncState(apiKeyId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        `/api/v1/sync/dashboard/reset-sync-state/${apiKeyId}`
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe('error handling', () => {
    it('should propagate network errors', async () => {
      const networkError = new Error('Network failure');
      mockedApiClient.get.mockRejectedValueOnce(networkError);

      await expect(syncService.getStatus('model123')).rejects.toThrow('Network failure');
    });

    it('should handle API response errors', async () => {
      const apiError = {
        response: {
          status: 400,
          data: { message: 'Invalid sync request' }
        }
      };
      mockedApiClient.post.mockRejectedValueOnce(apiError);

      await expect(syncService.syncNow({
        model_id: 'model123',
        platforms: []
      })).rejects.toMatchObject(apiError);
    });

    it('should handle authorization errors', async () => {
      const authError = {
        response: {
          status: 401,
          data: { message: 'Unauthorized' }
        }
      };
      mockedApiClient.post.mockRejectedValueOnce(authError);

      await expect(syncService.triggerManualSync('key123')).rejects.toMatchObject(authError);
    });
  });
});