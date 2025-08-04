import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { io, Socket } from 'socket.io-client';
import { authService } from '@/services/auth/authService';
import { socketManager } from '@/services/socket/socketManager';

// Mock socket.io-client
vi.mock('socket.io-client');

// Mock authService
vi.mock('@/services/auth/authService');

// Mock logger to prevent console errors
vi.mock('@/utils/logger', () => ({
  logger: {
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
  },
}));

describe('Socket.IO Connection - Simplified', () => {
  let mockSockets: Record<string, any> = {};
  let eventHandlers: Record<string, Record<string, Function>> = {};

  const createMockSocket = (namespace: string) => {
    const handlers: Record<string, Function[]> = {};
    
    const socket = {
      connected: false,
      id: `mock-socket-${namespace}`,
      auth: {},
      on: vi.fn((event: string, handler: Function) => {
        if (!handlers[event]) handlers[event] = [];
        handlers[event].push(handler);
        eventHandlers[namespace] = eventHandlers[namespace] || {};
        eventHandlers[namespace][event] = handler;
      }),
      off: vi.fn((event: string, handler?: Function) => {
        if (!handler) {
          delete handlers[event];
        } else {
          handlers[event] = handlers[event]?.filter(h => h !== handler) || [];
        }
      }),
      emit: vi.fn(),
      connect: vi.fn(() => {
        socket.connected = true;
      }),
      disconnect: vi.fn(() => {
        socket.connected = false;
      }),
    };
    
    return socket;
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockSockets = {};
    eventHandlers = {};
    
    // Reset socketManager state
    socketManager.disconnect();
    
    // Mock authService to return a token
    vi.mocked(authService.getAccessToken).mockReturnValue('mock-token');
    
    // Mock io to return our mock sockets
    vi.mocked(io).mockImplementation((url: string, options?: any) => {
      let namespace = 'main';
      if (url.includes('/chat')) namespace = 'chat';
      else if (url.includes('/notifications')) namespace = 'notifications';
      else if (url.includes('/dashboard')) namespace = 'dashboard';
      
      const socket = createMockSocket(namespace);
      // Store auth from options
      if (options?.auth) {
        socket.auth = options.auth;
      }
      mockSockets[namespace] = socket;
      return socket as any;
    });
  });

  afterEach(() => {
    socketManager.disconnect();
  });

  describe('Connection Management', () => {
    it('should establish socket connections when authenticated', () => {
      socketManager.connect();

      // Should create 4 socket connections
      expect(io).toHaveBeenCalledTimes(4);
      
      // Check each namespace was created with auth
      expect(io).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          auth: { token: 'mock-token' },
        })
      );
      
      // Verify all sockets were created
      expect(mockSockets.main).toBeDefined();
      expect(mockSockets.chat).toBeDefined();
      expect(mockSockets.notifications).toBeDefined();
      expect(mockSockets.dashboard).toBeDefined();
    });

    it('should not connect when no auth token available', () => {
      vi.mocked(authService.getAccessToken).mockReturnValue(null);
      
      socketManager.connect();

      expect(io).not.toHaveBeenCalled();
    });

    it('should handle connection events', () => {
      const connectHandler = vi.fn();
      socketManager.on('connect', connectHandler);
      
      socketManager.connect();

      // Simulate connection on main socket
      const mainSocket = mockSockets.main;
      expect(mainSocket).toBeDefined();
      
      // Trigger the connect event
      const onConnectHandler = eventHandlers.main?.connect;
      if (onConnectHandler) {
        onConnectHandler();
      }

      expect(connectHandler).toHaveBeenCalled();
    });

    it('should handle disconnection events', () => {
      const disconnectHandler = vi.fn();
      socketManager.on('disconnect', disconnectHandler);
      
      socketManager.connect();

      // Simulate disconnection
      const onDisconnectHandler = eventHandlers.main?.disconnect;
      if (onDisconnectHandler) {
        onDisconnectHandler('io server disconnect');
      }

      expect(disconnectHandler).toHaveBeenCalledWith('io server disconnect');
    });

    it('should disconnect all sockets', () => {
      socketManager.connect();
      
      const mainSocket = mockSockets.main;
      const chatSocket = mockSockets.chat;
      const notificationSocket = mockSockets.notifications;
      const dashboardSocket = mockSockets.dashboard;
      
      socketManager.disconnect();

      expect(mainSocket.disconnect).toHaveBeenCalled();
      expect(chatSocket.disconnect).toHaveBeenCalled();
      expect(notificationSocket.disconnect).toHaveBeenCalled();
      expect(dashboardSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('Message Handling', () => {
    beforeEach(() => {
      socketManager.connect();
    });

    it('should send chat messages', () => {
      const chatSocket = mockSockets.chat;
      
      socketManager.sendMessage('123', 'Hello', ['image.jpg']);

      expect(chatSocket.emit).toHaveBeenCalledWith('message:send', {
        conversation_id: '123',
        content: 'Hello',
        media_urls: ['image.jpg'],
      });
    });

    it('should handle incoming messages', () => {
      const messageHandler = vi.fn();
      socketManager.on('message:new', messageHandler);

      const incomingMessage = {
        id: '1',
        content: 'New message',
        sender_id: 'user1',
      };

      // Trigger message on chat socket
      const handler = eventHandlers.chat?.['message:new'];
      if (handler) {
        handler(incomingMessage);
      }

      expect(messageHandler).toHaveBeenCalledWith(incomingMessage);
    });

    it('should emit typing status', () => {
      const chatSocket = mockSockets.chat;
      
      socketManager.emitTyping('123', true);
      expect(chatSocket.emit).toHaveBeenCalledWith('typing:start', {
        conversation_id: '123',
      });

      socketManager.emitTyping('123', false);
      expect(chatSocket.emit).toHaveBeenCalledWith('typing:stop', {
        conversation_id: '123',
      });
    });

    it('should handle typing status updates', () => {
      const typingHandler = vi.fn();
      socketManager.on('typing:status', typingHandler);

      // Simulate typing start
      const handler = eventHandlers.chat?.['typing:start'];
      if (handler) {
        handler({ user_id: 'user1', conversation_id: '123' });
      }

      expect(typingHandler).toHaveBeenCalledWith({
        user_id: 'user1',
        conversation_id: '123',
        is_typing: true,
      });
    });
  });

  describe('Room Management', () => {
    beforeEach(() => {
      socketManager.connect();
    });

    it('should join conversation room', () => {
      const chatSocket = mockSockets.chat;
      
      socketManager.joinConversation('123');

      expect(chatSocket.emit).toHaveBeenCalledWith('conversation:join', {
        conversation_id: '123',
      });
    });

    it('should leave conversation room', () => {
      const chatSocket = mockSockets.chat;
      
      socketManager.leaveConversation('123');

      expect(chatSocket.emit).toHaveBeenCalledWith('conversation:leave', {
        conversation_id: '123',
      });
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      socketManager.connect();
    });

    it('should handle connection errors', () => {
      const errorHandler = vi.fn();
      socketManager.on('error', errorHandler);

      const error = new Error('Connection failed');
      
      // Trigger error on main socket
      const handler = eventHandlers.main?.error;
      if (handler) {
        handler(error);
      }

      expect(errorHandler).toHaveBeenCalledWith(error);
    });

    it('should handle authentication events', () => {
      const connectedHandler = vi.fn();
      socketManager.on('connected', connectedHandler);

      const authData = { user_id: 'user1', username: 'test', role: 'model' };
      
      // Trigger connected event
      const handler = eventHandlers.main?.connected;
      if (handler) {
        handler(authData);
      }

      expect(connectedHandler).toHaveBeenCalledWith(authData);
    });
  });

  describe('Connection Status', () => {
    it('should report connection status', () => {
      // Initially disconnected
      expect(socketManager.isConnected()).toBe(false);
      
      // Connect but sockets aren't actually connected yet (just created)
      socketManager.connect();
      expect(socketManager.isConnected()).toBe(false);
      
      // Note: socketManager checks its internal mainSocket?.connected property
      // which we can't easily modify from outside the class
      // This is a limitation of testing a singleton with internal state
    });

    it('should report namespace connection status', () => {
      socketManager.connect();
      
      // All namespaces start disconnected
      expect(socketManager.isNamespaceConnected('chat')).toBe(false);
      expect(socketManager.isNamespaceConnected('notifications')).toBe(false);
      expect(socketManager.isNamespaceConnected('dashboard')).toBe(false);
    });
  });

  describe('Event Listener Management', () => {
    it('should add and remove event listeners', () => {
      const handler = vi.fn();
      
      // Add listener
      socketManager.on('connect', handler);
      
      // Remove listener  
      socketManager.off('connect', handler);
      
      // Connect and trigger event
      socketManager.connect();
      
      const onConnectHandler = eventHandlers.main?.connect;
      if (onConnectHandler) {
        onConnectHandler();
      }
      
      // Handler should not be called since it was removed
      expect(handler).not.toHaveBeenCalled();
    });

    it('should handle multiple listeners for same event', () => {
      const handler1 = vi.fn();
      const handler2 = vi.fn();
      
      socketManager.on('connect', handler1);
      socketManager.on('connect', handler2);
      
      socketManager.connect();
      
      const onConnectHandler = eventHandlers.main?.connect;
      if (onConnectHandler) {
        onConnectHandler();
      }
      
      expect(handler1).toHaveBeenCalled();
      expect(handler2).toHaveBeenCalled();
    });
  });
});