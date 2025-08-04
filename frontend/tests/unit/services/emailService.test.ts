import { describe, it, expect, vi, beforeEach } from 'vitest';
import { emailService } from '@/services/email/emailService';
import { apiClient as api } from '@/services/api';
import {
  EmailTemplate,
  EmailRecipient,
  EmailStatus,
  EmailCampaign,
  EmailSchedule,
} from '@/types/email';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('EmailService', () => {
  const mockTemplate: EmailTemplate = {
    id: 'template-1',
    name: 'Welcome Email',
    subject: 'Welcome to {{agency_name}}',
    body_html: '<h1>Welcome {{model_name}}!</h1>',
    body_text: 'Welcome {{model_name}}!',
    variables: ['agency_name', 'model_name'],
    category: 'onboarding',
    is_active: true,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockRecipient: EmailRecipient = {
    email: 'model@example.com',
    name: 'Test Model',
    type: 'model',
    model_id: 'model-1',
    variables: {
      model_name: 'Test Model',
      agency_name: 'Test Agency',
    },
  };

  const mockCampaign: EmailCampaign = {
    id: 'campaign-1',
    name: 'Welcome Campaign',
    template_id: 'template-1',
    status: 'active',
    audience_type: 'all_models',
    filters: {},
    scheduled_at: null,
    sent_count: 0,
    open_count: 0,
    click_count: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Email Sending', () => {
    it('should send a single email', async () => {
      const emailData = {
        to: 'recipient@example.com',
        subject: 'Test Email',
        body_html: '<p>Test content</p>',
        body_text: 'Test content',
      };
      const mockResponse = {
        data: {
          id: 'email-1',
          status: EmailStatus.SENT,
          sent_at: '2024-01-01T00:00:00Z',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.sendEmail(emailData);

      expect(api.post).toHaveBeenCalledWith('/email/send', emailData);
      expect(result).toEqual(mockResponse.data);
    });

    it('should send email using template', async () => {
      const emailData = {
        to: 'recipient@example.com',
        template_id: 'template-1',
        variables: {
          model_name: 'Test Model',
          agency_name: 'Test Agency',
        },
      };
      const mockResponse = {
        data: {
          id: 'email-2',
          status: EmailStatus.SENT,
          sent_at: '2024-01-01T00:00:00Z',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.sendTemplateEmail(emailData);

      expect(api.post).toHaveBeenCalledWith('/email/send-template', emailData);
      expect(result).toEqual(mockResponse.data);
    });

    it('should send bulk emails', async () => {
      const bulkData = {
        template_id: 'template-1',
        recipients: [mockRecipient],
      };
      const mockResponse = {
        data: {
          batch_id: 'batch-1',
          total: 1,
          queued: 1,
          failed: 0,
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.sendBulkEmail(bulkData);

      expect(api.post).toHaveBeenCalledWith('/email/send-bulk', bulkData);
      expect(result).toEqual(mockResponse.data);
    });

    it('should schedule an email', async () => {
      const scheduleData = {
        to: 'recipient@example.com',
        subject: 'Scheduled Email',
        body_html: '<p>Scheduled content</p>',
        scheduled_for: '2024-01-02T10:00:00Z',
      };
      const mockResponse = {
        data: {
          id: 'schedule-1',
          status: EmailStatus.SCHEDULED,
          scheduled_for: '2024-01-02T10:00:00Z',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.scheduleEmail(scheduleData);

      expect(api.post).toHaveBeenCalledWith('/email/schedule', scheduleData);
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Template Management', () => {
    it('should get email templates', async () => {
      const mockResponse = {
        data: {
          items: [mockTemplate],
          total: 1,
          page: 1,
          size: 20,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await emailService.getTemplates({
        page: 1,
        size: 20,
        category: 'onboarding',
      });

      expect(api.get).toHaveBeenCalledWith('/email/templates', {
        params: { page: 1, size: 20, category: 'onboarding' },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should create an email template', async () => {
      const newTemplate = {
        name: 'New Template',
        subject: 'New Subject',
        body_html: '<p>New content</p>',
        body_text: 'New content',
        category: 'marketing',
      };
      const mockResponse = { data: { ...mockTemplate, ...newTemplate } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.createTemplate(newTemplate);

      expect(api.post).toHaveBeenCalledWith('/email/templates', newTemplate);
      expect(result).toEqual(mockResponse.data);
    });

    it('should update an email template', async () => {
      const updates = { subject: 'Updated Subject' };
      const mockResponse = { data: { ...mockTemplate, ...updates } };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await emailService.updateTemplate('template-1', updates);

      expect(api.put).toHaveBeenCalledWith('/email/templates/template-1', updates);
      expect(result).toEqual(mockResponse.data);
    });

    it('should delete an email template', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.delete).mockResolvedValue(mockResponse);

      const result = await emailService.deleteTemplate('template-1');

      expect(api.delete).toHaveBeenCalledWith('/email/templates/template-1');
      expect(result).toEqual(mockResponse.data);
    });

    it('should preview email template', async () => {
      const previewData = {
        template_id: 'template-1',
        variables: {
          model_name: 'Preview Model',
          agency_name: 'Preview Agency',
        },
      };
      const mockResponse = {
        data: {
          subject: 'Welcome to Preview Agency',
          body_html: '<h1>Welcome Preview Model!</h1>',
          body_text: 'Welcome Preview Model!',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.previewTemplate(previewData);

      expect(api.post).toHaveBeenCalledWith('/email/templates/preview', previewData);
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Campaign Management', () => {
    it('should get email campaigns', async () => {
      const mockResponse = {
        data: {
          items: [mockCampaign],
          total: 1,
          page: 1,
          size: 20,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await emailService.getCampaigns({
        page: 1,
        size: 20,
        status: 'active',
      });

      expect(api.get).toHaveBeenCalledWith('/email/campaigns', {
        params: { page: 1, size: 20, status: 'active' },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should create an email campaign', async () => {
      const newCampaign = {
        name: 'New Campaign',
        template_id: 'template-1',
        audience_type: 'all_models' as const,
      };
      const mockResponse = { data: { ...mockCampaign, ...newCampaign } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.createCampaign(newCampaign);

      expect(api.post).toHaveBeenCalledWith('/email/campaigns', newCampaign);
      expect(result).toEqual(mockResponse.data);
    });

    it('should launch a campaign', async () => {
      const mockResponse = {
        data: {
          ...mockCampaign,
          status: 'launched',
          launched_at: '2024-01-01T10:00:00Z',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.launchCampaign('campaign-1');

      expect(api.post).toHaveBeenCalledWith('/email/campaigns/campaign-1/launch');
      expect(result).toEqual(mockResponse.data);
    });

    it('should pause a campaign', async () => {
      const mockResponse = {
        data: {
          ...mockCampaign,
          status: 'paused',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.pauseCampaign('campaign-1');

      expect(api.post).toHaveBeenCalledWith('/email/campaigns/campaign-1/pause');
      expect(result).toEqual(mockResponse.data);
    });

    it('should get campaign analytics', async () => {
      const mockAnalytics = {
        sent_count: 100,
        delivered_count: 98,
        open_count: 45,
        click_count: 20,
        bounce_count: 2,
        unsubscribe_count: 1,
        open_rate: 0.45,
        click_rate: 0.2,
        bounce_rate: 0.02,
      };
      const mockResponse = { data: mockAnalytics };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await emailService.getCampaignAnalytics('campaign-1');

      expect(api.get).toHaveBeenCalledWith('/email/campaigns/campaign-1/analytics');
      expect(result).toEqual(mockAnalytics);
    });
  });

  describe('Email Tracking', () => {
    it('should get email status', async () => {
      const mockStatus = {
        id: 'email-1',
        status: EmailStatus.DELIVERED,
        sent_at: '2024-01-01T00:00:00Z',
        delivered_at: '2024-01-01T00:01:00Z',
        opened_at: '2024-01-01T00:05:00Z',
        clicks: [],
      };
      const mockResponse = { data: mockStatus };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await emailService.getEmailStatus('email-1');

      expect(api.get).toHaveBeenCalledWith('/email/status/email-1');
      expect(result).toEqual(mockStatus);
    });

    it('should get email history', async () => {
      const mockHistory = [
        {
          id: 'email-1',
          recipient: 'model@example.com',
          subject: 'Welcome Email',
          status: EmailStatus.DELIVERED,
          sent_at: '2024-01-01T00:00:00Z',
        },
      ];
      const mockResponse = {
        data: {
          items: mockHistory,
          total: 1,
          page: 1,
          size: 20,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await emailService.getEmailHistory({
        model_id: 'model-1',
        page: 1,
        size: 20,
      });

      expect(api.get).toHaveBeenCalledWith('/email/history', {
        params: { model_id: 'model-1', page: 1, size: 20 },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should track email open', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.trackOpen('email-1');

      expect(api.post).toHaveBeenCalledWith('/email/track/open', {
        email_id: 'email-1',
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should track email click', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.trackClick('email-1', 'https://example.com');

      expect(api.post).toHaveBeenCalledWith('/email/track/click', {
        email_id: 'email-1',
        url: 'https://example.com',
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Subscription Management', () => {
    it('should get subscription preferences', async () => {
      const mockPreferences = {
        model_id: 'model-1',
        marketing: true,
        notifications: true,
        weekly_digest: false,
        monthly_report: true,
      };
      const mockResponse = { data: mockPreferences };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await emailService.getSubscriptionPreferences('model-1');

      expect(api.get).toHaveBeenCalledWith('/email/subscriptions/model-1');
      expect(result).toEqual(mockPreferences);
    });

    it('should update subscription preferences', async () => {
      const updates = { marketing: false, weekly_digest: true };
      const mockResponse = {
        data: {
          model_id: 'model-1',
          marketing: false,
          notifications: true,
          weekly_digest: true,
          monthly_report: true,
        },
      };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await emailService.updateSubscriptionPreferences('model-1', updates);

      expect(api.put).toHaveBeenCalledWith('/email/subscriptions/model-1', updates);
      expect(result).toEqual(mockResponse.data);
    });

    it('should handle unsubscribe', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.unsubscribe('model-1', 'marketing');

      expect(api.post).toHaveBeenCalledWith('/email/unsubscribe', {
        model_id: 'model-1',
        category: 'marketing',
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Email Automation', () => {
    it('should create automated email flow', async () => {
      const flowData = {
        name: 'Onboarding Flow',
        trigger: 'model_signup',
        steps: [
          {
            template_id: 'template-1',
            delay_hours: 0,
          },
          {
            template_id: 'template-2',
            delay_hours: 24,
          },
        ],
      };
      const mockResponse = {
        data: {
          id: 'flow-1',
          ...flowData,
          is_active: true,
          created_at: '2024-01-01T00:00:00Z',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.createAutomatedFlow(flowData);

      expect(api.post).toHaveBeenCalledWith('/email/automations', flowData);
      expect(result).toEqual(mockResponse.data);
    });

    it('should trigger automated email', async () => {
      const triggerData = {
        flow_id: 'flow-1',
        model_id: 'model-1',
        variables: {
          model_name: 'Test Model',
        },
      };
      const mockResponse = {
        data: {
          automation_id: 'automation-1',
          status: 'triggered',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await emailService.triggerAutomatedEmail(triggerData);

      expect(api.post).toHaveBeenCalledWith('/email/automations/trigger', triggerData);
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Error Handling', () => {
    it('should handle email sending failure', async () => {
      const error = {
        response: {
          status: 400,
          data: {
            error_code: 'INVALID_RECIPIENT',
            message: 'Invalid email address',
          },
        },
      };
      vi.mocked(api.post).mockRejectedValue(error);

      await expect(
        emailService.sendEmail({
          to: 'invalid-email',
          subject: 'Test',
          body_html: '<p>Test</p>',
        })
      ).rejects.toMatchObject(error);
    });

    it('should handle template not found error', async () => {
      const error = {
        response: {
          status: 404,
          data: {
            error_code: 'TEMPLATE_NOT_FOUND',
            message: 'Email template not found',
          },
        },
      };
      vi.mocked(api.get).mockRejectedValue(error);

      await expect(emailService.getTemplate('invalid-id')).rejects.toMatchObject(error);
    });

    it('should handle rate limit error', async () => {
      const error = {
        response: {
          status: 429,
          data: {
            error_code: 'RATE_LIMIT_EXCEEDED',
            message: 'Too many requests',
            retry_after: 60,
          },
        },
      };
      vi.mocked(api.post).mockRejectedValue(error);

      await expect(
        emailService.sendBulkEmail({
          template_id: 'template-1',
          recipients: [mockRecipient],
        })
      ).rejects.toMatchObject(error);
    });
  });
});