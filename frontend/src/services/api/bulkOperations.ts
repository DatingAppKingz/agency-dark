import apiClient from './client';
import {
  BulkOperation,
  BulkOperationCreate,
  BulkOperationLog,
  BulkOperationProgress,
  BulkOperationStats,
  BulkOperationTemplate,
  PaginatedBulkOperations,
} from '@/types/bulkOperations';

export const bulkOperationsService = {
  // Bulk operations CRUD
  async createBulkOperation(data: BulkOperationCreate): Promise<BulkOperation> {
    const response = await apiClient.post('/api/v1/bulk-operations', data);
    return response.data;
  },

  async getBulkOperation(id: string): Promise<BulkOperation> {
    const response = await apiClient.get(`/api/v1/bulk-operations/${id}`);
    return response.data;
  },

  async getBulkOperations(params?: {
    limit?: number;
    offset?: number;
    status?: string;
    operation_type?: string;
    search?: string;
  }): Promise<PaginatedBulkOperations> {
    const response = await apiClient.get('/api/v1/bulk-operations', { params });
    return response.data;
  },

  async cancelBulkOperation(id: string): Promise<void> {
    await apiClient.post(`/api/v1/bulk-operations/${id}/cancel`);
  },

  async retryBulkOperation(id: string): Promise<BulkOperation> {
    const response = await apiClient.post(`/api/v1/bulk-operations/${id}/retry`);
    return response.data;
  },

  async rollbackBulkOperation(id: string): Promise<BulkOperation> {
    const response = await apiClient.post(`/api/v1/bulk-operations/${id}/rollback`);
    return response.data;
  },

  // Operation progress
  async getBulkOperationProgress(id: string): Promise<BulkOperationProgress> {
    const response = await apiClient.get(`/api/v1/bulk-operations/${id}/progress`);
    return response.data;
  },

  // Operation logs
  async getBulkOperationLogs(
    operationId: string,
    params?: { limit?: number; offset?: number; status?: string }
  ): Promise<{ items: BulkOperationLog[]; total: number }> {
    const response = await apiClient.get(`/api/v1/bulk-operations/${operationId}/logs`, { params });
    return response.data;
  },

  // Templates
  async getBulkOperationTemplates(): Promise<BulkOperationTemplate[]> {
    const response = await apiClient.get('/api/v1/bulk-operations/templates');
    return response.data;
  },

  async createBulkOperationTemplate(data: Partial<BulkOperationTemplate>): Promise<BulkOperationTemplate> {
    const response = await apiClient.post('/api/v1/bulk-operations/templates', data);
    return response.data;
  },

  async deleteBulkOperationTemplate(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/bulk-operations/templates/${id}`);
  },

  // Statistics
  async getBulkOperationStats(): Promise<BulkOperationStats> {
    const response = await apiClient.get('/api/v1/bulk-operations/stats');
    return response.data;
  },

  // Recipient count for messages
  async getRecipientCount(params: {
    type: string;
    filters?: Record<string, any>;
  }): Promise<{ count: number }> {
    const response = await apiClient.post('/api/v1/bulk-operations/recipients/count', params);
    return response.data;
  },

  // Validate operation
  async validateBulkOperation(data: BulkOperationCreate): Promise<{
    valid: boolean;
    errors?: string[];
    warnings?: string[];
  }> {
    const response = await apiClient.post('/api/v1/bulk-operations/validate', data);
    return response.data;
  },

  // Download results
  async downloadBulkOperationResults(id: string): Promise<Blob> {
    const response = await apiClient.get(`/api/v1/bulk-operations/${id}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },
};