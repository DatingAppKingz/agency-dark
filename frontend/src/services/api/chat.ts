import apiClient from './client';
import { 
  Conversation, 
  Message, 
  SendMessageData,
  ChatStats 
} from '@/types/chat';
import { PaginatedResponse, QueryParams } from '@/types/api';

export const chatService = {
  // Conversations
  async getConversations(params?: QueryParams & { 
    status?: string; 
    assigned_to?: string; 
  }): Promise<PaginatedResponse<Conversation>> {
    const { data } = await apiClient.get('/chat/conversations', { params });
    return data;
  },

  async getConversation(conversationId: string): Promise<Conversation> {
    const { data } = await apiClient.get(`/chat/conversations/${conversationId}`);
    return data;
  },

  async createConversation(fanId: string, modelId: string): Promise<Conversation> {
    const { data } = await apiClient.post('/chat/conversations', {
      fan_id: fanId,
      model_id: modelId,
    });
    return data;
  },

  async archiveConversation(conversationId: string): Promise<void> {
    await apiClient.patch(`/chat/conversations/${conversationId}/archive`);
  },

  async pinConversation(conversationId: string, isPinned: boolean): Promise<void> {
    await apiClient.patch(`/chat/conversations/${conversationId}/pin`, { is_pinned: isPinned });
  },

  async assignChatter(conversationId: string, chatterId: string): Promise<void> {
    await apiClient.patch(`/chat/conversations/${conversationId}/assign`, {
      chatter_id: chatterId,
    });
  },

  // Messages
  async getMessages(conversationId: string, params?: QueryParams): Promise<PaginatedResponse<Message>> {
    const { data } = await apiClient.get(`/chat/conversations/${conversationId}/messages`, { params });
    return data;
  },

  async sendMessage(data: SendMessageData): Promise<Message> {
    const formData = new FormData();
    formData.append('content', data.content);
    
    if (data.attachments) {
      data.attachments.forEach((file, index) => {
        formData.append(`attachments`, file);
      });
    }

    const { data: message } = await apiClient.post(
      `/chat/conversations/${data.conversation_id}/messages`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    );
    return message;
  },

  async markAsRead(conversationId: string, messageIds: string[]): Promise<void> {
    await apiClient.post(`/chat/conversations/${conversationId}/read`, {
      message_ids: messageIds,
    });
  },

  async deleteMessage(conversationId: string, messageId: string): Promise<void> {
    await apiClient.delete(`/chat/conversations/${conversationId}/messages/${messageId}`);
  },

  // Typing indicators
  async sendTypingStatus(conversationId: string, isTyping: boolean): Promise<void> {
    await apiClient.post(`/chat/conversations/${conversationId}/typing`, { is_typing: isTyping });
  },

  // Stats
  async getChatStats(): Promise<ChatStats> {
    const { data } = await apiClient.get('/chat/stats');
    return data;
  },

  // Search
  async searchConversations(query: string): Promise<Conversation[]> {
    const { data } = await apiClient.get('/chat/search', { params: { q: query } });
    return data;
  },

  // Canned responses
  async getCannedResponses(): Promise<Array<{ id: string; title: string; content: string }>> {
    const { data } = await apiClient.get('/chat/canned-responses');
    return data;
  },

  async createCannedResponse(title: string, content: string): Promise<void> {
    await apiClient.post('/chat/canned-responses', { title, content });
  },
};