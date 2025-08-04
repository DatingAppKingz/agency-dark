import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { chatService } from '@/services/chat/chatService';
import { apiClient as api } from '@/services/api';
import { io } from 'socket.io-client';
import {
  Conversation,
  Message,
  MessageType,
  MessageStatus,
  MessageAttachment,
  ConversationParticipant,
  TypingStatus,
} from '@/types/chat';

vi.mock('@/services/api', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('socket.io-client', () => {
  const listeners: Record<string, Function[]> = {};
  return {
    io: vi.fn(() => ({
      on: vi.fn((event: string, handler: Function) => {
        if (!listeners[event]) {
          listeners[event] = [];
        }
        listeners[event].push(handler);
      }),
      emit: vi.fn(),
      disconnect: vi.fn(),
      connect: vi.fn(),
      connected: true,
      // Helper to trigger events in tests
      _trigger: (event: string, data: any) => {
        if (listeners[event]) {
          listeners[event].forEach(handler => handler(data));
        }
      },
    })),
  };
});

describe('ChatService', () => {
  const mockConversation: Conversation = {
    id: 'conv-1',
    participants: [
      {
        id: 'user-1',
        role: 'model',
        name: 'Test Model',
        avatar_url: 'https://example.com/avatar1.jpg',
        last_seen: '2024-01-01T00:00:00Z',
        is_online: true,
      },
      {
        id: 'user-2',
        role: 'fan',
        name: 'Test Fan',
        avatar_url: 'https://example.com/avatar2.jpg',
        last_seen: '2024-01-01T00:00:00Z',
        is_online: false,
      },
    ],
    last_message: {
      id: 'msg-last',
      content: 'Last message',
      sender_id: 'user-1',
      created_at: '2024-01-01T00:00:00Z',
    },
    unread_count: 0,
    is_pinned: false,
    is_muted: false,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockMessage: Message = {
    id: 'msg-1',
    conversation_id: 'conv-1',
    sender_id: 'user-1',
    sender_type: 'model',
    content: 'Hello there!',
    message_type: MessageType.TEXT,
    status: MessageStatus.SENT,
    is_automated: false,
    attachments: [],
    metadata: {},
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Ensure chat service disconnects any existing socket
    chatService.disconnectSocket();
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('Conversation Management', () => {
    it('should get conversations list', async () => {
      const mockResponse = {
        data: {
          items: [mockConversation],
          total: 1,
          page: 1,
          size: 20,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await chatService.getConversations({
        page: 1,
        size: 20,
        unread_only: false,
      });

      expect(api.get).toHaveBeenCalledWith('/chat/conversations', {
        params: { page: 1, size: 20, unread_only: false },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should get a single conversation', async () => {
      const mockResponse = { data: mockConversation };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await chatService.getConversation('conv-1');

      expect(api.get).toHaveBeenCalledWith('/chat/conversations/conv-1');
      expect(result).toEqual(mockConversation);
    });

    it('should create a new conversation', async () => {
      const newConversation = {
        participant_id: 'user-2',
        initial_message: 'Hello!',
      };
      const mockResponse = { data: mockConversation };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.createConversation(newConversation);

      expect(api.post).toHaveBeenCalledWith('/chat/conversations', newConversation);
      expect(result).toEqual(mockConversation);
    });

    it('should archive a conversation', async () => {
      const mockResponse = { data: { ...mockConversation, is_archived: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.archiveConversation('conv-1');

      expect(api.post).toHaveBeenCalledWith('/chat/conversations/conv-1/archive');
      expect(result.is_archived).toBe(true);
    });

    it('should pin/unpin a conversation', async () => {
      const mockResponse = { data: { ...mockConversation, is_pinned: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.togglePin('conv-1', true);

      expect(api.post).toHaveBeenCalledWith('/chat/conversations/conv-1/pin', {
        is_pinned: true,
      });
      expect(result.is_pinned).toBe(true);
    });

    it('should mute/unmute a conversation', async () => {
      const mockResponse = { data: { ...mockConversation, is_muted: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.toggleMute('conv-1', true);

      expect(api.post).toHaveBeenCalledWith('/chat/conversations/conv-1/mute', {
        is_muted: true,
      });
      expect(result.is_muted).toBe(true);
    });

    it('should delete a conversation', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.delete).mockResolvedValue(mockResponse);

      const result = await chatService.deleteConversation('conv-1');

      expect(api.delete).toHaveBeenCalledWith('/chat/conversations/conv-1');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Message Management', () => {
    it('should get messages for a conversation', async () => {
      const mockResponse = {
        data: {
          items: [mockMessage],
          total: 1,
          page: 1,
          size: 50,
          has_more: false,
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await chatService.getMessages('conv-1', {
        page: 1,
        size: 50,
      });

      expect(api.get).toHaveBeenCalledWith('/chat/conversations/conv-1/messages', {
        params: { page: 1, size: 50 },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should send a text message', async () => {
      const newMessage = {
        content: 'New message',
        conversation_id: 'conv-1',
      };
      const mockResponse = { data: { ...mockMessage, ...newMessage } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.sendMessage(newMessage);

      expect(api.post).toHaveBeenCalledWith('/chat/messages', newMessage);
      expect(result).toEqual(mockResponse.data);
    });

    it('should send a message with attachments', async () => {
      const attachment: MessageAttachment = {
        id: 'attach-1',
        type: 'image',
        url: 'https://example.com/image.jpg',
        thumbnail_url: 'https://example.com/thumb.jpg',
        filename: 'image.jpg',
        size: 1024,
        mime_type: 'image/jpeg',
      };
      const newMessage = {
        content: 'Check this out!',
        conversation_id: 'conv-1',
        attachments: [attachment],
      };
      const mockResponse = {
        data: {
          ...mockMessage,
          content: newMessage.content,
          attachments: [attachment],
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.sendMessage(newMessage);

      expect(api.post).toHaveBeenCalledWith('/chat/messages', newMessage);
      expect(result.attachments).toHaveLength(1);
    });

    it('should edit a message', async () => {
      const updates = { content: 'Edited message' };
      const mockResponse = { data: { ...mockMessage, ...updates, is_edited: true } };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await chatService.editMessage('msg-1', updates.content);

      expect(api.put).toHaveBeenCalledWith('/chat/messages/msg-1', updates);
      expect(result.content).toBe('Edited message');
    });

    it('should delete a message', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.delete).mockResolvedValue(mockResponse);

      const result = await chatService.deleteMessage('msg-1');

      expect(api.delete).toHaveBeenCalledWith('/chat/messages/msg-1');
      expect(result).toEqual(mockResponse.data);
    });

    it('should mark messages as read', async () => {
      const mockResponse = { data: { updated: 5 } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.markAsRead('conv-1', ['msg-1', 'msg-2']);

      expect(api.post).toHaveBeenCalledWith('/chat/conversations/conv-1/read', {
        message_ids: ['msg-1', 'msg-2'],
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should react to a message', async () => {
      const mockResponse = {
        data: {
          message_id: 'msg-1',
          reaction: '❤️',
          count: 1,
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.addReaction('msg-1', '❤️');

      expect(api.post).toHaveBeenCalledWith('/chat/messages/msg-1/react', {
        reaction: '❤️',
      });
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Real-time Features', () => {
    it('should emit typing status', async () => {
      const socket = chatService.connectSocket();
      const emitSpy = vi.spyOn(socket, 'emit');

      chatService.sendTypingStatus('conv-1', true);

      expect(emitSpy).toHaveBeenCalledWith('typing', {
        conversation_id: 'conv-1',
        is_typing: true,
      });
    });

    it('should handle incoming messages', async () => {
      const socket = chatService.connectSocket() as any;
      const callback = vi.fn();
      
      chatService.onNewMessage(callback);
      
      // Simulate incoming message
      socket._trigger('new_message', mockMessage);

      expect(callback).toHaveBeenCalledWith(mockMessage);
    });

    it('should handle typing indicators', async () => {
      const socket = chatService.connectSocket() as any;
      const callback = vi.fn();
      
      chatService.onTypingStatus(callback);
      
      // Simulate typing status
      const typingStatus: TypingStatus = {
        user_id: 'user-2',
        conversation_id: 'conv-1',
        is_typing: true,
      };
      
      socket._trigger('typing_status', typingStatus);

      expect(callback).toHaveBeenCalledWith(typingStatus);
    });

    it('should handle message status updates', async () => {
      const socket = chatService.connectSocket() as any;
      const callback = vi.fn();
      
      chatService.onMessageStatusUpdate(callback);
      
      // Simulate status update
      const statusUpdate = {
        message_id: 'msg-1',
        status: MessageStatus.DELIVERED,
        delivered_at: '2024-01-01T00:01:00Z',
      };
      
      socket._trigger('message_status', statusUpdate);

      expect(callback).toHaveBeenCalledWith(statusUpdate);
    });
  });

  describe('File Upload', () => {
    it('should upload a file attachment', async () => {
      const file = new File(['content'], 'test.jpg', { type: 'image/jpeg' });
      const mockResponse = {
        data: {
          id: 'attach-1',
          url: 'https://example.com/uploads/test.jpg',
          thumbnail_url: 'https://example.com/uploads/thumb_test.jpg',
          filename: 'test.jpg',
          size: 1024,
          mime_type: 'image/jpeg',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.uploadAttachment('conv-1', file);

      expect(api.post).toHaveBeenCalledWith(
        '/chat/conversations/conv-1/attachments',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      );
      expect(result).toEqual(mockResponse.data);
    });

    it('should validate file size before upload', async () => {
      const largeFile = new File(['x'.repeat(11 * 1024 * 1024)], 'large.jpg', {
        type: 'image/jpeg',
      });

      await expect(
        chatService.uploadAttachment('conv-1', largeFile)
      ).rejects.toThrow('File size exceeds maximum allowed size');
    });

    it('should validate file type before upload', async () => {
      const invalidFile = new File(['content'], 'test.exe', {
        type: 'application/x-msdownload',
      });

      await expect(
        chatService.uploadAttachment('conv-1', invalidFile)
      ).rejects.toThrow('File type not allowed');
    });
  });

  describe('Search and Filtering', () => {
    it('should search messages', async () => {
      const mockResponse = {
        data: {
          items: [mockMessage],
          total: 1,
          highlights: {
            'msg-1': ['Hello <mark>there</mark>!'],
          },
        },
      };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await chatService.searchMessages({
        query: 'there',
        conversation_id: 'conv-1',
      });

      expect(api.get).toHaveBeenCalledWith('/chat/search', {
        params: { query: 'there', conversation_id: 'conv-1' },
      });
      expect(result).toEqual(mockResponse.data);
    });

    it('should get conversation statistics', async () => {
      const mockStats = {
        total_messages: 100,
        messages_today: 10,
        average_response_time: 300,
        media_count: 25,
        participants: 2,
      };
      const mockResponse = { data: mockStats };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await chatService.getConversationStats('conv-1');

      expect(api.get).toHaveBeenCalledWith('/chat/conversations/conv-1/stats');
      expect(result).toEqual(mockStats);
    });
  });

  describe('Moderation', () => {
    it('should report a message', async () => {
      const reportData = {
        reason: 'spam',
        details: 'Promotional content',
      };
      const mockResponse = {
        data: {
          report_id: 'report-1',
          status: 'pending',
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.reportMessage('msg-1', reportData);

      expect(api.post).toHaveBeenCalledWith('/chat/messages/msg-1/report', reportData);
      expect(result).toEqual(mockResponse.data);
    });

    it('should block a user', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.blockUser('user-2');

      expect(api.post).toHaveBeenCalledWith('/chat/users/user-2/block');
      expect(result).toEqual(mockResponse.data);
    });

    it('should unblock a user', async () => {
      const mockResponse = { data: { success: true } };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.unblockUser('user-2');

      expect(api.post).toHaveBeenCalledWith('/chat/users/user-2/unblock');
      expect(result).toEqual(mockResponse.data);
    });
  });

  describe('Automated Messages', () => {
    it('should create an automated message template', async () => {
      const template = {
        name: 'Welcome Message',
        content: 'Welcome to my page! How can I help you?',
        trigger: 'conversation_start',
      };
      const mockResponse = {
        data: {
          id: 'template-1',
          ...template,
          is_active: true,
        },
      };
      vi.mocked(api.post).mockResolvedValue(mockResponse);

      const result = await chatService.createAutomatedTemplate(template);

      expect(api.post).toHaveBeenCalledWith('/chat/automated-messages', template);
      expect(result).toEqual(mockResponse.data);
    });

    it('should get automated message templates', async () => {
      const mockTemplates = [
        {
          id: 'template-1',
          name: 'Welcome Message',
          content: 'Welcome!',
          trigger: 'conversation_start',
          is_active: true,
        },
      ];
      const mockResponse = { data: mockTemplates };
      vi.mocked(api.get).mockResolvedValue(mockResponse);

      const result = await chatService.getAutomatedTemplates();

      expect(api.get).toHaveBeenCalledWith('/chat/automated-messages');
      expect(result).toEqual(mockTemplates);
    });

    it('should toggle automated message', async () => {
      const mockResponse = {
        data: {
          id: 'template-1',
          is_active: false,
        },
      };
      vi.mocked(api.put).mockResolvedValue(mockResponse);

      const result = await chatService.toggleAutomatedTemplate('template-1', false);

      expect(api.put).toHaveBeenCalledWith('/chat/automated-messages/template-1', {
        is_active: false,
      });
      expect(result.is_active).toBe(false);
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      const networkError = new Error('Network error');
      vi.mocked(api.get).mockRejectedValue(networkError);

      await expect(chatService.getConversations()).rejects.toThrow('Network error');
    });

    it('should handle rate limiting', async () => {
      const rateLimitError = {
        response: {
          status: 429,
          data: {
            error_code: 'RATE_LIMIT_EXCEEDED',
            message: 'Too many requests',
            retry_after: 60,
          },
        },
      };
      vi.mocked(api.post).mockRejectedValue(rateLimitError);

      await expect(
        chatService.sendMessage({
          content: 'Test',
          conversation_id: 'conv-1',
        })
      ).rejects.toMatchObject(rateLimitError);
    });

    it('should handle unauthorized access', async () => {
      const authError = {
        response: {
          status: 403,
          data: {
            error_code: 'FORBIDDEN',
            message: 'You do not have permission to access this conversation',
          },
        },
      };
      vi.mocked(api.get).mockRejectedValue(authError);

      await expect(chatService.getConversation('conv-1')).rejects.toMatchObject(authError);
    });
  });
});