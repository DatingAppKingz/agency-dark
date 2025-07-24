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
  // Get dashboard statistics
  async getDashboardStats(): Promise<DashboardStats> {
    const { data } = await apiClient.get('/analytics/dashboard');
    return data;
  },

  // Get agency statistics (for super admin)
  async getAgencyStats(): Promise<AgencyStats[]> {
    const { data } = await apiClient.get('/analytics/agencies');
    return data;
  },

  // Get model performance
  async getModelPerformance(period: 'day' | 'week' | 'month' = 'month'): Promise<ModelPerformance[]> {
    const { data } = await apiClient.get('/analytics/models', { 
      params: { period } 
    });
    return data;
  },

  // Get revenue chart data
  async getRevenueChart(period: 'day' | 'week' | 'month' = 'month') {
    const { data } = await apiClient.get('/analytics/revenue-chart', { 
      params: { period } 
    });
    return data;
  },

  // Get message volume chart
  async getMessageChart(period: 'day' | 'week' | 'month' = 'month') {
    const { data } = await apiClient.get('/analytics/message-chart', { 
      params: { period } 
    });
    return data;
  },
};