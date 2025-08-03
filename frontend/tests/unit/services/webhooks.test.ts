import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { webhookService } from '@/services/api/webhooks';
import apiClient from '@/services/api/client';
import {
  WebhookCreate,
  WebhookUpdate,
  WebhookResponse,
  WebhookTestResult,
  WebhookPayload
} from '@/types/webhooks';

// Mock dependencies
vi.mock('@/services/api/client');
const mockedApiClient = apiClient as any;

describe('Webhook Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('listWebhooks', () => {
    it('should fetch all webhooks', async () => {
      const mockWebhooks: WebhookResponse[] = [
        {
          id: 'webhook1',
          url: 'https://example.com/webhook1',
          events: ['user.created', 'user.updated'],
          is_active: true,
          created_at: '2025-01-31T10:00:00Z',
          updated_at: '2025-01-31T10:00:00Z',
          secret_key: 'secret123',
          description: 'User events webhook'
        },
        {
          id: 'webhook2',
          url: 'https://example.com/webhook2',
          events: ['payment.completed'],
          is_active: false,
          created_at: '2025-01-31T11:00:00Z',
          updated_at: '2025-01-31T11:00:00Z',
          secret_key: 'secret456',
          description: 'Payment webhook'
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockWebhooks });

      const result = await webhookService.listWebhooks();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/webhooks');
      expect(result).toEqual(mockWebhooks);
    });

    it('should handle empty webhook list', async () => {
      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      const result = await webhookService.listWebhooks();

      expect(result).toEqual([]);
    });
  });

  describe('getWebhook', () => {
    it('should fetch a specific webhook', async () => {
      const webhookId = 'webhook123';
      const mockWebhook: WebhookResponse = {
        id: webhookId,
        url: 'https://example.com/webhook',
        events: ['model.earnings.updated', 'model.payout.created'],
        is_active: true,
        created_at: '2025-01-31T10:00:00Z',
        updated_at: '2025-01-31T15:00:00Z',
        secret_key: 'webhook-secret-key',
        description: 'Model financial events',
        headers: { 'X-Custom-Header': 'value' },
        retry_config: {
          max_retries: 3,
          retry_delay: 60
        }
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockWebhook });

      const result = await webhookService.getWebhook(webhookId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(`/api/v1/webhooks/${webhookId}`);
      expect(result).toEqual(mockWebhook);
    });
  });

  describe('createWebhook', () => {
    it('should create a new webhook', async () => {
      const createData: WebhookCreate = {
        url: 'https://api.example.com/notifications',
        events: ['user.created', 'user.deleted', 'payment.completed'],
        is_active: true,
        description: 'Main notification webhook',
        headers: {
          'Authorization': 'Bearer token123',
          'Content-Type': 'application/json'
        }
      };

      const mockCreatedWebhook: WebhookResponse = {
        id: 'webhook-new',
        ...createData,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        secret_key: 'generated-secret-key'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockCreatedWebhook });

      const result = await webhookService.createWebhook(createData);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/webhooks', createData);
      expect(result).toEqual(mockCreatedWebhook);
      expect(result.secret_key).toBeDefined();
    });

    it('should create webhook with minimal data', async () => {
      const createData: WebhookCreate = {
        url: 'https://minimal.example.com/hook',
        events: ['test.event']
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: { id: 'webhook-min', ...createData } });

      await webhookService.createWebhook(createData);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/webhooks', createData);
    });
  });

  describe('updateWebhook', () => {
    it('should update webhook configuration', async () => {
      const webhookId = 'webhook123';
      const updateData: WebhookUpdate = {
        url: 'https://updated.example.com/webhook',
        events: ['user.created', 'user.updated', 'user.deleted'],
        is_active: false,
        description: 'Updated webhook description'
      };

      const mockUpdatedWebhook: WebhookResponse = {
        id: webhookId,
        ...updateData,
        created_at: '2025-01-31T10:00:00Z',
        updated_at: new Date().toISOString(),
        secret_key: 'existing-secret'
      };

      mockedApiClient.put.mockResolvedValueOnce({ data: mockUpdatedWebhook });

      const result = await webhookService.updateWebhook(webhookId, updateData);

      expect(mockedApiClient.put).toHaveBeenCalledWith(`/api/v1/webhooks/${webhookId}`, updateData);
      expect(result).toEqual(mockUpdatedWebhook);
    });

    it('should update single webhook field', async () => {
      const webhookId = 'webhook123';
      const updateData: WebhookUpdate = {
        is_active: true
      };

      mockedApiClient.put.mockResolvedValueOnce({ data: {} });

      await webhookService.updateWebhook(webhookId, updateData);

      expect(mockedApiClient.put).toHaveBeenCalledWith(
        `/api/v1/webhooks/${webhookId}`,
        { is_active: true }
      );
    });
  });

  describe('deleteWebhook', () => {
    it('should delete a webhook', async () => {
      const webhookId = 'webhook123';
      mockedApiClient.delete.mockResolvedValueOnce({});

      await webhookService.deleteWebhook(webhookId);

      expect(mockedApiClient.delete).toHaveBeenCalledWith(`/api/v1/webhooks/${webhookId}`);
    });
  });

  describe('testWebhook', () => {
    it('should test webhook with default payload', async () => {
      const webhookId = 'webhook123';
      const mockTestResult: WebhookTestResult = {
        success: true,
        status_code: 200,
        response_time_ms: 150,
        response_body: '{"status": "received"}',
        headers_sent: {
          'Content-Type': 'application/json',
          'X-Webhook-Signature': 'test-signature'
        }
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockTestResult });

      const result = await webhookService.testWebhook(webhookId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(`/api/v1/webhooks/${webhookId}/test`);
      expect(result).toEqual(mockTestResult);
      expect(result.success).toBe(true);
    });

    it('should handle failed webhook test', async () => {
      const webhookId = 'webhook123';
      const mockTestResult: WebhookTestResult = {
        success: false,
        status_code: 500,
        response_time_ms: 5000,
        error: 'Connection timeout',
        response_body: null
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockTestResult });

      const result = await webhookService.testWebhook(webhookId);

      expect(result.success).toBe(false);
      expect(result.error).toBeDefined();
    });
  });

  describe('sendTestWebhook', () => {
    it('should send test webhook with custom payload', async () => {
      const webhookId = 'webhook123';
      const payload: WebhookPayload = {
        event: 'test.custom',
        data: {
          test_id: 'test123',
          message: 'Custom test payload',
          timestamp: new Date().toISOString()
        }
      };

      const mockTestResult: WebhookTestResult = {
        success: true,
        status_code: 200,
        response_time_ms: 100,
        response_body: '{"received": true}'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockTestResult });

      const result = await webhookService.sendTestWebhook(webhookId, payload);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        `/api/v1/webhooks/${webhookId}/test`,
        payload
      );
      expect(result).toEqual(mockTestResult);
    });
  });

  describe('getWebhookDeliveries', () => {
    it('should fetch webhook delivery history', async () => {
      const webhookId = 'webhook123';
      const mockDeliveries = [
        {
          id: 'delivery1',
          webhook_id: webhookId,
          event: 'user.created',
          status: 'success',
          status_code: 200,
          response_time_ms: 120,
          attempted_at: '2025-01-31T15:00:00Z',
          payload: { user_id: 'user123' }
        },
        {
          id: 'delivery2',
          webhook_id: webhookId,
          event: 'payment.completed',
          status: 'failed',
          status_code: 500,
          response_time_ms: 5000,
          attempted_at: '2025-01-31T14:00:00Z',
          error: 'Internal server error',
          retry_count: 3
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockDeliveries });

      const result = await webhookService.getWebhookDeliveries(webhookId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/api/v1/webhooks/${webhookId}/deliveries`,
        { params: { limit: 100 } }
      );
      expect(result).toEqual(mockDeliveries);
    });

    it('should fetch deliveries with custom limit', async () => {
      const webhookId = 'webhook123';
      const limit = 50;

      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await webhookService.getWebhookDeliveries(webhookId, limit);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/api/v1/webhooks/${webhookId}/deliveries`,
        { params: { limit } }
      );
    });
  });

  describe('getDeadLetters', () => {
    it('should fetch dead letter queue items', async () => {
      const mockDeadLetters = [
        {
          id: 'dl1',
          webhook_id: 'webhook123',
          event: 'user.created',
          payload: { user_id: 'user456' },
          error: 'Max retries exceeded',
          failed_at: '2025-01-31T16:00:00Z',
          retry_count: 5
        },
        {
          id: 'dl2',
          webhook_id: 'webhook456',
          event: 'payment.failed',
          payload: { payment_id: 'pay789' },
          error: 'Webhook URL not reachable',
          failed_at: '2025-01-31T17:00:00Z',
          retry_count: 3
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockDeadLetters });

      const result = await webhookService.getDeadLetters();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/webhooks/dead-letters', {
        params: {}
      });
      expect(result.items).toEqual(mockDeadLetters);
      expect(result.total).toBe(2);
      expect(result.page).toBe(1);
      expect(result.per_page).toBe(100);
    });

    it('should handle pagination params', async () => {
      const params = { limit: 20, offset: 40 };
      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      const result = await webhookService.getDeadLetters(params);

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/webhooks/dead-letters', {
        params
      });
      expect(result.page).toBe(3); // offset 40 / limit 20 + 1
      expect(result.per_page).toBe(20);
    });
  });

  describe('reprocessDeadLetter', () => {
    it('should reprocess a dead letter', async () => {
      const deadLetterId = 'dl123';
      mockedApiClient.post.mockResolvedValueOnce({});

      await webhookService.reprocessDeadLetter(deadLetterId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        `/api/v1/webhooks/dead-letters/${deadLetterId}/reprocess`
      );
    });
  });

  describe('deleteDeadLetter', () => {
    it('should delete a dead letter', async () => {
      const deadLetterId = 'dl123';
      mockedApiClient.delete.mockResolvedValueOnce({});

      await webhookService.deleteDeadLetter(deadLetterId);

      expect(mockedApiClient.delete).toHaveBeenCalledWith(
        `/api/v1/webhooks/dead-letters/${deadLetterId}`
      );
    });
  });

  describe('getWebhookEvents', () => {
    it('should fetch webhook events documentation', async () => {
      const mockEvents = {
        events: [
          {
            name: 'user.created',
            description: 'Triggered when a new user is created',
            payload_schema: {
              user_id: 'string',
              email: 'string',
              created_at: 'datetime'
            }
          },
          {
            name: 'payment.completed',
            description: 'Triggered when a payment is completed',
            payload_schema: {
              payment_id: 'string',
              amount: 'number',
              currency: 'string'
            }
          }
        ]
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockEvents });

      const result = await webhookService.getWebhookEvents();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/webhooks/docs/events');
      expect(result).toEqual(mockEvents);
    });
  });

  describe('getSignatureVerificationDocs', () => {
    it('should fetch signature verification documentation', async () => {
      const mockDocs = {
        algorithm: 'HMAC-SHA256',
        header_name: 'X-Webhook-Signature',
        example_code: {
          python: 'import hmac\nimport hashlib\n...',
          javascript: 'const crypto = require("crypto");\n...'
        },
        description: 'How to verify webhook signatures'
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockDocs });

      const result = await webhookService.getSignatureVerificationDocs();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/webhooks/docs/signature');
      expect(result).toEqual(mockDocs);
    });
  });

  describe('error handling', () => {
    it('should propagate network errors', async () => {
      const networkError = new Error('Network failure');
      mockedApiClient.get.mockRejectedValueOnce(networkError);

      await expect(webhookService.listWebhooks()).rejects.toThrow('Network failure');
    });

    it('should handle validation errors', async () => {
      const validationError = {
        response: {
          status: 400,
          data: { message: 'Invalid webhook URL' }
        }
      };
      mockedApiClient.post.mockRejectedValueOnce(validationError);

      await expect(webhookService.createWebhook({
        url: 'invalid-url',
        events: []
      })).rejects.toMatchObject(validationError);
    });

    it('should handle authorization errors', async () => {
      const authError = {
        response: {
          status: 403,
          data: { message: 'Insufficient permissions to manage webhooks' }
        }
      };
      mockedApiClient.delete.mockRejectedValueOnce(authError);

      await expect(webhookService.deleteWebhook('webhook123')).rejects.toMatchObject(authError);
    });
  });
});