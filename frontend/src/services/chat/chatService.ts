import { apiClient as api } from '@/services/api';
import { io, Socket } from 'socket.io-client';
import {
  Conversation,
  Message,
  MessageType,
  MessageStatus,
  MessageAttachment,
  TypingStatus,
  SendMessageData,
} from '@/types/chat';

interface GetConversationsParams {
  page?: number;
  size?: number;
  unread_only?: boolean;
  search?: string;
  model_id?: string;
  fan_id?: string;
}

interface ConversationResponse {
  items: Conversation[];
  total: number;
  page: number;
  size: number;
}

interface GetMessagesParams {
  page?: number;
  size?: number;
  before?: string;
  after?: string;
}

interface MessageResponse {
  items: Message[];
  total: number;
  page: number;
  size: number;
  has_more: boolean;
}

interface CreateConversationData {
  participant_id: string;
  initial_message?: string;
}

interface SendMessagePayload {
  content: string;
  conversation_id: string;
  attachments?: MessageAttachment[];
  metadata?: Record<string, any>;
}

interface SearchMessagesParams {
  query: string;
  conversation_id?: string;
  start_date?: string;
  end_date?: string;
  sender_id?: string;
  page?: number;
  size?: number;
}

interface SearchMessagesResponse {
  items: Message[];
  total: number;
  highlights?: Record<string, string[]>;
}

interface ConversationStats {
  total_messages: number;
  messages_today: number;
  average_response_time: number;
  media_count: number;
  participants: number;
}

interface ReportMessageData {
  reason: string;
  details?: string;
}

interface AutomatedMessageTemplate {
  id?: string;
  name: string;
  content: string;
  trigger: string;
  conditions?: Record<string, any>;
  is_active?: boolean;
}

class ChatService {
  private socket: Socket | null = null;
  private socketUrl: string = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
  private messageCallbacks: ((message: Message) => void)[] = [];
  private typingCallbacks: ((status: TypingStatus) => void)[] = [];
  private statusCallbacks: ((update: any) => void)[] = [];

  // Socket Connection Management
  connectSocket(): Socket {
    if (!this.socket) {
      this.socket = io(this.socketUrl, {
        transports: ['websocket'],
        autoConnect: true,
      });

      this.socket.on('new_message', (message: Message) => {
        this.messageCallbacks.forEach(cb => cb(message));
      });

      this.socket.on('typing_status', (status: TypingStatus) => {
        this.typingCallbacks.forEach(cb => cb(status));
      });

      this.socket.on('message_status', (update: any) => {
        this.statusCallbacks.forEach(cb => cb(update));
      });
    }
    return this.socket;
  }

  disconnectSocket(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  // Real-time Event Handlers
  onNewMessage(callback: (message: Message) => void): () => void {
    this.messageCallbacks.push(callback);
    return () => {
      this.messageCallbacks = this.messageCallbacks.filter(cb => cb !== callback);
    };
  }

  onTypingStatus(callback: (status: TypingStatus) => void): () => void {
    this.typingCallbacks.push(callback);
    return () => {
      this.typingCallbacks = this.typingCallbacks.filter(cb => cb !== callback);
    };
  }

  onMessageStatusUpdate(callback: (update: any) => void): () => void {
    this.statusCallbacks.push(callback);
    return () => {
      this.statusCallbacks = this.statusCallbacks.filter(cb => cb !== callback);
    };
  }

  sendTypingStatus(conversationId: string, isTyping: boolean): void {
    if (this.socket) {
      this.socket.emit('typing', { conversation_id: conversationId, is_typing: isTyping });
    }
  }

  // Conversation Management
  async getConversations(params: GetConversationsParams = {}): Promise<ConversationResponse> {
    const response = await api.get<ConversationResponse>('/chat/conversations', { params });
    return response.data;
  }

  async getConversation(conversationId: string): Promise<Conversation> {
    const response = await api.get<Conversation>(`/chat/conversations/${conversationId}`);
    return response.data;
  }

  async createConversation(data: CreateConversationData): Promise<Conversation> {
    const response = await api.post<Conversation>('/chat/conversations', data);
    return response.data;
  }

  async archiveConversation(conversationId: string): Promise<Conversation> {
    const response = await api.post<Conversation>(`/chat/conversations/${conversationId}/archive`);
    return response.data;
  }

  async togglePin(conversationId: string, isPinned: boolean): Promise<Conversation> {
    const response = await api.post<Conversation>(`/chat/conversations/${conversationId}/pin`, {
      is_pinned: isPinned,
    });
    return response.data;
  }

  async toggleMute(conversationId: string, isMuted: boolean): Promise<Conversation> {
    const response = await api.post<Conversation>(`/chat/conversations/${conversationId}/mute`, {
      is_muted: isMuted,
    });
    return response.data;
  }

  async deleteConversation(conversationId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(`/chat/conversations/${conversationId}`);
    return response.data;
  }

  // Message Management
  async getMessages(conversationId: string, params: GetMessagesParams = {}): Promise<MessageResponse> {
    const response = await api.get<MessageResponse>(
      `/chat/conversations/${conversationId}/messages`,
      { params }
    );
    return response.data;
  }

  async sendMessage(data: SendMessagePayload): Promise<Message> {
    const response = await api.post<Message>('/chat/messages', data);
    return response.data;
  }

  async editMessage(messageId: string, content: string): Promise<Message> {
    const response = await api.put<Message>(`/chat/messages/${messageId}`, { content });
    return response.data;
  }

  async deleteMessage(messageId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(`/chat/messages/${messageId}`);
    return response.data;
  }

  async markAsRead(conversationId: string, messageIds: string[]): Promise<{ updated: number }> {
    const response = await api.post<{ updated: number }>(
      `/chat/conversations/${conversationId}/read`,
      { message_ids: messageIds }
    );
    return response.data;
  }

  async addReaction(messageId: string, reaction: string): Promise<any> {
    const response = await api.post(`/chat/messages/${messageId}/react`, { reaction });
    return response.data;
  }

  async removeReaction(messageId: string, reaction: string): Promise<any> {
    const response = await api.delete(`/chat/messages/${messageId}/react`, {
      data: { reaction },
    });
    return response.data;
  }

  // File Upload
  async uploadAttachment(conversationId: string, file: File): Promise<MessageAttachment> {
    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      throw new Error('File size exceeds maximum allowed size');
    }

    // Validate file type
    const allowedTypes = ['image/', 'video/', 'audio/', 'application/pdf'];
    const isAllowed = allowedTypes.some(type => file.type.startsWith(type));
    if (!isAllowed && !file.type.includes('document')) {
      throw new Error('File type not allowed');
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post<MessageAttachment>(
      `/chat/conversations/${conversationId}/attachments`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      }
    );
    return response.data;
  }

  // Search and Filtering
  async searchMessages(params: SearchMessagesParams): Promise<SearchMessagesResponse> {
    const response = await api.get<SearchMessagesResponse>('/chat/search', { params });
    return response.data;
  }

  async getConversationStats(conversationId: string): Promise<ConversationStats> {
    const response = await api.get<ConversationStats>(
      `/chat/conversations/${conversationId}/stats`
    );
    return response.data;
  }

  // Moderation
  async reportMessage(messageId: string, data: ReportMessageData): Promise<any> {
    const response = await api.post(`/chat/messages/${messageId}/report`, data);
    return response.data;
  }

  async blockUser(userId: string): Promise<{ success: boolean }> {
    const response = await api.post<{ success: boolean }>(`/chat/users/${userId}/block`);
    return response.data;
  }

  async unblockUser(userId: string): Promise<{ success: boolean }> {
    const response = await api.post<{ success: boolean }>(`/chat/users/${userId}/unblock`);
    return response.data;
  }

  async getBlockedUsers(): Promise<any[]> {
    const response = await api.get<any[]>('/chat/users/blocked');
    return response.data;
  }

  // Automated Messages
  async createAutomatedTemplate(template: AutomatedMessageTemplate): Promise<AutomatedMessageTemplate> {
    const response = await api.post<AutomatedMessageTemplate>(
      '/chat/automated-messages',
      template
    );
    return response.data;
  }

  async getAutomatedTemplates(): Promise<AutomatedMessageTemplate[]> {
    const response = await api.get<AutomatedMessageTemplate[]>('/chat/automated-messages');
    return response.data;
  }

  async updateAutomatedTemplate(
    templateId: string,
    updates: Partial<AutomatedMessageTemplate>
  ): Promise<AutomatedMessageTemplate> {
    const response = await api.put<AutomatedMessageTemplate>(
      `/chat/automated-messages/${templateId}`,
      updates
    );
    return response.data;
  }

  async toggleAutomatedTemplate(
    templateId: string,
    isActive: boolean
  ): Promise<AutomatedMessageTemplate> {
    const response = await api.put<AutomatedMessageTemplate>(
      `/chat/automated-messages/${templateId}`,
      { is_active: isActive }
    );
    return response.data;
  }

  async deleteAutomatedTemplate(templateId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(
      `/chat/automated-messages/${templateId}`
    );
    return response.data;
  }

  // Utility Methods
  async exportConversation(conversationId: string, format: 'pdf' | 'txt'): Promise<Blob> {
    const response = await api.get<Blob>(`/chat/conversations/${conversationId}/export`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  }

  async getQuickReplies(): Promise<any[]> {
    const response = await api.get<any[]>('/chat/quick-replies');
    return response.data;
  }

  async createQuickReply(content: string, category?: string): Promise<any> {
    const response = await api.post('/chat/quick-replies', { content, category });
    return response.data;
  }

  async deleteQuickReply(replyId: string): Promise<{ success: boolean }> {
    const response = await api.delete<{ success: boolean }>(`/chat/quick-replies/${replyId}`);
    return response.data;
  }

  async getMessageTemplates(): Promise<any[]> {
    const response = await api.get<any[]>('/chat/message-templates');
    return response.data;
  }

  async createMessageTemplate(name: string, content: string, variables?: string[]): Promise<any> {
    const response = await api.post('/chat/message-templates', { name, content, variables });
    return response.data;
  }
}

export const chatService = new ChatService();