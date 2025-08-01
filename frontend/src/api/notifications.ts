import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export interface NotificationCreate {
  type: 'email' | 'sms' | 'push' | 'in_app' | 'webhook';
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  subject?: string;
  content: string;
  html_content?: string;
  user_id?: string;
  email?: string;
  phone?: string;
  template_id?: string;
  template_data?: Record<string, any>;
  metadata?: Record<string, any>;
  tags?: string[];
  scheduled_at?: string;
  callback_url?: string;
}

export interface BulkNotificationCreate {
  type: 'email' | 'sms' | 'push' | 'in_app' | 'webhook';
  priority?: 'low' | 'normal' | 'high' | 'urgent';
  subject?: string;
  content: string;
  html_content?: string;
  template_id?: string;
  template_data?: Record<string, any>;
  user_ids?: string[];
  emails?: string[];
  phones?: string[];
  user_filters?: Record<string, any>;
  metadata?: Record<string, any>;
  tags?: string[];
  scheduled_at?: string;
}

export interface NotificationTemplateCreate {
  name: string;
  description?: string;
  type: 'email' | 'sms' | 'push' | 'in_app' | 'webhook';
  subject_template?: string;
  content_template: string;
  html_template?: string;
  variables_schema?: Record<string, any>;
  is_active?: boolean;
}

export interface NotificationPreferenceUpdate {
  email_enabled?: boolean;
  sms_enabled?: boolean;
  push_enabled?: boolean;
  in_app_enabled?: boolean;
  categories?: Record<string, boolean>;
  digest_enabled?: boolean;
  digest_frequency?: 'daily' | 'weekly' | 'monthly';
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  timezone?: string;
  preferred_email?: string;
  preferred_phone?: string;
}

export interface TestNotificationRequest {
  type: 'email' | 'sms' | 'push' | 'in_app' | 'webhook';
  template_id?: string;
  template_data?: Record<string, any>;
  subject?: string;
  content?: string;
  html_content?: string;
}

export const notificationApi = {
  // Notifications
  createNotification: (data: NotificationCreate) =>
    axios.post(`${API_BASE_URL}/notifications`, data),

  createBulkNotifications: (data: BulkNotificationCreate) =>
    axios.post(`${API_BASE_URL}/notifications/bulk`, data),

  getNotifications: (params?: {
    skip?: number;
    limit?: number;
    type?: string;
    status?: string;
    priority?: string;
    user_id?: string;
    date_from?: string;
    date_to?: string;
  }) => axios.get(`${API_BASE_URL}/notifications`, { params }),

  getNotification: (notificationId: string) =>
    axios.get(`${API_BASE_URL}/notifications/${notificationId}`),

  updateNotification: (notificationId: string, data: any) =>
    axios.patch(`${API_BASE_URL}/notifications/${notificationId}`, data),

  deleteNotification: (notificationId: string) =>
    axios.delete(`${API_BASE_URL}/notifications/${notificationId}`),

  // Templates
  createTemplate: (data: NotificationTemplateCreate) =>
    axios.post(`${API_BASE_URL}/notifications/templates`, data),

  getTemplates: (params?: {
    skip?: number;
    limit?: number;
    type?: string;
    is_active?: boolean;
  }) => axios.get(`${API_BASE_URL}/notifications/templates`, { params }),

  getTemplate: (templateId: string) =>
    axios.get(`${API_BASE_URL}/notifications/templates/${templateId}`),

  updateTemplate: (templateId: string, data: any) =>
    axios.patch(`${API_BASE_URL}/notifications/templates/${templateId}`, data),

  deleteTemplate: (templateId: string) =>
    axios.delete(`${API_BASE_URL}/notifications/templates/${templateId}`),

  // Preferences
  getPreferences: () =>
    axios.get(`${API_BASE_URL}/notifications/preferences`),

  updatePreferences: (data: NotificationPreferenceUpdate) =>
    axios.patch(`${API_BASE_URL}/notifications/preferences`, data),

  // Events
  getNotificationEvents: (notificationId: string) =>
    axios.get(`${API_BASE_URL}/notifications/${notificationId}/events`),

  trackClick: (notificationId: string, link?: string) =>
    axios.post(`${API_BASE_URL}/notifications/${notificationId}/click`, { link }),

  // Statistics
  getStats: (params?: { start_date?: string; end_date?: string }) =>
    axios.get(`${API_BASE_URL}/notifications/stats/summary`, { params }),

  // Test
  sendTestNotification: (data: TestNotificationRequest) =>
    axios.post(`${API_BASE_URL}/notifications/test`, data),
};