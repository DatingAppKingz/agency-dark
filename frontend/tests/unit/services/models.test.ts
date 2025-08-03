import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { modelsService } from '@/services/api/models';
import apiClient from '@/services/api/client';
import { logger } from '@/utils/logger';

// Mock dependencies
vi.mock('@/services/api/client');
vi.mock('@/utils/logger');

const mockedApiClient = apiClient as any;
const mockedLogger = logger as any;

describe('Models Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('getModel', () => {
    it('should fetch model status via orchestration', async () => {
      const modelId = 'model123';
      const mockModelData = {
        id: modelId,
        status: 'active',
        sync_status: 'completed',
        last_sync: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockModelData });

      const result = await modelsService.getModel(modelId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/sync/${modelId}/status`
      );
      expect(result).toEqual(mockModelData);
    });

    it('should handle API errors', async () => {
      const error = new Error('API Error');
      mockedApiClient.get.mockRejectedValueOnce(error);

      await expect(modelsService.getModel('model123')).rejects.toThrow('API Error');
    });
  });

  describe('getModelAnalytics', () => {
    it('should fetch model analytics for date range', async () => {
      const modelId = 'model123';
      const startDate = '2025-01-01';
      const endDate = '2025-01-31';
      const mockAnalytics = {
        total_earnings: 5000,
        total_messages: 150,
        total_fans: 50,
        conversion_rate: 0.15
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockAnalytics });

      const result = await modelsService.getModelAnalytics(modelId, startDate, endDate);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/analytics/${modelId}`,
        {
          params: { start_date: startDate, end_date: endDate }
        }
      );
      expect(result).toEqual(mockAnalytics);
    });
  });

  describe('getModelFans', () => {
    it('should fetch model fans with pagination', async () => {
      const modelId = 'model123';
      const params = { limit: 20, offset: 40 };
      const mockFans = [
        { id: 'fan1', username: 'fan1', total_spent: 100 },
        { id: 'fan2', username: 'fan2', total_spent: 200 }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockFans });

      const result = await modelsService.getModelFans(modelId, params);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/fans/${modelId}`,
        { params }
      );
      expect(result).toEqual(mockFans);
    });

    it('should fetch fans without params', async () => {
      const modelId = 'model123';
      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await modelsService.getModelFans(modelId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/fans/${modelId}`,
        { params: undefined }
      );
    });
  });

  describe('syncModelData', () => {
    it('should trigger sync for both platforms by default', async () => {
      const modelId = 'model123';
      const mockResponse = {
        task_id: 'sync123',
        status: 'started',
        platforms: ['inflow', 'onlyfans']
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await modelsService.syncModelData(modelId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        `/orchestration/sync/${modelId}`,
        null,
        {
          params: { sync_inflow: true, sync_onlyfans: true }
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should allow selective platform sync', async () => {
      const modelId = 'model123';
      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await modelsService.syncModelData(modelId, false, true);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        `/orchestration/sync/${modelId}`,
        null,
        {
          params: { sync_inflow: false, sync_onlyfans: true }
        }
      );
    });
  });

  describe('getSyncStatus', () => {
    it('should fetch sync status', async () => {
      const modelId = 'model123';
      const mockStatus = {
        inflow: { status: 'completed', last_sync: '2025-01-31T10:00:00Z' },
        onlyfans: { status: 'in_progress', last_sync: '2025-01-31T09:00:00Z' }
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockStatus });

      const result = await modelsService.getSyncStatus(modelId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/sync/${modelId}/status`
      );
      expect(result).toEqual(mockStatus);
    });
  });

  describe('getModels', () => {
    it('should fetch models list', async () => {
      const params = { page: 1, size: 20 };
      const mockModels = {
        items: [
          { id: 'model1', name: 'Model 1' },
          { id: 'model2', name: 'Model 2' }
        ],
        total: 2
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockModels });

      const result = await modelsService.getModels(params);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        '/api/v1/users/models',
        { params }
      );
      expect(result).toEqual(mockModels);
    });
  });

  describe('uploadContent', () => {
    it('should upload content via orchestration', async () => {
      const modelId = 'model123';
      const file = new File(['content'], 'image.jpg', { type: 'image/jpeg' });
      const metadata = {
        title: 'New post',
        is_free: false
      };
      const mockResponse = {
        content_id: 'content123',
        status: 'posted'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await modelsService.uploadContent(modelId, file, metadata);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/content/post',
        {
          model_id: modelId,
          text: metadata.title,
          media_urls: [],
          is_free: metadata.is_free,
          publish_immediately: true,
          post_to_onlyfans: true,
          post_to_inflow: true
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should handle default metadata values', async () => {
      const modelId = 'model123';
      const file = new File(['content'], 'image.jpg');
      
      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await modelsService.uploadContent(modelId, file, {});

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/content/post',
        expect.objectContaining({
          text: '',
          is_free: false
        })
      );
    });
  });

  describe('getModelMessages', () => {
    it('should fetch model messages with params', async () => {
      const modelId = 'model123';
      const fanId = 'fan456';
      const limit = 100;
      const offset = 50;
      const mockMessages = [
        { id: 'msg1', text: 'Hello' },
        { id: 'msg2', text: 'How are you?' }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockMessages });

      const result = await modelsService.getModelMessages(modelId, fanId, limit, offset);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/messages/${modelId}`,
        {
          params: { fan_id: fanId, limit, offset }
        }
      );
      expect(result).toEqual(mockMessages);
    });

    it('should use default values when params not provided', async () => {
      const modelId = 'model123';
      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await modelsService.getModelMessages(modelId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/messages/${modelId}`,
        {
          params: { fan_id: undefined, limit: 50, offset: 0 }
        }
      );
    });
  });

  describe('sendMessage', () => {
    it('should send message with price', async () => {
      const modelId = 'model123';
      const fanId = 'fan456';
      const text = 'Special content!';
      const price = 25;
      const mockResponse = {
        message_id: 'msg123',
        status: 'sent'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await modelsService.sendMessage(modelId, fanId, text, price);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/messages/send',
        {
          fan_id: fanId,
          text,
          price
        },
        {
          params: { model_id: modelId }
        }
      );
      expect(result).toEqual(mockResponse);
    });

    it('should send message without price', async () => {
      const modelId = 'model123';
      const fanId = 'fan456';
      const text = 'Regular message';
      
      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await modelsService.sendMessage(modelId, fanId, text);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/messages/send',
        {
          fan_id: fanId,
          text,
          price: undefined
        },
        {
          params: { model_id: modelId }
        }
      );
    });
  });

  describe('getStats', () => {
    it('should calculate stats for day period', async () => {
      const modelId = 'model123';
      const mockAnalytics = { earnings: 100, messages: 10 };
      
      vi.setSystemTime(new Date('2025-01-31T12:00:00Z'));
      mockedApiClient.get.mockResolvedValueOnce({ data: mockAnalytics });

      const result = await modelsService.getStats(modelId, 'day');

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/analytics/${modelId}`,
        {
          params: {
            start_date: '2025-01-30',
            end_date: '2025-01-31'
          }
        }
      );
      expect(result).toEqual(mockAnalytics);
    });

    it('should calculate stats for week period', async () => {
      const modelId = 'model123';
      vi.setSystemTime(new Date('2025-01-31T12:00:00Z'));
      mockedApiClient.get.mockResolvedValueOnce({ data: {} });

      await modelsService.getStats(modelId, 'week');

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/analytics/${modelId}`,
        {
          params: {
            start_date: '2025-01-24',
            end_date: '2025-01-31'
          }
        }
      );
    });

    it('should calculate stats for month period by default', async () => {
      const modelId = 'model123';
      vi.setSystemTime(new Date('2025-01-31T12:00:00Z'));
      mockedApiClient.get.mockResolvedValueOnce({ data: {} });

      await modelsService.getStats(modelId, 'month');

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/analytics/${modelId}`,
        {
          params: {
            start_date: '2024-12-31',
            end_date: '2025-01-31'
          }
        }
      );
    });
  });

  describe('not implemented methods', () => {
    it('should throw error for createModel', async () => {
      await expect(modelsService.createModel({} as any)).rejects.toThrow(
        'Model creation not yet implemented in backend'
      );
    });

    it('should throw error for updateModel', async () => {
      await expect(modelsService.updateModel('model123', {})).rejects.toThrow(
        'Model update not yet implemented in backend'
      );
    });

    it('should throw error for deleteModel', async () => {
      await expect(modelsService.deleteModel('model123')).rejects.toThrow(
        'Model deletion not yet implemented in backend'
      );
    });

    it('should throw error for deleteContent', async () => {
      await expect(modelsService.deleteContent('model123', 'content456')).rejects.toThrow(
        'Content deletion not yet implemented'
      );
    });

    it('should throw error for toggleModelStatus', async () => {
      await expect(modelsService.toggleModelStatus('model123', true)).rejects.toThrow(
        'Status toggle not implemented in backend'
      );
    });

    it('should throw error for uploadAvatar', async () => {
      const file = new File([''], 'avatar.jpg');
      await expect(modelsService.uploadAvatar('model123', file)).rejects.toThrow(
        'Avatar upload not implemented in backend'
      );
    });

    it('should throw error for uploadCover', async () => {
      const file = new File([''], 'cover.jpg');
      await expect(modelsService.uploadCover('model123', file)).rejects.toThrow(
        'Cover upload not implemented in backend'
      );
    });

    it('should log warning and return empty array for getModelContent', async () => {
      const result = await modelsService.getModelContent('model123');
      
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Content management through orchestration API'
      );
      expect(result).toEqual([]);
    });

    it('should log warning and return empty array for getAvailability', async () => {
      const result = await modelsService.getAvailability('model123');
      
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Availability not implemented in backend'
      );
      expect(result).toEqual([]);
    });

    it('should log warning and return input for updateAvailability', async () => {
      const availability = [{ day: 'Monday', start: '09:00', end: '17:00' }];
      const result = await modelsService.updateAvailability('model123', availability);
      
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Availability update not implemented in backend'
      );
      expect(result).toEqual(availability);
    });

    it('should log warning and return empty object for getPreferences', async () => {
      const result = await modelsService.getPreferences('model123');
      
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Preferences not implemented in backend'
      );
      expect(result).toEqual({});
    });

    it('should log warning and return input for updatePreferences', async () => {
      const preferences = { autoReply: true, greeting: 'Hello!' };
      const result = await modelsService.updatePreferences('model123', preferences);
      
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Preferences update not implemented in backend'
      );
      expect(result).toEqual(preferences);
    });
  });

  describe('error handling', () => {
    it('should propagate network errors', async () => {
      const networkError = new Error('Network failure');
      mockedApiClient.get.mockRejectedValueOnce(networkError);

      await expect(modelsService.getModel('model123')).rejects.toThrow('Network failure');
    });

    it('should handle API response errors', async () => {
      const apiError = {
        response: {
          status: 404,
          data: { message: 'Model not found' }
        }
      };
      mockedApiClient.get.mockRejectedValueOnce(apiError);

      await expect(modelsService.getModelAnalytics('model123', '2025-01-01', '2025-01-31'))
        .rejects.toMatchObject(apiError);
    });
  });
});