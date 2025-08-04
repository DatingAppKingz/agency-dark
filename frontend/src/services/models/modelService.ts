import api from '@/services/api';
import { ModelProfile, ModelStatus, ModelDocument, ModelAnalytics } from '@/types/models';

interface GetModelsParams {
  page?: number;
  size?: number;
  search?: string;
  status?: ModelStatus;
  min_earnings?: number;
  max_earnings?: number;
  has_documents?: boolean;
  agency_id?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

interface ModelResponse {
  items: ModelProfile[];
  total: number;
  page: number;
  size: number;
}

interface DateRangeParams {
  start_date: string;
  end_date: string;
}

interface PayoutSettings {
  frequency: string;
  method: string;
  details?: Record<string, any>;
}

class ModelService {
  // CRUD Operations
  async getModels(params: GetModelsParams = {}): Promise<ModelResponse> {
    const { page = 1, size = 20, ...filters } = params;
    const skip = (page - 1) * size;
    
    const response = await api.get<ModelResponse>('/models', {
      params: { ...filters, page, size, skip },
    });
    return response.data;
  }

  async getModel(modelId: string): Promise<ModelProfile> {
    const response = await api.get<ModelProfile>(`/models/${modelId}`);
    return response.data;
  }

  async createModel(data: Partial<ModelProfile>): Promise<ModelProfile> {
    const response = await api.post<ModelProfile>('/models', data);
    return response.data;
  }

  async updateModel(modelId: string, data: Partial<ModelProfile>): Promise<ModelProfile> {
    const response = await api.put<ModelProfile>(`/models/${modelId}`, data);
    return response.data;
  }

  async deleteModel(modelId: string): Promise<{ message: string }> {
    const response = await api.delete<{ message: string }>(`/models/${modelId}`);
    return response.data;
  }

  // Status Management
  async toggleModelStatus(modelId: string, isActive: boolean): Promise<ModelProfile> {
    const response = await api.post<ModelProfile>(`/models/${modelId}/toggle-status`, {
      is_active: isActive,
    });
    return response.data;
  }

  async suspendModel(modelId: string, reason: string): Promise<ModelProfile> {
    const response = await api.post<ModelProfile>(`/models/${modelId}/suspend`, {
      reason,
    });
    return response.data;
  }

  async reactivateModel(modelId: string): Promise<ModelProfile> {
    const response = await api.post<ModelProfile>(`/models/${modelId}/reactivate`);
    return response.data;
  }

  // Document Management
  async uploadDocument(
    modelId: string,
    file: File,
    documentType: string
  ): Promise<ModelDocument> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    const response = await api.post<ModelDocument>(
      `/models/${modelId}/documents`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    );
    return response.data;
  }

  async getDocuments(modelId: string): Promise<ModelDocument[]> {
    const response = await api.get<ModelDocument[]>(`/models/${modelId}/documents`);
    return response.data;
  }

  async verifyDocuments(
    modelId: string,
    approved: boolean,
    notes?: string
  ): Promise<{ verified: boolean }> {
    const response = await api.post<{ verified: boolean }>(
      `/models/${modelId}/documents/verify`,
      { approved, notes }
    );
    return response.data;
  }

  // Analytics
  async getModelAnalytics(
    modelId: string,
    params: DateRangeParams
  ): Promise<ModelAnalytics> {
    const response = await api.get<ModelAnalytics>(`/models/${modelId}/analytics`, {
      params,
    });
    return response.data;
  }

  async getModelPerformance(modelId: string): Promise<any> {
    const response = await api.get(`/models/${modelId}/performance`);
    return response.data;
  }

  // Financial Operations
  async updateCommissionRate(modelId: string, rate: number): Promise<ModelProfile> {
    const response = await api.put<ModelProfile>(`/models/${modelId}/commission`, {
      rate,
    });
    return response.data;
  }

  async updatePayoutSettings(
    modelId: string,
    settings: PayoutSettings
  ): Promise<ModelProfile> {
    const response = await api.put<ModelProfile>(
      `/models/${modelId}/payout-settings`,
      settings
    );
    return response.data;
  }

  async getModelEarnings(
    modelId: string,
    params: DateRangeParams
  ): Promise<any> {
    const response = await api.get(`/models/${modelId}/earnings`, { params });
    return response.data;
  }

  // Bulk Operations
  async bulkUpdateStatus(
    modelIds: string[],
    status: ModelStatus
  ): Promise<{ updated: number }> {
    const response = await api.post<{ updated: number }>('/models/bulk/status', {
      model_ids: modelIds,
      status,
    });
    return response.data;
  }

  async exportModels(format: 'csv' | 'xlsx', filters?: any): Promise<Blob> {
    const response = await api.get<Blob>('/models/export', {
      params: { format, ...filters },
      responseType: 'blob',
    });
    return response.data;
  }

  // Search and Filtering
  async searchModels(query: string): Promise<ModelResponse> {
    const response = await api.get<ModelResponse>('/models/search', {
      params: { q: query },
    });
    return response.data;
  }

  // Onboarding
  async startOnboarding(modelId: string): Promise<any> {
    const response = await api.post(`/models/${modelId}/onboarding/start`);
    return response.data;
  }

  async updateOnboardingStep(
    modelId: string,
    step: string,
    data: any
  ): Promise<any> {
    const response = await api.put(`/models/${modelId}/onboarding/${step}`, data);
    return response.data;
  }

  async completeOnboarding(modelId: string): Promise<ModelProfile> {
    const response = await api.post<ModelProfile>(`/models/${modelId}/onboarding/complete`);
    return response.data;
  }

  // Platform Integration
  async connectPlatform(
    modelId: string,
    platform: string,
    credentials: any
  ): Promise<any> {
    const response = await api.post(`/models/${modelId}/platforms/${platform}/connect`, {
      credentials,
    });
    return response.data;
  }

  async disconnectPlatform(modelId: string, platform: string): Promise<any> {
    const response = await api.delete(`/models/${modelId}/platforms/${platform}`);
    return response.data;
  }

  async syncPlatformData(modelId: string, platform: string): Promise<any> {
    const response = await api.post(`/models/${modelId}/platforms/${platform}/sync`);
    return response.data;
  }
}

export const modelService = new ModelService();