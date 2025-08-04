import { describe, it, expect, vi, beforeEach } from 'vitest';
import { modelService } from '@/services/models/modelService';
import api from '@/services/api';
import { ModelProfile, ModelStatus } from '@/types/models';

vi.mock('@/services/api');

describe('ModelService', () => {
  const mockModel: ModelProfile = {
    id: '1',
    user_id: 'user-1',
    stage_name: 'TestModel',
    email: 'model@example.com',
    status: ModelStatus.ACTIVE,
    commission_rate: 20,
    payout_frequency: 'weekly',
    payout_method: 'bank_transfer',
    biography: 'Test bio',
    profile_image: 'https://example.com/image.jpg',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    total_earnings: 1000,
    total_fans: 100,
    active_subscriptions: 50,
    last_active: '2024-01-01T00:00:00Z',
    onboarding_completed: true,
    documents_verified: true,
    metadata: {},
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('CRUD Operations', () => {
    it('should get all models', async () => {
      const mockResponse = {
        data: {
          items: [mockModel],
          total: 1,
          page: 1,
          size: 20,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.getModels({ page: 1, size: 20 });

      expect(api.get).toHaveBeenCalledWith('/models', {
        params: { page: 1, size: 20, skip: 0 },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should get a single model', async () => {
      const mockResponse = { data: mockModel };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.getModel('1');

      expect(api.get).toHaveBeenCalledWith('/models/1');
      expect(result).toEqual(mockModel);
    });

    it('should create a new model', async () => {
      const newModel = {
        stage_name: 'NewModel',
        email: 'new@example.com',
        commission_rate: 25,
      };
      const mockResponse = { data: { ...mockModel, ...newModel } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await modelService.createModel(newModel);

      expect(api.post).toHaveBeenCalledWith('/models', newModel);
      expect(result).toEqual(mockResponse.data);
    });

    it('should update a model', async () => {
      const updates = { stage_name: 'UpdatedModel' };
      const mockResponse = { data: { ...mockModel, ...updates } };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await modelService.updateModel('1', updates);

      expect(api.put).toHaveBeenCalledWith('/models/1', updates);
      expect(result).toEqual(mockResponse.data);
    });

    it('should delete a model', async () => {
      const mockResponse = { data: { message: 'Model deleted' } };
      vi.mocked(api.delete).mockResolvedValue(mockResponse);

      const result = await modelService.deleteModel('1');

      expect(api.delete).toHaveBeenCalledWith('/models/1');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Status Management', () => {
    it('should toggle model status', async () => {
      const mockResponse = { data: { ...mockModel, status: ModelStatus.INACTIVE } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await modelService.toggleModelStatus('1', false);

      expect(api.post).toHaveBeenCalledWith('/models/1/toggle-status', {
        is_active: false,
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should suspend a model', async () => {
      const mockResponse = { data: { ...mockModel, status: ModelStatus.SUSPENDED } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await modelService.suspendModel('1', 'Violation of terms');

      expect(api.post).toHaveBeenCalledWith('/models/1/suspend', {
        reason: 'Violation of terms',
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should reactivate a model', async () => {
      const mockResponse = { data: { ...mockModel, status: ModelStatus.ACTIVE } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await modelService.reactivateModel('1');

      expect(api.post).toHaveBeenCalledWith('/models/1/reactivate');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Document Management', () => {
    it('should upload model documents', async () => {
      const file = new File(['content'], 'document.pdf', { type: 'application/pdf' });
      const mockResponse = { data: { id: 'doc-1', url: 'https://example.com/doc.pdf' } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await modelService.uploadDocument('1', file, 'id_verification');

      expect(api.post).toHaveBeenCalledWith(
        '/models/1/documents',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      );
      expect(result).toEqual(mockResponse.data);
    });

    it('should get model documents', async () => {
      const mockDocuments = [
        { id: 'doc-1', type: 'id_verification', status: 'approved' },
      ];
      const mockResponse = { data: mockDocuments };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.getDocuments('1');

      expect(api.get).toHaveBeenCalledWith('/models/1/documents');
      expect(result).toEqual(mockDocuments);
    });

    it('should verify model documents', async () => {
      const mockResponse = { data: { verified: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await modelService.verifyDocuments('1', true, 'All documents verified');

      expect(api.post).toHaveBeenCalledWith('/models/1/documents/verify', {
        approved: true,
        notes: 'All documents verified',
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Analytics', () => {
    it('should get model analytics', async () => {
      const mockAnalytics = {
        earnings: { total: 1000, this_month: 500 },
        fans: { total: 100, new_this_month: 20 },
        content: { total_posts: 50, total_messages: 200 },
      };
      const mockResponse = { data: mockAnalytics };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.getModelAnalytics('1', {
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      });

      expect(api.get).toHaveBeenCalledWith('/models/1/analytics', {
        params: { start_date: '2024-01-01', end_date: '2024-01-31' },
      });
      expect(result).toEqual(mockAnalytics);
    });

    it('should get model performance metrics', async () => {
      const mockMetrics = {
        engagement_rate: 0.75,
        response_time_avg: 2.5,
        content_frequency: 10,
      };
      const mockResponse = { data: mockMetrics };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.getModelPerformance('1');

      expect(api.get).toHaveBeenCalledWith('/models/1/performance');
      expect(result).toEqual(mockMetrics);
    });
  });

  describe('Financial Operations', () => {
    it('should update commission rate', async () => {
      const mockResponse = { data: { ...mockModel, commission_rate: 30 } };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await modelService.updateCommissionRate('1', 30);

      expect(api.put).toHaveBeenCalledWith('/models/1/commission', {
        rate: 30,
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should update payout settings', async () => {
      const payoutSettings = {
        frequency: 'monthly',
        method: 'paypal',
        details: { email: 'payout@example.com' },
      };
      const mockResponse = { data: { ...mockModel, ...payoutSettings } };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await modelService.updatePayoutSettings('1', payoutSettings);

      expect(api.put).toHaveBeenCalledWith('/models/1/payout-settings', payoutSettings);
      expect(result).toEqual(mockResponse.data);
    });

    it('should get model earnings', async () => {
      const mockEarnings = {
        total: 1000,
        pending: 200,
        paid: 800,
        transactions: [],
      };
      const mockResponse = { data: mockEarnings };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.getModelEarnings('1', {
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      });

      expect(api.get).toHaveBeenCalledWith('/models/1/earnings', {
        params: { start_date: '2024-01-01', end_date: '2024-01-31' },
      });
      expect(result).toEqual(mockEarnings);
    });
  });

  describe('Bulk Operations', () => {
    it('should perform bulk status update', async () => {
      const modelIds = ['1', '2', '3'];
      const mockResponse = { data: { updated: 3 } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await modelService.bulkUpdateStatus(modelIds, ModelStatus.INACTIVE);

      expect(api.post).toHaveBeenCalledWith('/models/bulk/status', {
        model_ids: modelIds,
        status: ModelStatus.INACTIVE,
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should export models data', async () => {
      const mockResponse = { data: new Blob(['csv data']) };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.exportModels('csv', {
        status: ModelStatus.ACTIVE,
      });

      expect(api.get).toHaveBeenCalledWith('/models/export', {
        params: { format: 'csv', status: ModelStatus.ACTIVE },
        responseType: 'blob',
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Search and Filtering', () => {
    it('should search models', async () => {
      const mockResponse = {
        data: {
          items: [mockModel],
          total: 1,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.searchModels('TestModel');

      expect(api.get).toHaveBeenCalledWith('/models/search', {
        params: { q: 'TestModel' },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should filter models by multiple criteria', async () => {
      const filters = {
        status: ModelStatus.ACTIVE,
        min_earnings: 1000,
        max_earnings: 5000,
        has_documents: true,
      };
      const mockResponse = {
        data: {
          items: [mockModel],
          total: 1,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await modelService.getModels({ ...filters, page: 1, size: 20 });

      expect(api.get).toHaveBeenCalledWith('/models', {
        params: {
          ...filters,
          page: 1,
          size: 20,
          skip: 0,
        },
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      const networkError = new Error('Network error');
      vi.mocked(api.get).mockRejectedValue(networkError);

      await expect(modelService.getModels()).rejects.toThrow('Network error');
    });

    it('should handle validation errors', async () => {
      const validationError = {
        response: {
          status: 422,
          data: {
            detail: [
              { field: 'email', message: 'Invalid email format' },
            ],
          },
        },
      };
      vi.mocked(api.post).mockRejectedValue(validationError);

      await expect(
        modelService.createModel({ stage_name: 'Test', email: 'invalid' })
      ).rejects.toMatchObject(validationError);
    });

    it('should handle authorization errors', async () => {
      const authError = {
        response: {
          status: 403,
          data: { detail: 'Insufficient permissions' },
        },
      };
      vi.mocked(api.delete).mockRejectedValue(authError);

      await expect(modelService.deleteModel('1')).rejects.toMatchObject(authError);
    });
  });
});