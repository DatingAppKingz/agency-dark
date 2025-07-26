import apiClient from './client';
import { 
  Conversation, 
  Message, 
  SendMessageData,
  ChatStats 
} from '@/types/chat';
import { PaginatedResponse, QueryParams } from '@/types/api';

export const chatApi = {
  // Note: Backend uses orchestration endpoints for messaging
  // These methods integrate with available backend endpoints
  
  // Get messages for a model
  async getMessages(modelId: string, fanId?: string, params?: QueryParams): Promise<Message[]> {
    const { data } = await apiClient.get(`/orchestration/messages/${modelId}`, {
      params: {
        fan_id: fanId,
        limit: params?.limit || 50,
        offset: params?.offset || 0,
      }
    });
    return data || [];
  },

  // Send a message
  async sendMessage(data: SendMessageData): Promise<Message> {
    const { data: response } = await apiClient.post('/orchestration/messages/send', {
      fan_id: data.fan_id,
      text: data.content,
      media_urls: data.media_urls || [],
      price: data.price,
    }, {
      params: { model_id: data.model_id }
    });
    
    // Transform response to match Message type
    return {
      id: response.message_id || Date.now().toString(),
      conversation_id: data.conversation_id,
      content: data.content,
      sender_id: 'current_user',
      created_at: new Date().toISOString(),
      ...response
    } as Message;
  },

  // Send mass message
  async sendMassMessage(modelId: string, fanIds: string[], content: string, campaignName?: string): Promise<any> {
    const { data } = await apiClient.post('/orchestration/messages/mass-send', {
      fan_ids: fanIds,
      text: content,
      campaign_name: campaignName,
      send_to_all: false,
    }, {
      params: { model_id: modelId }
    });
    return data;
  },

  // Get fans (as conversations)
  async getConversations(modelId: string, params?: QueryParams): Promise<Conversation[]> {
    const { data } = await apiClient.get(`/orchestration/fans/${modelId}`, {
      params: {
        limit: params?.limit || 100,
        offset: params?.offset || 0,
        include_unclaimed: true,
      }
    });
    
    // Transform fans to conversations
    return (data || []).map((fan: any) => ({
      id: fan.id,
      model_id: modelId,
      fan_id: fan.id,
      fan_name: fan.username || fan.name,
      fan_avatar: fan.avatar_url,
      last_message: fan.last_message,
      last_message_at: fan.last_message_date,
      unread_count: fan.unread_messages || 0,
      is_pinned: false,
      is_archived: false,
      assigned_to: fan.assigned_chatter_id,
      ...fan
    }));
  },

  // Placeholder methods for features not directly available in backend
  async getConversation(conversationId: string): Promise<Conversation> {
    console.warn('Single conversation endpoint not available, use getConversations');
    throw new Error('Not implemented');
  },

  async createConversation(fanId: string, modelId: string): Promise<Conversation> {
    // Conversations are created automatically when sending first message
    return {
      id: `${modelId}-${fanId}`,
      model_id: modelId,
      fan_id: fanId,
      created_at: new Date().toISOString(),
    } as Conversation;
  },

  async archiveConversation(conversationId: string): Promise<void> {
    console.warn('Archive functionality not available in backend');
  },

  async pinConversation(conversationId: string, isPinned: boolean): Promise<void> {
    console.warn('Pin functionality not available in backend');
  },

  async assignChatter(conversationId: string, chatterId: string): Promise<void> {
    console.warn('Chatter assignment managed through orchestration');
  },

  async updateConversation(conversationId: string, data: Partial<Conversation>): Promise<Conversation> {
    console.warn('Conversation update not available in backend');
    return { id: conversationId, ...data } as Conversation;
  },

  async markAsRead(conversationId: string, messageIds?: string[]): Promise<void> {
    console.warn('Mark as read not available in backend');
  },

  async deleteMessage(conversationId: string, messageId: string): Promise<void> {
    console.warn('Message deletion not available in backend');
  },

  async sendTypingStatus(conversationId: string, isTyping: boolean): Promise<void> {
    // This would be handled by Socket.IO in real-time
    console.log('Typing status:', isTyping);
  },

  async getChatStats(): Promise<ChatStats> {
    console.warn('Chat stats not directly available, use analytics endpoints');
    return {
      total_conversations: 0,
      active_conversations: 0,
      unread_messages: 0,
      response_time_avg: 0,
    } as ChatStats;
  },

  async searchConversations(query: string): Promise<Conversation[]> {
    console.warn('Search not implemented in backend');
    return [];
  },

  async getCannedResponses(): Promise<Array<{ id: string; title: string; content: string }>> {
    console.warn('Canned responses not available from backend');
    return [];
  },

  async createCannedResponse(title: string, content: string): Promise<void> {
    console.warn('Canned response creation not available in backend');
  },

  async blockUser(userId: string, reason: string): Promise<void> {
    console.warn('User blocking not implemented in backend');
  },

  async reportUser(userId: string, reason: string, details: string): Promise<void> {
    console.warn('User reporting not implemented in backend');
  },
};