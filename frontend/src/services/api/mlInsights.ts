import apiClient from './client';
import {
  RevenueForecastResponse,
  ChurnPredictionResponse,
  ContentRecommendationResponse,
  AnomalyDetectionResponse,
  MLInsightsSummary,
  TrainingStatus,
  ModelMetrics,
} from '@/types/mlInsights';

export const mlInsightsService = {
  // Training endpoints
  async trainRevenueModel(agencyId?: string): Promise<TrainingStatus> {
    const { data } = await apiClient.post('/ml-insights/train/revenue-forecast', {
      agency_id: agencyId,
    });
    return data;
  },

  async trainChurnModel(agencyId?: string): Promise<TrainingStatus> {
    const { data } = await apiClient.post('/ml-insights/train/churn-prediction', {
      agency_id: agencyId,
    });
    return data;
  },

  async trainContentModel(agencyId?: string): Promise<TrainingStatus> {
    const { data } = await apiClient.post('/ml-insights/train/content-recommendation', {
      agency_id: agencyId,
    });
    return data;
  },

  // Prediction endpoints
  async getRevenueForecast(
    periods: number = 30,
    agencyId?: string
  ): Promise<RevenueForecastResponse> {
    const params = new URLSearchParams();
    params.append('periods', periods.toString());
    if (agencyId) params.append('agency_id', agencyId);
    
    const { data } = await apiClient.get(`/ml-insights/revenue-forecast?${params}`);
    return data;
  },

  async getChurnPredictions(
    agencyId?: string,
    modelId?: string
  ): Promise<ChurnPredictionResponse> {
    const params = new URLSearchParams();
    if (agencyId) params.append('agency_id', agencyId);
    if (modelId) params.append('model_id', modelId);
    
    const { data } = await apiClient.get(`/ml-insights/churn-predictions?${params}`);
    return data;
  },

  async getContentRecommendations(
    agencyId?: string,
    modelId?: string,
    fanId?: string
  ): Promise<ContentRecommendationResponse> {
    const params = new URLSearchParams();
    if (agencyId) params.append('agency_id', agencyId);
    if (modelId) params.append('model_id', modelId);
    if (fanId) params.append('fan_id', fanId);
    
    const { data } = await apiClient.get(`/ml-insights/content-recommendations?${params}`);
    return data;
  },

  async getAnomalies(
    agencyId?: string,
    timeRange: 'day' | 'week' | 'month' = 'day'
  ): Promise<AnomalyDetectionResponse> {
    const params = new URLSearchParams();
    if (agencyId) params.append('agency_id', agencyId);
    params.append('time_range', timeRange);
    
    const { data } = await apiClient.get(`/ml-insights/anomalies?${params}`);
    return data;
  },

  // Summary endpoint
  async getInsightsSummary(agencyId?: string): Promise<MLInsightsSummary> {
    const params = agencyId ? `?agency_id=${agencyId}` : '';
    const { data } = await apiClient.get(`/ml-insights/summary${params}`);
    return data;
  },

  // Model metrics
  async getModelMetrics(modelName: string, agencyId?: string): Promise<ModelMetrics> {
    const params = new URLSearchParams();
    params.append('model_name', modelName);
    if (agencyId) params.append('agency_id', agencyId);
    
    const { data } = await apiClient.get(`/ml-insights/model-metrics?${params}`);
    return data;
  },
};