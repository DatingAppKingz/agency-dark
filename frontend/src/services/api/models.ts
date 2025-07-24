import apiClient from './client';
import { 
  ModelProfile, 
  ModelContent, 
  ModelAvailability, 
  ModelPreferences,
  ModelStats,
  CreateModelProfileData, 
  UpdateModelProfileData 
} from '@/types/models';
import { PaginatedResponse, QueryParams } from '@/types/api';

export const modelsService = {
  // Model Profiles
  async getModels(params?: QueryParams): Promise<PaginatedResponse<ModelProfile>> {
    const { data } = await apiClient.get('/models', { params });
    return data;
  },

  async getModel(modelId: string): Promise<ModelProfile> {
    const { data } = await apiClient.get(`/models/${modelId}`);
    return data;
  },

  async createModel(modelData: CreateModelProfileData): Promise<ModelProfile> {
    const { data } = await apiClient.post('/models', modelData);
    return data;
  },

  async updateModel(modelId: string, modelData: UpdateModelProfileData): Promise<ModelProfile> {
    const { data } = await apiClient.put(`/models/${modelId}`, modelData);
    return data;
  },

  async deleteModel(modelId: string): Promise<void> {
    await apiClient.delete(`/models/${modelId}`);
  },

  // Model Content
  async getModelContent(modelId: string): Promise<ModelContent[]> {
    const { data } = await apiClient.get(`/models/${modelId}/content`);
    return data;
  },

  async uploadContent(modelId: string, file: File, metadata: Partial<ModelContent>): Promise<ModelContent> {
    const formData = new FormData();
    formData.append('file', file);
    Object.keys(metadata).forEach(key => {
      formData.append(key, String(metadata[key as keyof ModelContent]));
    });

    const { data } = await apiClient.post(`/models/${modelId}/content`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async deleteContent(modelId: string, contentId: string): Promise<void> {
    await apiClient.delete(`/models/${modelId}/content/${contentId}`);
  },

  // Model Availability
  async getAvailability(modelId: string): Promise<ModelAvailability[]> {
    const { data } = await apiClient.get(`/models/${modelId}/availability`);
    return data;
  },

  async updateAvailability(modelId: string, availability: ModelAvailability[]): Promise<ModelAvailability[]> {
    const { data } = await apiClient.put(`/models/${modelId}/availability`, { availability });
    return data;
  },

  // Model Preferences
  async getPreferences(modelId: string): Promise<ModelPreferences> {
    const { data } = await apiClient.get(`/models/${modelId}/preferences`);
    return data;
  },

  async updatePreferences(modelId: string, preferences: Partial<ModelPreferences>): Promise<ModelPreferences> {
    const { data } = await apiClient.put(`/models/${modelId}/preferences`, preferences);
    return data;
  },

  // Model Statistics
  async getStats(modelId: string, period: 'day' | 'week' | 'month' = 'month'): Promise<ModelStats> {
    const { data } = await apiClient.get(`/models/${modelId}/stats`, { 
      params: { period } 
    });
    return data;
  },

  // Bulk operations
  async toggleModelStatus(modelId: string, isActive: boolean): Promise<ModelProfile> {
    const { data } = await apiClient.patch(`/models/${modelId}/status`, { is_active: isActive });
    return data;
  },

  // Upload avatar/cover
  async uploadAvatar(modelId: string, file: File): Promise<{ avatar_url: string }> {
    const formData = new FormData();
    formData.append('avatar', file);

    const { data } = await apiClient.post(`/models/${modelId}/avatar`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async uploadCover(modelId: string, file: File): Promise<{ cover_image_url: string }> {
    const formData = new FormData();
    formData.append('cover', file);

    const { data } = await apiClient.post(`/models/${modelId}/cover`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },
};