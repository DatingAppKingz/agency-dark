import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { chatApi } from '@/services/api/chat';
import apiClient from '@/services/api/client';
import { logger } from '@/utils/logger';

// Mock dependencies
vi.mock('@/services/api/client');
vi.mock('@/utils/logger');

const mockedApiClient = apiClient as any;
const mockedLogger = logger as any;

describe('Chat API Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getMessages', () => {
    it('should fetch messages for a model', async () => {
      const modelId = 'model123';
      const fanId = 'fan456';
      const mockMessages = [
        {
          id: 'msg1',
          conversation_id: 'conv1',
          sender_id: 'fan456',
          text: 'Hello there!',
          created_at: '2025-01-31T10:00:00Z'
        },
        {
          id: 'msg2',
          conversation_id: 'conv1',
          sender_id: 'model123',
          text: 'Hi! How can I help you?',
          created_at: '2025-01-31T10:01:00Z'
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockMessages });

      const result = await chatApi.getMessages(modelId, fanId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/messages/${modelId}`,
        {
          params: {
            fan_id: fanId,
            limit: 50,
            offset: 0
          }
        }
      );
      expect(result).toEqual(mockMessages);
    });

    it('should handle pagination params', async () => {
      const modelId = 'model123';
      const params = { page: 2, size: 20 };
      
      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await chatApi.getMessages(modelId, undefined, params);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/messages/${modelId}`,
        {
          params: {
            fan_id: undefined,
            limit: 20,
            offset: 20 // (page 2 - 1) * size 20
          }
        }
      );
    });

    it('should return empty array when no data', async () => {
      mockedApiClient.get.mockResolvedValueOnce({ data: null });

      const result = await chatApi.getMessages('model123');

      expect(result).toEqual([]);
    });

    it('should handle API errors', async () => {
      const error = new Error('API Error');
      mockedApiClient.get.mockRejectedValueOnce(error);

      await expect(chatApi.getMessages('model123')).rejects.toThrow('API Error');
    });
  });

  describe('sendMessage', () => {
    it('should send a message successfully', async () => {
      const messageData = {
        model_id: 'model123',
        fan_id: 'fan456',
        conversation_id: 'conv1',
        sender_id: 'model123',
        text: 'Thanks for your support!',
        media_urls: ['https://example.com/image.jpg'],
        price: 10
      };

      const mockResponse = {
        message_id: 'msg123',
        status: 'sent'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await chatApi.sendMessage(messageData);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/messages/send',
        {
          fan_id: messageData.fan_id,
          text: messageData.text,
          media_urls: messageData.media_urls,
          price: messageData.price
        },
        {
          params: { model_id: messageData.model_id }
        }
      );

      expect(result).toMatchObject({
        id: 'msg123',
        conversation_id: messageData.conversation_id,
        sender_id: messageData.sender_id,
        status: 'sent'
      });
    });

    it('should handle messages without media or price', async () => {
      const messageData = {
        model_id: 'model123',
        fan_id: 'fan456',
        conversation_id: 'conv1',
        text: 'Simple message'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await chatApi.sendMessage(messageData);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/messages/send',
        {
          fan_id: messageData.fan_id,
          text: messageData.text,
          media_urls: [],
          price: undefined
        },
        {
          params: { model_id: messageData.model_id }
        }
      );
    });

    it('should generate ID if not returned', async () => {
      const messageData = {
        model_id: 'model123',
        fan_id: 'fan456',
        conversation_id: 'conv1',
        text: 'Test message'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      const result = await chatApi.sendMessage(messageData);

      expect(result.id).toBeDefined();
      expect(result.created_at).toBeDefined();
    });
  });

  describe('sendMassMessage', () => {
    it('should send mass message to multiple fans', async () => {
      const modelId = 'model123';
      const fanIds = ['fan1', 'fan2', 'fan3'];
      const text = 'Special announcement!';
      const campaignName = 'Holiday Sale';

      const mockResponse = {
        campaign_id: 'campaign123',
        messages_sent: 3,
        status: 'completed'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await chatApi.sendMassMessage(modelId, fanIds, text, campaignName);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/messages/mass-send',
        {
          fan_ids: fanIds,
          text: text,
          campaign_name: campaignName,
          send_to_all: false
        },
        {
          params: { model_id: modelId }
        }
      );

      expect(result).toEqual(mockResponse);
    });

    it('should handle mass message without campaign name', async () => {
      const modelId = 'model123';
      const fanIds = ['fan1', 'fan2'];
      const text = 'Quick update';

      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await chatApi.sendMassMessage(modelId, fanIds, text);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/orchestration/messages/mass-send',
        {
          fan_ids: fanIds,
          text: text,
          campaign_name: undefined,
          send_to_all: false
        },
        {
          params: { model_id: modelId }
        }
      );
    });
  });

  describe('getConversations', () => {
    it('should fetch and transform fans to conversations', async () => {
      const modelId = 'model123';
      const mockFans = [
        {
          id: 'fan1',
          username: 'superfan123',
          name: 'Super Fan',
          avatar_url: 'https://example.com/avatar1.jpg',
          last_message: 'Thanks!',
          last_message_date: '2025-01-31T10:00:00Z',
          unread_messages: 3,
          assigned_chatter_id: 'chatter1'
        },
        {
          id: 'fan2',
          username: 'loyalfan456',
          avatar_url: 'https://example.com/avatar2.jpg',
          last_message: 'Love your content',
          last_message_date: '2025-01-31T09:00:00Z',
          unread_messages: 0
        }
      ];

      mockedApiClient.get.mockResolvedValueOnce({ data: mockFans });

      const result = await chatApi.getConversations(modelId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/fans/${modelId}`,
        {
          params: {
            limit: 100,
            offset: 0,
            include_unclaimed: true
          }
        }
      );

      expect(result).toHaveLength(2);
      expect(result[0]).toMatchObject({
        id: 'fan1',
        model_id: modelId,
        fan_id: 'fan1',
        fan_name: 'superfan123',
        fan_avatar: 'https://example.com/avatar1.jpg',
        last_message: 'Thanks!',
        last_message_at: '2025-01-31T10:00:00Z',
        unread_count: 3,
        is_pinned: false,
        is_archived: false,
        assigned_to: 'chatter1'
      });
    });

    it('should handle pagination in conversations', async () => {
      const modelId = 'model123';
      const params = { page: 3, size: 25 };

      mockedApiClient.get.mockResolvedValueOnce({ data: [] });

      await chatApi.getConversations(modelId, params);

      expect(mockedApiClient.get).toHaveBeenCalledWith(
        `/orchestration/fans/${modelId}`,
        {
          params: {
            limit: 25,
            offset: 50, // (page 3 - 1) * size 25
            include_unclaimed: true
          }
        }
      );
    });

    it('should handle empty fan list', async () => {
      mockedApiClient.get.mockResolvedValueOnce({ data: null });

      const result = await chatApi.getConversations('model123');

      expect(result).toEqual([]);
    });
  });

  describe('createConversation', () => {
    it('should create a placeholder conversation', async () => {
      const fanId = 'fan123';
      const modelId = 'model456';

      const result = await chatApi.createConversation(fanId, modelId);

      expect(result).toMatchObject({
        id: `${modelId}-${fanId}`,
        model_id: modelId,
        fan_id: fanId
      });
      expect(result.created_at).toBeDefined();
    });
  });

  describe('not implemented methods', () => {
    it('should log warning and throw for getConversation', async () => {
      await expect(chatApi.getConversation('event123')).rejects.toThrow('Not implemented');
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Single conversation endpoint not available, use getConversations'
      );
    });

    it('should log warning for archiveConversation', async () => {
      await chatApi.archiveConversation('conv123');
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Archive functionality not available in backend'
      );
    });

    it('should log warning for pinConversation', async () => {
      await chatApi.pinConversation('conv123', true);
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Pin functionality not available in backend'
      );
    });

    it('should log warning for assignChatter', async () => {
      await chatApi.assignChatter('conv123', 'chatter456');
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Chatter assignment managed through orchestration'
      );
    });

    it('should return partial update for updateConversation', async () => {
      const conversationId = 'conv123';
      const updateData = { is_pinned: true, notes: 'VIP customer' };

      const result = await chatApi.updateConversation(conversationId, updateData);

      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Conversation update not available in backend'
      );
      expect(result).toMatchObject({
        id: conversationId,
        ...updateData
      });
    });

    it('should log warning for markAsRead', async () => {
      await chatApi.markAsRead('conv123', ['msg1', 'msg2']);
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Mark as read not available in backend'
      );
    });

    it('should log warning for deleteMessage', async () => {
      await chatApi.deleteMessage('conv123', 'msg456');
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Message deletion not available in backend'
      );
    });

    it('should log info for sendTypingStatus', async () => {
      await chatApi.sendTypingStatus('conv123', true);
      expect(mockedLogger.info).toHaveBeenCalledWith('Typing status:', true);
    });

    it('should return empty stats for getChatStats', async () => {
      const result = await chatApi.getChatStats();

      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Chat stats not directly available, use analytics endpoints'
      );
      expect(result).toEqual({
        total_conversations: 0,
        active_chats: 0,
        unread_messages: 0,
        avg_response_time: 0
      });
    });

    it('should return empty array for searchConversations', async () => {
      const result = await chatApi.searchConversations('search term');

      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Search not implemented in backend'
      );
      expect(result).toEqual([]);
    });

    it('should return empty array for getCannedResponses', async () => {
      const result = await chatApi.getCannedResponses();

      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Canned responses not available from backend'
      );
      expect(result).toEqual([]);
    });

    it('should log warning for createCannedResponse', async () => {
      await chatApi.createCannedResponse('Greeting', 'Hello there!');
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'Canned response creation not available in backend'
      );
    });

    it('should log warning for blockUser', async () => {
      await chatApi.blockUser('conv123', 'user456');
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'User blocking not implemented in backend'
      );
    });

    it('should log warning for reportUser', async () => {
      await chatApi.reportUser('conv123', 'user456', 'Spam');
      expect(mockedLogger.warn).toHaveBeenCalledWith(
        'User reporting not implemented in backend'
      );
    });
  });

  describe('error handling', () => {
    it('should propagate network errors', async () => {
      const networkError = new Error('Network failure');
      mockedApiClient.get.mockRejectedValueOnce(networkError);

      await expect(chatApi.getMessages('model123')).rejects.toThrow('Network failure');
    });

    it('should handle API response errors', async () => {
      const apiError = {
        response: {
          status: 403,
          data: { message: 'Forbidden' }
        }
      };
      mockedApiClient.post.mockRejectedValueOnce(apiError);

      await expect(chatApi.sendMessage({
        model_id: 'model123',
        fan_id: 'fan456',
        text: 'Test'
      })).rejects.toMatchObject(apiError);
    });
  });
});