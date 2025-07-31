import { io, Socket } from 'socket.io-client';
import { authService } from '@/services/auth/authService';
import { Message, TypingStatus, Conversation } from '@/types/chat';
import { logger } from '@/utils/logger';

export interface SocketEvents {
  // Connection events
  connect: () => void;
  disconnect: (reason: string) => void;
  connected: (data: { user_id: string; username: string; role: string }) => void;
  error: (error: any) => void;

  // Chat events (from /chat namespace)
  'message:new': (message: Message) => void;
  'message:updated': (message: Message) => void;
  'message:deleted': (data: { conversation_id: string; message_id: string }) => void;
  'typing:status': (status: TypingStatus) => void;
  'conversation:updated': (conversation: Conversation) => void;
  'fan:claimed': (data: { fan_id: string; chatter_id: string }) => void;
  'fan:released': (data: { fan_id: string }) => void;

  // Notification events (from /notifications namespace)
  'notification': (notification: any) => void;
  'user:online': (userId: string) => void;
  'user:offline': (userId: string) => void;
  
  // Message status events
  'message:delivered': (data: { message_id: string; delivered_at: string }) => void;
  'message:read': (data: { message_id: string; read_at: string }) => void;
}

class SocketManager {
  private mainSocket: Socket | null = null;
  private chatSocket: Socket | null = null;
  private notificationSocket: Socket | null = null;
  private dashboardSocket: Socket | null = null;
  private listeners: Map<string, Set<(...args: any[]) => void>> = new Map();

  connect(): void {
    const token = authService.getAccessToken();
    if (!token) {
      logger.error('No auth token available for socket connection');
      return;
    }

    const wsUrl = import.meta.env.VITE_WS_URL || 'http://localhost:8000';

    // Connect to main namespace
    if (!this.mainSocket?.connected) {
      this.mainSocket = io(wsUrl, {
        auth: { token },
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
      });
      this.setupMainEventListeners();
    }

    // Connect to chat namespace
    if (!this.chatSocket?.connected) {
      this.chatSocket = io(`${wsUrl}/chat`, {
        auth: { token },
        transports: ['websocket', 'polling'],
      });
      this.setupChatEventListeners();
    }

    // Connect to notifications namespace
    if (!this.notificationSocket?.connected) {
      this.notificationSocket = io(`${wsUrl}/notifications`, {
        auth: { token },
        transports: ['websocket', 'polling'],
      });
      this.setupNotificationEventListeners();
    }

    // Connect to dashboard namespace
    if (!this.dashboardSocket?.connected) {
      this.dashboardSocket = io(`${wsUrl}/dashboard`, {
        auth: { token },
        transports: ['websocket', 'polling'],
      });
      this.setupDashboardEventListeners();
    }
  }

  disconnect(): void {
    this.mainSocket?.disconnect();
    this.chatSocket?.disconnect();
    this.notificationSocket?.disconnect();
    this.dashboardSocket?.disconnect();
    
    this.mainSocket = null;
    this.chatSocket = null;
    this.notificationSocket = null;
    this.dashboardSocket = null;
  }

  private setupMainEventListeners(): void {
    if (!this.mainSocket) return;

    this.mainSocket.on('connect', () => {
      logger.info('Main socket connected');
      this.emit('connect');
    });

    this.mainSocket.on('disconnect', (reason) => {
      logger.info('Main socket disconnected:', reason);
      this.emit('disconnect', reason);
    });

    this.mainSocket.on('connected', (data) => {
      logger.info('Socket authenticated:', data);
      this.emit('connected', data);
    });

    this.mainSocket.on('error', (error) => {
      logger.error('Socket error:', error);
      this.emit('error', error);
    });

    // Keep-alive ping/pong
    setInterval(() => {
      if (this.mainSocket?.connected) {
        this.mainSocket.emit('ping');
      }
    }, 30000); // Every 30 seconds
  }

  private setupChatEventListeners(): void {
    if (!this.chatSocket) return;

    this.chatSocket.on('message:new', (message: Message) => {
      this.emit('message:new', message);
    });

    this.chatSocket.on('message:updated', (message: Message) => {
      this.emit('message:updated', message);
    });

    this.chatSocket.on('message:deleted', (data) => {
      this.emit('message:deleted', data);
    });

    this.chatSocket.on('typing:start', (data) => {
      this.emit('typing:status', { ...data, is_typing: true });
    });

    this.chatSocket.on('typing:stop', (data) => {
      this.emit('typing:status', { ...data, is_typing: false });
    });

    this.chatSocket.on('conversation:updated', (conversation: Conversation) => {
      this.emit('conversation:updated', conversation);
    });

    this.chatSocket.on('fan:claimed', (data) => {
      this.emit('fan:claimed', data);
    });

    this.chatSocket.on('fan:released', (data) => {
      this.emit('fan:released', data);
    });

    this.chatSocket.on('message:delivered', (data) => {
      this.emit('message:delivered', data);
    });

    this.chatSocket.on('message:read', (data) => {
      this.emit('message:read', data);
    });
  }

  private setupNotificationEventListeners(): void {
    if (!this.notificationSocket) return;

    this.notificationSocket.on('notification', (notification: any) => {
      this.emit('notification', notification);
    });

    this.notificationSocket.on('user:online', (userId: string) => {
      this.emit('user:online', userId);
    });

    this.notificationSocket.on('user:offline', (userId: string) => {
      this.emit('user:offline', userId);
    });
  }

  private setupDashboardEventListeners(): void {
    if (!this.dashboardSocket) return;

    // Dashboard real-time updates
    this.dashboardSocket.on('stats:update', (stats) => {
      // Handle dashboard stats updates
      logger.info('Dashboard stats updated:', stats);
    });
  }

  // Event emitter methods
  on<K extends keyof SocketEvents>(event: K, callback: SocketEvents[K]): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback as (...args: any[]) => void);
  }

  off<K extends keyof SocketEvents>(event: K, callback: SocketEvents[K]): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback as (...args: any[]) => void);
    }
  }

  private emit(event: string, ...args: any[]): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => callback(...args));
    }
  }

  // Chat namespace methods
  emitTyping(conversationId: string, isTyping: boolean): void {
    this.chatSocket?.emit(isTyping ? 'typing:start' : 'typing:stop', { 
      conversation_id: conversationId 
    });
  }

  joinConversation(conversationId: string): void {
    this.chatSocket?.emit('conversation:join', { conversation_id: conversationId });
  }

  leaveConversation(conversationId: string): void {
    this.chatSocket?.emit('conversation:leave', { conversation_id: conversationId });
  }

  claimFan(fanId: string): void {
    this.chatSocket?.emit('fan:claim', { fan_id: fanId });
  }

  releaseFan(fanId: string): void {
    this.chatSocket?.emit('fan:release', { fan_id: fanId });
  }

  sendMessage(conversationId: string, content: string, mediaUrls?: string[]): void {
    this.chatSocket?.emit('message:send', {
      conversation_id: conversationId,
      content,
      media_urls: mediaUrls || [],
    });
  }

  markAsRead(conversationId: string, messageIds: string[]): void {
    this.chatSocket?.emit('message:read', {
      conversation_id: conversationId,
      message_ids: messageIds,
    });
  }

  // Notification namespace methods
  subscribeToNotifications(): void {
    this.notificationSocket?.emit('subscribe');
  }

  unsubscribeFromNotifications(): void {
    this.notificationSocket?.emit('unsubscribe');
  }

  // Dashboard namespace methods
  subscribeToDashboard(modelId?: string): void {
    this.dashboardSocket?.emit('subscribe', { model_id: modelId });
  }

  unsubscribeFromDashboard(): void {
    this.dashboardSocket?.emit('unsubscribe');
  }

  // Connection status
  isConnected(): boolean {
    return this.mainSocket?.connected || false;
  }

  isNamespaceConnected(namespace: 'chat' | 'notifications' | 'dashboard'): boolean {
    switch(namespace) {
      case 'chat':
        return this.chatSocket?.connected || false;
      case 'notifications':
        return this.notificationSocket?.connected || false;
      case 'dashboard':
        return this.dashboardSocket?.connected || false;
      default:
        return false;
    }
  }
}

export const socketManager = new SocketManager();
