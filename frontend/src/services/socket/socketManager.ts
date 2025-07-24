import { io, Socket } from 'socket.io-client';
import { authService } from '@/services/auth/authService';
import { Message, TypingStatus, Conversation } from '@/types/chat';

export interface SocketEvents {
  // Connection events
  connect: () => void;
  disconnect: (reason: string) => void;
  error: (error: Error) => void;

  // Chat events
  'message:new': (message: Message) => void;
  'message:updated': (message: Message) => void;
  'message:deleted': (data: { conversation_id: string; message_id: string }) => void;
  'typing:status': (status: TypingStatus) => void;
  'conversation:updated': (conversation: Conversation) => void;
  'user:online': (userId: string) => void;
  'user:offline': (userId: string) => void;

  // Notification events
  'notification': (notification: any) => void;
}

class SocketManager {
  private socket: Socket | null = null;
  private listeners: Map<string, Set<Function>> = new Map();

  connect(): void {
    if (this.socket?.connected) {
      return;
    }

    const token = authService.getAccessToken();
    if (!token) {
      console.error('No auth token available for socket connection');
      return;
    }

    const wsUrl = import.meta.env.VITE_WS_URL || 'http://localhost:8000';

    this.socket = io(wsUrl, {
      auth: { token },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    this.setupEventListeners();
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  private setupEventListeners(): void {
    if (!this.socket) return;

    // Connection events
    this.socket.on('connect', () => {
      console.log('Socket connected');
      this.emit('connect');
    });

    this.socket.on('disconnect', (reason) => {
      console.log('Socket disconnected:', reason);
      this.emit('disconnect', reason);
    });

    this.socket.on('error', (error) => {
      console.error('Socket error:', error);
      this.emit('error', error);
    });

    // Chat events
    this.socket.on('message:new', (message: Message) => {
      this.emit('message:new', message);
    });

    this.socket.on('message:updated', (message: Message) => {
      this.emit('message:updated', message);
    });

    this.socket.on('message:deleted', (data) => {
      this.emit('message:deleted', data);
    });

    this.socket.on('typing:status', (status: TypingStatus) => {
      this.emit('typing:status', status);
    });

    this.socket.on('conversation:updated', (conversation: Conversation) => {
      this.emit('conversation:updated', conversation);
    });

    this.socket.on('user:online', (userId: string) => {
      this.emit('user:online', userId);
    });

    this.socket.on('user:offline', (userId: string) => {
      this.emit('user:offline', userId);
    });

    this.socket.on('notification', (notification: any) => {
      this.emit('notification', notification);
    });
  }

  // Event emitter methods
  on<K extends keyof SocketEvents>(event: K, callback: SocketEvents[K]): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event)!.add(callback as Function);
  }

  off<K extends keyof SocketEvents>(event: K, callback: SocketEvents[K]): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.delete(callback as Function);
    }
  }

  private emit(event: string, ...args: any[]): void {
    const callbacks = this.listeners.get(event);
    if (callbacks) {
      callbacks.forEach(callback => callback(...args));
    }
  }

  // Socket.IO methods
  emitTyping(conversationId: string, isTyping: boolean): void {
    this.socket?.emit('typing', { conversation_id: conversationId, is_typing: isTyping });
  }

  joinConversation(conversationId: string): void {
    this.socket?.emit('join:conversation', conversationId);
  }

  leaveConversation(conversationId: string): void {
    this.socket?.emit('leave:conversation', conversationId);
  }

  subscribeToNotifications(): void {
    this.socket?.emit('subscribe:notifications');
  }

  isConnected(): boolean {
    return this.socket?.connected || false;
  }
}

export const socketManager = new SocketManager();