import { apiClient } from './client';
import {
  SyncRequest,
  SyncResponse,
  SyncStatusResponse,
  SyncHistoryItem,
  SyncStats,
  SyncScheduleRequest,
  SyncScheduleResponse,
  SyncPlatform
} from '@/types/sync';

export const syncService = {
  // Trigger immediate sync
  async syncNow(request: SyncRequest): Promise<SyncResponse> {
    const response = await apiClient.post('/api/v1/sync/sync-now', request);
    return response.data;
  },

  // Get sync status for a model
  async getStatus(modelId: string): Promise<SyncStatusResponse> {
    const response = await apiClient.get(`/api/v1/sync/status/${modelId}`);
    return response.data;
  },

  // Get sync history
  async getHistory(modelId: string, limit: number = 10): Promise<SyncHistoryItem[]> {
    const response = await apiClient.get(`/api/v1/sync/history/${modelId}?limit=${limit}`);
    return response.data;
  },

  // Schedule a sync
  async scheduleSync(request: SyncScheduleRequest): Promise<SyncScheduleResponse> {
    const response = await apiClient.post('/api/v1/sync/schedule', request);
    return response.data;
  },

  // Cancel scheduled sync
  async cancelScheduledSync(jobId: string): Promise<void> {
    await apiClient.delete(`/api/v1/sync/schedule/${jobId}`);
  },

  // Get sync statistics
  async getStats(agencyId?: string): Promise<SyncStats> {
    const params = agencyId ? `?agency_id=${agencyId}` : '';
    const response = await apiClient.get(`/api/v1/sync/stats${params}`);
    return response.data;
  },

  // Sync all models
  async syncAll(platform: SyncPlatform = SyncPlatform.ALL, agencyId?: string): Promise<any> {
    const response = await apiClient.post('/api/v1/sync/sync-all', {
      platform,
      agency_id: agencyId
    });
    return response.data;
  }
};