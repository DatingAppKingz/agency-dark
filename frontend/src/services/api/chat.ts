import apiClient from './client';
import { 
  Conversation, 
  Message, 
  SendMessageData,
  ChatStats 
} from '@/types/chat';
import { QueryParams } from '@/types/api';
import { logger } from '@/utils/logger';

export const chatApi = {
  // Note: Backend uses orchestration endpoints for messaging
  // These methods integrate with available backend endpoints
  
  // Get messages for a model
  async getMessages(modelId: string, fanId?: string, params?: QueryParams): Promise<Message[]> {
    const { data } = await apiClient.get(`/orchestration/messages/${modelId}`, {
      params: {
        fan_id: fanId,
        limit: params?.size || 50,
        offset: ((params?.page || 1) - 1) * (params?.size || 50) }
    });
    return data || [];
  },

  // Send a message
  async sendMessage(data: SendMessageData): Promise<Message> {
    const { data: response } = await apiClient.post('/orchestration/messages/send', {
      fan_id: data.fan_id,
      text: data.text,
      media_urls: data.media_urls || [],
      price: data.price }, {
      params: { model_id: data.model_id }
    });
    
    // Transform response to match Message type
    return {
      id: response.message_id || Date.now().toString(),
      conversation_id: data.conversation_id,
      sender_id: data.sender_id || 'current_user',
      created_at: new Date().toISOString(),
      ...response
    } as Message;
  },

  // Send mass message
  async sendMassMessage(modelId: string, fanIds: string[], text: string, campaignName?: string): Promise<any> {
    const { data } = await apiClient.post('/orchestration/messages/mass-send', {
      fan_ids: fanIds,
      text: text,
      campaign_name: campaignName,
      send_to_all: false }, {
      params: { model_id: modelId }
    });
    return data;
  },

  // Get fans (as conversations)
  async getConversations(modelId: string, params?: QueryParams): Promise<Conversation[]> {
    const { data } = await apiClient.get(`/orchestration/fans/${modelId}`, {
      params: {
        limit: params?.size || 100,
        offset: ((params?.page || 1) - 1) * (params?.size || 100),
        include_unclaimed: true }
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
  async getConversation(_event: string): Promise<Conversation> {
    logger.warn('Single conversation endpoint not available, use getConversations');
    throw new Error('Not implemented');
  },

  async createConversation(fanId: string, modelId: string): Promise<Conversation> {
    // Conversations are created automatically when sending first message
    return {
      id: `${modelId}-${fanId}`,
      model_id: modelId,
      fan_id: fanId,
      created_at: new Date().toISOString() } as Conversation;
  },

  async archiveConversation(_conversationId: string): Promise<void> {
    logger.warn('Archive functionality not available in backend');
  },

  async pinConversation(_conversationId: string, _isPinned: boolean): Promise<void> {
    logger.warn('Pin functionality not available in backend');
  },

  async assignChatter(_conversationId: string, _chatterId: string): Promise<void> {
    logger.warn('Chatter assignment managed through orchestration');
  },

  async updateConversation(conversationId: string, data: Partial<Conversation>): Promise<Conversation> {
    logger.warn('Conversation update not available in backend');
    return { id: conversationId, ...data } as Conversation;
  },

  async markAsRead(_conversationId: string, _messageIds?: string[]): Promise<void> { 
    logger.warn('Mark as read not available in backend');
  },

  async deleteMessage(_conversationId: string, _messageId: string): Promise<void> {
    logger.warn('Message deletion not available in backend');
  },

  async sendTypingStatus(_conversationId: string, isTyping: boolean): Promise<void> {
    // This would be handled by Socket.IO in real-time
    logger.info('Typing status:', isTyping);
  },

  async getChatStats(): Promise<ChatStats> {
    logger.warn('Chat stats not directly available, use analytics endpoints');
    return {
      total_conversations: 0,
      active_chats: 0,
      unread_messages: 0,
      avg_response_time: 0 };
  },

  async searchConversations(_searchTerm: string): Promise<Conversation[]> {
    logger.warn('Search not implemented in backend');
    return [];
  },

  async getCannedResponses(): Promise<Array<{ id: string; title: string; content: string }>> {
    logger.warn('Canned responses not available from backend');
    return [];
  },

  async createCannedResponse(_title: string, _content: string): Promise<void> {
    logger.warn('Canned response creation not available in backend');
  },

  async blockUser(_conversationId: string, _userId: string): Promise<void> {
    logger.warn('User blocking not implemented in backend');
  },

  async reportUser(_conversationId: string, _userId: string, _reason: string): Promise<void> {
    logger.warn('User reporting not implemented in backend');
  } };
