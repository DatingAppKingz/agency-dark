import apiClient from './client';

export interface DashboardStats {
  total_users: number;
  active_models: number;
  total_revenue: number;
  total_messages: number;
  new_users_today: number;
  revenue_today: number;
  messages_today: number;
  active_chats: number;
}

export interface AgencyStats {
  agency_id: string;
  agency_name: string;
  total_models: number;
  total_revenue: number;
  active_subscriptions: number;
  churn_rate: number;
}

export interface ModelPerformance {
  model_id: string;
  model_name: string;
  revenue: number;
  messages: number;
  fans: number;
  conversion_rate: number;
}

export const analyticsService = {
  // Get dashboard summary for a model
  async getDashboardSummary(modelId: string, period: 'today' | 'week' | 'month' = 'today') {
    const { data } = await apiClient.get(`/analytics/dashboard/${modelId}`, {
      params: { period }
    });
    return data;
  },

  // Get subscriber growth chart
  async getSubscriberGrowthChart(modelId: string, startDate: string, endDate: string, granularity: 'hour' | 'day' | 'week' | 'month' = 'day') {
    const { data } = await apiClient.post('/analytics/charts/subscriber-growth', null, {
      params: {
        model_id: modelId,
        period_start: startDate,
        period_end: endDate,
        granularity
      }
    });
    return data;
  },

  // Get revenue timeline chart
  async getRevenueTimelineChart(modelId: string, startDate: string, endDate: string, granularity: 'hour' | 'day' | 'week' | 'month' = 'day') {
    const { data } = await apiClient.post('/analytics/charts/revenue-timeline', null, {
      params: {
        model_id: modelId,
        period_start: startDate,
        period_end: endDate,
        granularity
      }
    });
    return data;
  },

  // Get fan revenue chart
  async getFanRevenueChart(modelId: string, fanIds: string[], startDate: string, endDate: string, granularity: 'hour' | 'day' | 'week' | 'month' = 'day') {
    const { data } = await apiClient.post('/analytics/charts/fan-revenue', {
      entity_ids: fanIds,
      period_start: startDate,
      period_end: endDate,
      granularity,
      chart_type: 'fan_revenue'
    }, {
      params: { model_id: modelId }
    });
    return data;
  },

  // Get category popularity
  async getCategoryPopularity(modelId: string, startDate: string, endDate: string) {
    const { data } = await apiClient.get(`/analytics/categories/${modelId}`, {
      params: {
        period_start: startDate,
        period_end: endDate
      }
    });
    return data;
  },

  // Get content performance
  async getContentPerformance(modelId: string, contentIds: string[]) {
    const { data } = await apiClient.post('/analytics/content/performance', null, {
      params: {
        model_id: modelId,
        content_ids: contentIds
      }
    });
    return data;
  },

  // Export analytics data
  async exportAnalytics(modelId: string, exportType: 'revenue' | 'subscribers' | 'content' | 'fans', startDate: string, endDate: string, format: 'csv' | 'json' = 'csv') {
    const { data } = await apiClient.post('/analytics/export', {
      export_type: exportType,
      period_start: startDate,
      period_end: endDate,
      format
    }, {
      params: { model_id: modelId }
    });
    return data;
  },

  // Download exported file
  async downloadExport(exportId: string) {
    const { data } = await apiClient.get(`/analytics/exports/${exportId}/download`, {
      responseType: 'blob'
    });
    return data;
  },

  // Get generic chart data
  async getGenericChart(modelId: string, chartType: string, startDate: string, endDate: string, options?: Record<string, unknown>) {
    const { data } = await apiClient.post('/analytics/charts/generic', {
      chart_type: chartType,
      period_start: startDate,
      period_end: endDate,
      ...options
    }, {
      params: { model_id: modelId }
    });
    return data;
  },

  // Legacy methods - map to new endpoints
  async getDashboardStats(): Promise<DashboardStats> {
    console.log('📊 Fetching dashboard stats...');
    try {
      const { data } = await apiClient.get('/analytics/agency/dashboard-stats');
      console.log('✅ Dashboard stats received:', data);
      return data;
    } catch (error) {
      console.error('❌ Failed to fetch dashboard stats:', error);
      // Return default values on error
      return {
        total_users: 0,
        active_models: 0,
        total_revenue: 0,
        total_messages: 0,
        new_users_today: 0,
        revenue_today: 0,
        messages_today: 0,
        active_chats: 0 };
    }
  },

  async getAgencyStats(): Promise<AgencyStats[]> {
    console.warn('Agency stats not directly available in analytics API');
    return [];
  },

  async getModelPerformance(period: 'day' | 'week' | 'month' = 'month'): Promise<ModelPerformance[]> {
    console.log('📊 Fetching model performance...');
    try {
      const { data } = await apiClient.get('/analytics/agency/model-performance', {
        params: { period }
      });
      console.log('✅ Model performance received:', data);
      return data;
    } catch (error) {
      console.error('❌ Failed to fetch model performance:', error);
      return [];
    }
  },

  async getRevenueChart(period: 'day' | 'week' | 'month' = 'month') {
    try {
      const { data } = await apiClient.get('/analytics/agency/revenue-chart', {
        params: { period }
      });
      
      // Transform data for chart format
      return {
        labels: data.data.map((d: { date: string }) => d.date),
        datasets: [
          {
            label: 'Total Revenue',
            data: data.data.map((d: { revenue: number }) => d.revenue),
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.1)' },
          {
            label: 'Tips',
            data: data.data.map((d: { tips: number }) => d.tips),
            borderColor: 'rgb(255, 99, 132)',
            backgroundColor: 'rgba(255, 99, 132, 0.1)' }
        ]
      };
    } catch (error) {
      console.error('Failed to fetch revenue chart:', error);
      return {
        labels: [],
        datasets: []
      };
    }
  },

  async getMessageChart(_period: 'day' | 'week' | 'month' = 'month') {
    console.warn('Message chart not directly available in analytics API');
    return { labels: [], datasets: [] };
  } };
