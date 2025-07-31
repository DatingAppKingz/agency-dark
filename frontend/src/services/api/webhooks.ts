import apiClient from './client';
import {
  WebhookCreate,
  WebhookUpdate,
  WebhookResponse,
  WebhookDelivery,
  WebhookTestResult,
  PaginatedWebhookDeadLetters,
  WebhookPayload } from '@/types/webhooks';

export const webhookService = {
  // Webhook CRUD operations
  async listWebhooks(): Promise<WebhookResponse[]> {
    const response = await apiClient.get('/api/v1/webhooks');
    return response.data;
  },

  async getWebhook(id: string): Promise<WebhookResponse> {
    const response = await apiClient.get(`/api/v1/webhooks/${id}`);
    return response.data;
  },

  async createWebhook(data: WebhookCreate): Promise<WebhookResponse> {
    const response = await apiClient.post('/api/v1/webhooks', data);
    return response.data;
  },

  async updateWebhook(id: string, data: WebhookUpdate): Promise<WebhookResponse> {
    const response = await apiClient.put(`/api/v1/webhooks/${id}`, data);
    return response.data;
  },

  async deleteWebhook(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/webhooks/${id}`);
  },

  // Webhook testing
  async testWebhook(id: string): Promise<WebhookTestResult> {
    const response = await apiClient.post(`/api/v1/webhooks/${id}/test`);
    return response.data;
  },

  async sendTestWebhook(id: string, payload: WebhookPayload): Promise<WebhookTestResult> {
    const response = await apiClient.post(`/api/v1/webhooks/${id}/test`, payload);
    return response.data;
  },

  // Webhook deliveries
  async getWebhookDeliveries(webhookId: string, limit: number = 100): Promise<WebhookDelivery[]> {
    const response = await apiClient.get(`/api/v1/webhooks/${webhookId}/deliveries`, {
      params: { limit } });
    return response.data;
  },

  // Dead letter queue
  async getDeadLetters(params: { limit?: number; offset?: number } = {}): Promise<PaginatedWebhookDeadLetters> {
    const response = await apiClient.get('/api/v1/webhooks/dead-letters', { params });
    
    // Transform the array response into paginated format
    const items = response.data || [];
    return {
      items,
      total: items.length, // This would ideally come from the backend
      page: Math.floor((params.offset || 0) / (params.limit || 100)) + 1,
      per_page: params.limit || 100 };
  },

  async reprocessDeadLetter(id: string): Promise<void> {
    await apiClient.post(`/api/v1/webhooks/dead-letters/${id}/reprocess`);
  },

  async deleteDeadLetter(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/webhooks/dead-letters/${id}`);
  },

  // Webhook documentation
  async getWebhookEvents(): Promise<any> {
    const response = await apiClient.get('/api/v1/webhooks/docs/events');
    return response.data;
  },

  async getSignatureVerificationDocs(): Promise<any> {
    const response = await apiClient.get('/api/v1/webhooks/docs/signature');
    return response.data;
  } };
