import apiClient from './client';
import {
  ApiKey,
  ApiKeyCreateRequest,
  ApiKeyUpdateRequest,
  ApiKeyRotateRequest,
  ApiKeyUsageStats,
  ApiKeyAuditLog,
  ApiKeyValidationResult,
  ApiKeyListResponse,
  ApiKeyFilters
} from '@/types/apiKeys';

export const apiKeysService = {
  // List all API keys with optional filters
  async list(filters?: ApiKeyFilters): Promise<ApiKeyListResponse> {
    const params = new URLSearchParams();
    if (filters) {
      Object.entries(filters).forEach(([key, value]) => {
        if (value !== undefined) {
          params.append(key, String(value));
        }
      });
    }
    
    const response = await apiClient.get(`/api/v1/api-keys?${params.toString()}`);
    return response.data;
  },

  // Get a single API key by ID
  async get(id: string): Promise<ApiKey> {
    const response = await apiClient.get(`/api/v1/api-keys/${id}`);
    return response.data;
  },

  // Create a new API key
  async create(data: ApiKeyCreateRequest): Promise<ApiKey> {
    const response = await apiClient.post('/api/v1/api-keys', data);
    return response.data;
  },

  // Update an existing API key
  async update(id: string, data: ApiKeyUpdateRequest): Promise<ApiKey> {
    const response = await apiClient.patch(`/api/v1/api-keys/${id}`, data);
    return response.data;
  },

  // Rotate an API key
  async rotate(id: string, data: ApiKeyRotateRequest): Promise<ApiKey> {
    const response = await apiClient.post(`/api/v1/api-keys/${id}/rotate`, data);
    return response.data;
  },

  // Delete an API key
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/api-keys/${id}`);
  },

  // Validate an API key
  async validate(provider: string, key: string): Promise<ApiKeyValidationResult> {
    const response = await apiClient.post('/api/v1/api-keys/validate', {
      provider,
      key
    });
    return response.data;
  },

  // Get usage statistics for an API key
  async getUsageStats(id: string, days: number = 30): Promise<ApiKeyUsageStats> {
    const response = await apiClient.get(`/api/v1/api-keys/${id}/usage?days=${days}`);
    return response.data;
  },

  // Get audit logs for an API key
  async getAuditLogs(id: string, limit: number = 50): Promise<ApiKeyAuditLog[]> {
    const response = await apiClient.get(`/api/v1/api-keys/${id}/audit-logs?limit=${limit}`);
    return response.data;
  },

  // Test an API key connection
  async testConnection(id: string): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post(`/api/v1/api-keys/${id}/test`);
    return response.data;
  },

  // Get available scopes for a provider
  async getProviderScopes(provider: string): Promise<string[]> {
    const response = await apiClient.get(`/api/v1/api-keys/providers/${provider}/scopes`);
    return response.data;
  }
};
