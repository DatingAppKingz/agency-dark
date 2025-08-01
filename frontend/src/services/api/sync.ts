import apiClient from './client';
import {
  SyncRequest,
  SyncResponse,
  SyncStatusResponse,
  SyncHistoryItem,
  SyncStats,
  SyncScheduleRequest,
  SyncScheduleResponse,
  SyncPlatform,
  SyncOverviewResponse,
  ApiKeySyncStatusResponse,
  SyncHealthResponse,
  DeltaSyncStateResponse
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
  },

  // Dashboard endpoints
  async getDashboardOverview(): Promise<SyncOverviewResponse> {
    const response = await apiClient.get('/api/v1/sync/dashboard/overview');
    return response.data;
  },

  async getApiKeysSyncStatus(
    filters?: {
      provider?: string;
      syncEnabled?: boolean;
      hasErrors?: boolean;
    }
  ): Promise<ApiKeySyncStatusResponse[]> {
    const params = new URLSearchParams();
    if (filters?.provider) params.append('provider', filters.provider);
    if (filters?.syncEnabled !== undefined) params.append('sync_enabled', String(filters.syncEnabled));
    if (filters?.hasErrors !== undefined) params.append('has_errors', String(filters.hasErrors));
    
    const response = await apiClient.get(`/api/v1/sync/dashboard/api-keys?${params}`);
    return response.data;
  },

  async getDashboardHistory(
    filters?: {
      apiKeyId?: string;
      status?: string;
      startDate?: Date;
      endDate?: Date;
      limit?: number;
    }
  ): Promise<SyncHistoryItem[]> {
    const params = new URLSearchParams();
    if (filters?.apiKeyId) params.append('api_key_id', filters.apiKeyId);
    if (filters?.status) params.append('status', filters.status);
    if (filters?.startDate) params.append('start_date', filters.startDate.toISOString());
    if (filters?.endDate) params.append('end_date', filters.endDate.toISOString());
    if (filters?.limit) params.append('limit', String(filters.limit));
    
    const response = await apiClient.get(`/api/v1/sync/dashboard/history?${params}`);
    return response.data;
  },

  async getSyncHealth(): Promise<SyncHealthResponse> {
    const response = await apiClient.get('/api/v1/sync/dashboard/health');
    return response.data;
  },

  async getDeltaSyncState(serviceName: string): Promise<DeltaSyncStateResponse> {
    const response = await apiClient.get(`/api/v1/sync/dashboard/delta-sync/${serviceName}`);
    return response.data;
  },

  async triggerManualSync(apiKeyId: string, priority: 'high' | 'normal' | 'low' = 'normal'): Promise<any> {
    const response = await apiClient.post(
      `/api/v1/sync/dashboard/trigger-sync/${apiKeyId}?priority=${priority}`
    );
    return response.data;
  },

  async resetSyncState(apiKeyId: string): Promise<any> {
    const response = await apiClient.post(`/api/v1/sync/dashboard/reset-sync-state/${apiKeyId}`);
    return response.data;
  }
};
