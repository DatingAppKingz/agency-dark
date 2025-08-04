import { apiClient as api } from '@/services/api';
import {
  EmailTemplate,
  EmailCampaign,
  EmailStatus,
  EmailTracking,
  EmailSubscriptionPreferences,
  EmailAutomationFlow,
  SendEmailData,
  SendTemplateEmailData,
  BulkEmailData,
  EmailAnalytics,
  EmailSettings,
} from '@/types/email';

interface GetTemplatesParams {
  page?: number;
  size?: number;
  category?: string;
  is_active?: boolean;
  search?: string;
}

interface TemplateResponse {
  items: EmailTemplate[];
  total: number;
  page: number;
  size: number;
}

interface GetCampaignsParams {
  page?: number;
  size?: number;
  status?: string;
  search?: string;
}

interface CampaignResponse {
  items: EmailCampaign[];
  total: number;
  page: number;
  size: number;
}

interface GetEmailHistoryParams {
  page?: number;
  size?: number;
  model_id?: string;
  fan_id?: string;
  status?: EmailStatus;
  start_date?: string;
  end_date?: string;
}

interface EmailHistoryResponse {
  items: EmailTracking[];
  total: number;
  page: number;
  size: number;
}

interface ScheduleEmailData extends SendEmailData {
  scheduled_for: string;
}

interface CreateTemplateData {
  name: string;
  subject: string;
  body_html: string;
  body_text?: string;
  category: string;
  variables?: string[];
  preview_text?: string;
  from_name?: string;
  from_email?: string;
  reply_to?: string;
}

interface CreateCampaignData {
  name: string;
  template_id: string;
  audience_type: 'all_models' | 'active_models' | 'new_models' | 'custom';
  filters?: any;
  scheduled_at?: string;
}

interface CreateAutomationFlowData {
  name: string;
  trigger: string;
  steps: Array<{
    template_id: string;
    delay_hours: number;
    condition?: any;
  }>;
}

interface TriggerAutomationData {
  flow_id: string;
  model_id: string;
  variables?: Record<string, any>;
}

interface PreviewTemplateData {
  template_id: string;
  variables?: Record<string, any>;
}

class EmailService {
  // Email Sending
  async sendEmail(data: SendEmailData): Promise<{ id: string; status: EmailStatus; sent_at: string }> {
    const response = await api.post('/email/send', data);
    return response.data;
  }

  async sendTemplateEmail(data: SendTemplateEmailData): Promise<{ id: string; status: EmailStatus; sent_at: string }> {
    const response = await api.post('/email/send-template', data);
    return response.data;
  }

  async sendBulkEmail(data: BulkEmailData): Promise<{
    batch_id: string;
    total: number;
    queued: number;
    failed: number;
  }> {
    const response = await api.post('/email/send-bulk', data);
    return response.data;
  }

  async scheduleEmail(data: ScheduleEmailData): Promise<{
    id: string;
    status: EmailStatus;
    scheduled_for: string;
  }> {
    const response = await api.post('/email/schedule', data);
    return response.data;
  }

  // Template Management
  async getTemplates(params: GetTemplatesParams = {}): Promise<TemplateResponse> {
    const response = await api.get<TemplateResponse>('/email/templates', { params });
    return response.data;
  }

  async getTemplate(templateId: string): Promise<EmailTemplate> {
    const response = await api.get<EmailTemplate>(`/email/templates/${templateId}`);
    return response.data;
  }

  async createTemplate(data: CreateTemplateData): Promise<EmailTemplate> {
    const response = await api.post<EmailTemplate>('/email/templates', data);
    return response.data;
  }

  async updateTemplate(templateId: string, data: Partial<CreateTemplateData>): Promise<EmailTemplate> {
    const response = await api.put<EmailTemplate>(`/email/templates/${templateId}`, data);
    return response.data;
  }

  async deleteTemplate(templateId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(`/email/templates/${templateId}`);
    return response.data;
  }

  async previewTemplate(data: PreviewTemplateData): Promise<{
    subject: string;
    body_html: string;
    body_text: string;
  }> {
    const response = await api.post('/email/templates/preview', data);
    return response.data;
  }

  async duplicateTemplate(templateId: string, name: string): Promise<EmailTemplate> {
    const response = await api.post<EmailTemplate>(`/email/templates/${templateId}/duplicate`, { name });
    return response.data;
  }

  // Campaign Management
  async getCampaigns(params: GetCampaignsParams = {}): Promise<CampaignResponse> {
    const response = await api.get<CampaignResponse>('/email/campaigns', { params });
    return response.data;
  }

  async getCampaign(campaignId: string): Promise<EmailCampaign> {
    const response = await api.get<EmailCampaign>(`/email/campaigns/${campaignId}`);
    return response.data;
  }

  async createCampaign(data: CreateCampaignData): Promise<EmailCampaign> {
    const response = await api.post<EmailCampaign>('/email/campaigns', data);
    return response.data;
  }

  async updateCampaign(campaignId: string, data: Partial<CreateCampaignData>): Promise<EmailCampaign> {
    const response = await api.put<EmailCampaign>(`/email/campaigns/${campaignId}`, data);
    return response.data;
  }

  async deleteCampaign(campaignId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(`/email/campaigns/${campaignId}`);
    return response.data;
  }

  async launchCampaign(campaignId: string): Promise<EmailCampaign> {
    const response = await api.post<EmailCampaign>(`/email/campaigns/${campaignId}/launch`);
    return response.data;
  }

  async pauseCampaign(campaignId: string): Promise<EmailCampaign> {
    const response = await api.post<EmailCampaign>(`/email/campaigns/${campaignId}/pause`);
    return response.data;
  }

  async resumeCampaign(campaignId: string): Promise<EmailCampaign> {
    const response = await api.post<EmailCampaign>(`/email/campaigns/${campaignId}/resume`);
    return response.data;
  }

  async getCampaignAnalytics(campaignId: string): Promise<EmailAnalytics> {
    const response = await api.get<EmailAnalytics>(`/email/campaigns/${campaignId}/analytics`);
    return response.data;
  }

  // Email Tracking
  async getEmailStatus(emailId: string): Promise<EmailTracking> {
    const response = await api.get<EmailTracking>(`/email/status/${emailId}`);
    return response.data;
  }

  async getEmailHistory(params: GetEmailHistoryParams = {}): Promise<EmailHistoryResponse> {
    const response = await api.get<EmailHistoryResponse>('/email/history', { params });
    return response.data;
  }

  async trackOpen(emailId: string): Promise<{ success: boolean }> {
    const response = await api.post('/email/track/open', { email_id: emailId });
    return response.data;
  }

  async trackClick(emailId: string, url: string): Promise<{ success: boolean }> {
    const response = await api.post('/email/track/click', { email_id: emailId, url });
    return response.data;
  }

  async getEmailAnalytics(startDate: string, endDate: string): Promise<EmailAnalytics> {
    const response = await api.get<EmailAnalytics>('/email/analytics', {
      params: { start_date: startDate, end_date: endDate },
    });
    return response.data;
  }

  // Subscription Management
  async getSubscriptionPreferences(modelId: string): Promise<EmailSubscriptionPreferences> {
    const response = await api.get<EmailSubscriptionPreferences>(`/email/subscriptions/${modelId}`);
    return response.data;
  }

  async updateSubscriptionPreferences(
    modelId: string,
    preferences: Partial<EmailSubscriptionPreferences>
  ): Promise<EmailSubscriptionPreferences> {
    const response = await api.put<EmailSubscriptionPreferences>(
      `/email/subscriptions/${modelId}`,
      preferences
    );
    return response.data;
  }

  async unsubscribe(modelId: string, category: string): Promise<{ success: boolean }> {
    const response = await api.post('/email/unsubscribe', { model_id: modelId, category });
    return response.data;
  }

  async resubscribe(modelId: string, category: string): Promise<{ success: boolean }> {
    const response = await api.post('/email/resubscribe', { model_id: modelId, category });
    return response.data;
  }

  async getUnsubscribers(params: { page?: number; size?: number } = {}): Promise<any> {
    const response = await api.get('/email/unsubscribers', { params });
    return response.data;
  }

  // Email Automation
  async getAutomatedFlows(params: { page?: number; size?: number } = {}): Promise<any> {
    const response = await api.get('/email/automations', { params });
    return response.data;
  }

  async getAutomatedFlow(flowId: string): Promise<EmailAutomationFlow> {
    const response = await api.get<EmailAutomationFlow>(`/email/automations/${flowId}`);
    return response.data;
  }

  async createAutomatedFlow(data: CreateAutomationFlowData): Promise<EmailAutomationFlow> {
    const response = await api.post<EmailAutomationFlow>('/email/automations', data);
    return response.data;
  }

  async updateAutomatedFlow(
    flowId: string,
    data: Partial<CreateAutomationFlowData>
  ): Promise<EmailAutomationFlow> {
    const response = await api.put<EmailAutomationFlow>(`/email/automations/${flowId}`, data);
    return response.data;
  }

  async deleteAutomatedFlow(flowId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(`/email/automations/${flowId}`);
    return response.data;
  }

  async toggleAutomatedFlow(flowId: string, isActive: boolean): Promise<EmailAutomationFlow> {
    const response = await api.put<EmailAutomationFlow>(`/email/automations/${flowId}/toggle`, {
      is_active: isActive,
    });
    return response.data;
  }

  async triggerAutomatedEmail(data: TriggerAutomationData): Promise<{
    automation_id: string;
    status: string;
  }> {
    const response = await api.post('/email/automations/trigger', data);
    return response.data;
  }

  // Email Settings
  async getEmailSettings(): Promise<EmailSettings> {
    const response = await api.get<EmailSettings>('/email/settings');
    return response.data;
  }

  async updateEmailSettings(settings: Partial<EmailSettings>): Promise<EmailSettings> {
    const response = await api.put<EmailSettings>('/email/settings', settings);
    return response.data;
  }

  // Utility Methods
  async validateEmailAddress(email: string): Promise<{ valid: boolean; reason?: string }> {
    const response = await api.post('/email/validate', { email });
    return response.data;
  }

  async getEmailProviderStatus(): Promise<{
    provider: string;
    status: 'active' | 'degraded' | 'down';
    quota: {
      used: number;
      limit: number;
      reset_at: string;
    };
  }> {
    const response = await api.get('/email/provider/status');
    return response.data;
  }

  async exportEmailHistory(
    params: GetEmailHistoryParams & { format: 'csv' | 'xlsx' }
  ): Promise<Blob> {
    const response = await api.get<Blob>('/email/history/export', {
      params,
      responseType: 'blob',
    });
    return response.data;
  }

  async testEmailTemplate(templateId: string, testEmail: string): Promise<{ success: boolean }> {
    const response = await api.post(`/email/templates/${templateId}/test`, {
      test_email: testEmail,
    });
    return response.data;
  }
}

export const emailService = new EmailService();