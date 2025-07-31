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
import { QueryParams } from '@/types/api';

export const modelsService = {
  // Note: Backend uses orchestration endpoints for model data
  // The following methods integrate with the available backend endpoints

  // Get model profile via orchestration
  async getModel(modelId: string): Promise<any> {
    // Use orchestration endpoint to get model data
    const { data } = await apiClient.get(`/orchestration/sync/${modelId}/status`);
    return data;
  },

  // Get model analytics
  async getModelAnalytics(modelId: string, startDate: string, endDate: string): Promise<any> {
    const { data } = await apiClient.get(`/orchestration/analytics/${modelId}`, {
      params: { start_date: startDate, end_date: endDate }
    });
    return data;
  },

  // Get unified fans for a model
  async getModelFans(modelId: string, params?: { limit?: number; offset?: number }): Promise<any> {
    const { data } = await apiClient.get(`/orchestration/fans/${event}`, { params });
    return data;
  },

  // Trigger sync for model data
  async syncModelData(modelId: string, syncInflow = true, syncOnlyfans = true): Promise<any> {
    const { data } = await apiClient.post(`/orchestration/sync/${modelId}`, null, {
      params: { sync_inflow: syncInflow, sync_onlyfans: syncOnlyfans }
    });
    return data;
  },

  // Get sync status
  async getSyncStatus(modelId: string): Promise<any> {
    const { data } = await apiClient.get(`/orchestration/sync/${modelId}/status`);
    return data;
  },

  // Note: The following are placeholder methods until backend implements full model management
  async getModels(params?: QueryParams): Promise<any> {
    const { data } = await apiClient.get('/api/v1/users/models', { params });
    return data;
  },

  async createModel(event: CreateModelProfileData): Promise<ModelProfile> {
    throw new Error('Model creation not yet implemented in backend');
  },

  async updateModel(modelId: string, data: UpdateModelProfileData): Promise<ModelProfile> {
    throw new Error('Model update not yet implemented in backend');
  },

  async deleteModel(modelId: string): Promise<void> {
    throw new Error('Model deletion not yet implemented in backend');
  },

  // Model Content - placeholder
  async getModelContent(modelId: string): Promise<ModelContent[]> {
    console.warn('Content management through orchestration API');
    return [];
  },

  async uploadContent(modelId: string, file: File, metadata: Partial<ModelContent>): Promise<ModelContent> {
    // Use orchestration content post endpoint
    const formData = new FormData();
    formData.append('file', file);
    
    const { data } = await apiClient.post('/orchestration/content/post', {
      model_id: modelId,
      text: metadata.title || '',
      media_urls: [],
      is_free: metadata.is_free || false,
      publish_immediately: true,
      post_to_onlyfans: true,
      post_to_inflow: true });
    
    return data;
  },

  async deleteContent(modelId: string, contentId: string): Promise<void> {
    throw new Error('Content deletion not yet implemented');
  },

  // Model Messages
  async getModelMessages(modelId: string, fanId?: string, limit = 50, offset = 0): Promise<any> {
    const { data } = await apiClient.get(`/orchestration/messages/${modelId}`, {
      params: { fan_id: fanId, limit, offset }
    });
    return data;
  },

  async sendMessage(modelId: string, fanId: string, text: string, price?: number): Promise<any> {
    const { data } = await apiClient.post('/orchestration/messages/send', {
      fan_id: fanId,
      text,
      price }, {
      params: { model_id: modelId }
    });
    return data;
  },

  // Placeholder methods for features not in backend yet
  async getAvailability(modelId: string): Promise<ModelAvailability[]> {
    console.warn('Availability not implemented in backend');
    return [];
  },

  async updateAvailability(modelId: string, availability: ModelAvailability[]): Promise<ModelAvailability[]> {
    console.warn('Availability update not implemented in backend');
    return availability;
  },

  async getPreferences(modelId: string): Promise<ModelPreferences> {
    console.warn('Preferences not implemented in backend');
    return {} as ModelPreferences;
  },

  async updatePreferences(modelId: string, preferences: Partial<ModelPreferences>): Promise<ModelPreferences> { 
    console.warn('Preferences update not implemented in backend');
    return preferences as ModelPreferences;
    },

  async getStats(modelId: string, period: 'day' | 'week' | 'month' = 'month'): Promise<ModelStats> {
    // Use analytics endpoint
    const endDate = new Date();
    const startDate = new Date();
    
    switch(period) {
      case 'day':
        startDate.setDate(endDate.getDate() - 1);
        break;
      case 'week':
        startDate.setDate(endDate.getDate() - 7);
        break;
      case 'month':
        startDate.setMonth(endDate.getMonth() - 1);
        break;
    }
    
    const analytics = await this.getModelAnalytics(
      startDate.toISOString().split('T')[0],
      endDate.toISOString().split('T')[0]
    );
    
    return analytics;
  },

  async toggleModelStatus(modelId: string, isActive: boolean): Promise<ModelProfile> {
    throw new Error('Status toggle not implemented in backend');
  },

  async uploadAvatar(modelId: string, file: File): Promise<{ avatar_url: string }> {
    throw new Error('Avatar upload not implemented in backend');
  },

  async uploadCover(modelId: string, file: File): Promise<{ cover_image_url: string }> {
    throw new Error('Cover upload not implemented in backend');
  } };
