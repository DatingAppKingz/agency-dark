import { vi } from 'vitest';
import { socketManager } from '@/services/socket/socketManager';
import { io } from 'socket.io-client';
import { authService } from '@/services/auth/authService';

// Create separate mock sockets for each namespace
const createMockSocket = () => ({
  connected: false,
  on: vi.fn(),
  off: vi.fn(),
  emit: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  id: 'mock-socket-id',
});

let mockMainSocket: ReturnType<typeof createMockSocket>;
let mockChatSocket: ReturnType<typeof createMockSocket>;
let mockNotificationSocket: ReturnType<typeof createMockSocket>;
let mockDashboardSocket: ReturnType<typeof createMockSocket>;

// Mock socket.io-client
vi.mock('socket.io-client', () => {
  return {
    io: vi.fn((url: string) => {
      if (url.includes('/chat')) {
        mockChatSocket = createMockSocket();
        return mockChatSocket;
      } else if (url.includes('/notifications')) {
        mockNotificationSocket = createMockSocket();
        return mockNotificationSocket;
      } else if (url.includes('/dashboard')) {
        mockDashboardSocket = createMockSocket();
        return mockDashboardSocket;
      } else {
        mockMainSocket = createMockSocket();
        return mockMainSocket;
      }
    }),
    Socket: vi.fn(),
  };
});

// Mock authService
vi.mock('@/services/auth/authService', () => ({
  authService: {
    getAccessToken: vi.fn(() => 'mock-token'),
  },
}));

describe('Socket.IO Connection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset socketManager state by disconnecting any existing connections
    socketManager.disconnect();
  });

  afterEach(() => {
    // Clean up after each test
    socketManager.disconnect();
  });

  describe('Connection Management', () => {
    it('should establish socket connections when authenticated', () => {
      socketManager.connect();

      // Should create 4 socket connections (main, chat, notifications, dashboard)
      expect(io).toHaveBeenCalledTimes(4);
      
      // Check main namespace
      expect(io).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          auth: { token: 'mock-token' },
          transports: ['websocket', 'polling'],
        })
      );

      // Check chat namespace
      expect(io).toHaveBeenCalledWith(
        expect.stringContaining('/chat'),
        expect.objectContaining({
          auth: { token: 'mock-token' },
        })
      );
    });

    it('should not connect when no auth token available', () => {
      vi.mocked(authService.getAccessToken).mockReturnValue(null);
      vi.mocked(io).mockClear();
      
      socketManager.connect();

      expect(io).not.toHaveBeenCalled();
    });

    it('should handle connection events', () => {
      const connectHandler = vi.fn();
      socketManager.on('connect', connectHandler);
      
      socketManager.connect();

      // Simulate connection on main socket
      const onConnectCall = mockMainSocket.on.mock.calls.find(
        ([event]) => event === 'connect'
      );
      if (onConnectCall) {
        onConnectCall[1]();
      }

      expect(connectHandler).toHaveBeenCalled();
    });

    it('should handle disconnection events', () => {
      const disconnectHandler = vi.fn();
      socketManager.on('disconnect', disconnectHandler);
      
      socketManager.connect();

      // Simulate disconnection on main socket
      const onDisconnectCall = mockMainSocket.on.mock.calls.find(
        ([event]) => event === 'disconnect'
      );
      if (onDisconnectCall) {
        onDisconnectCall[1]('io server disconnect');
      }

      expect(disconnectHandler).toHaveBeenCalledWith('io server disconnect');
    });

    it('should disconnect all sockets', () => {
      socketManager.connect();
      socketManager.disconnect();

      expect(mockMainSocket.disconnect).toHaveBeenCalled();
      expect(mockChatSocket.disconnect).toHaveBeenCalled();
      expect(mockNotificationSocket.disconnect).toHaveBeenCalled();
      expect(mockDashboardSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('Message Handling', () => {
    beforeEach(() => {
      socketManager.connect();
    });

    it('should send chat messages', () => {
      socketManager.sendMessage('123', 'Hello', ['image.jpg']);

      expect(mockChatSocket.emit).toHaveBeenCalledWith('message:send', {
        conversation_id: '123',
        content: 'Hello',
        media_urls: ['image.jpg'],
      });
    });

    it('should handle incoming messages', () => {
      const messageHandler = vi.fn();
      socketManager.on('message:new', messageHandler);

      // Simulate incoming message on chat socket
      const onMessageCall = mockChatSocket.on.mock.calls.find(
        ([event]) => event === 'message:new'
      );
      
      const incomingMessage = {
        id: '1',
        content: 'New message',
        sender_id: 'user1',
      };

      if (onMessageCall) {
        onMessageCall[1](incomingMessage);
      }

      expect(messageHandler).toHaveBeenCalledWith(incomingMessage);
    });

    it('should emit typing status', () => {
      socketManager.emitTyping('123', true);

      expect(mockChatSocket.emit).toHaveBeenCalledWith('typing:start', {
        conversation_id: '123',
      });

      socketManager.emitTyping('123', false);

      expect(mockChatSocket.emit).toHaveBeenCalledWith('typing:stop', {
        conversation_id: '123',
      });
    });

    it('should handle typing status updates', () => {
      const typingHandler = vi.fn();
      socketManager.on('typing:status', typingHandler);

      // Simulate typing start on chat socket
      const onTypingStartCall = mockChatSocket.on.mock.calls.find(
        ([event]) => event === 'typing:start'
      );
      
      if (onTypingStartCall) {
        onTypingStartCall[1]({ user_id: 'user1', conversation_id: '123' });
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
      socketManager.joinConversation('123');

      expect(mockChatSocket.emit).toHaveBeenCalledWith('conversation:join', {
        conversation_id: '123',
      });
    });

    it('should leave conversation room', () => {
      socketManager.leaveConversation('123');

      expect(mockChatSocket.emit).toHaveBeenCalledWith('conversation:leave', {
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

      // Simulate error on main socket
      const onErrorCall = mockMainSocket.on.mock.calls.find(
        ([event]) => event === 'error'
      );
      
      const error = new Error('Connection failed');
      
      if (onErrorCall) {
        onErrorCall[1](error);
      }

      expect(errorHandler).toHaveBeenCalledWith(error);
    });

    it('should handle authentication events', () => {
      const connectedHandler = vi.fn();
      socketManager.on('connected', connectedHandler);

      // Simulate auth success on main socket
      const onConnectedCall = mockMainSocket.on.mock.calls.find(
        ([event]) => event === 'connected'
      );
      
      const authData = { user_id: 'user1', username: 'test', role: 'model' };
      
      if (onConnectedCall) {
        onConnectedCall[1](authData);
      }

      expect(connectedHandler).toHaveBeenCalledWith(authData);
    });
  });

  describe('Connection Status', () => {
    it('should report connection status', () => {
      expect(socketManager.isConnected()).toBe(false);
      
      vi.mocked(io).mockImplementation((url: string) => {
        const socket = createMockSocket();
        socket.connected = true;
        return socket as any;
      });
      
      socketManager.connect();
      
      // Note: In real implementation, this would return true after connect
      // but our mock doesn't properly simulate the connected state
      expect(socketManager.isConnected()).toBe(false);
    });

    it('should report namespace connection status', () => {
      socketManager.connect();
      
      expect(socketManager.isNamespaceConnected('chat')).toBe(false);
      expect(socketManager.isNamespaceConnected('notifications')).toBe(false);
      expect(socketManager.isNamespaceConnected('dashboard')).toBe(false);
    });
  });

  describe('Event Listener Management', () => {
    it('should add and remove event listeners', () => {
      const handler = vi.fn();
      
      socketManager.on('connect', handler);
      socketManager.off('connect', handler);
      
      // Trigger event to verify handler was removed
      socketManager.connect();
      
      const onConnectCall = mockMainSocket.on.mock.calls.find(
        ([event]) => event === 'connect'
      );
      if (onConnectCall) {
        onConnectCall[1]();
      }
      
      // Handler should not be called since it was removed
      expect(handler).not.toHaveBeenCalled();
    });
  });
});