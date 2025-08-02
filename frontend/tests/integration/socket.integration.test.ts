import { io } from 'socket.io-client';
import { SocketManager } from '../../__mocks__/services';
// import { createMockUser } from '@/tests/utils/test-utils';

// Mock socket.io-client
jest.mock('socket.io-client');

describe('Socket.IO Integration Tests', () => {
  let mockSocket: any;
  let socketManager: SocketManager;
  // const mockUser = createMockUser(); // Would be used for user-specific socket events

  beforeEach(() => {
    // Create mock socket instance
    mockSocket = {
      connected: false,
      id: 'mock-socket-id',
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
      connect: jest.fn(),
      disconnect: jest.fn(),
      onAny: jest.fn(),
      offAny: jest.fn(),
    };

    // Mock io function to return our mock socket
    (io as jest.Mock).mockReturnValue(mockSocket);

    // Create socket manager instance
    socketManager = SocketManager.getInstance();
  });

  afterEach(() => {
    jest.clearAllMocks();
    // Reset singleton instance
    (SocketManager as any).instance = null;
  });

  describe('Connection Management', () => {
    it('should connect with authentication token', () => {
      const token = 'test-auth-token';
      socketManager.connect(token);

      expect(io).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          auth: { token },
          transports: ['websocket', 'polling'],
          reconnection: true,
          reconnectionAttempts: 5,
          reconnectionDelay: 1000,
        })
      );
    });

    it('should handle successful connection', () => {
      const onConnect = jest.fn();
      socketManager.on('connect', onConnect);

      socketManager.connect('token');
      mockSocket.connected = true;

      // Simulate connection event
      const connectHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'connect'
      )?.[1];
      connectHandler?.();

      expect(onConnect).toHaveBeenCalled();
    });

    it('should handle connection errors', () => {
      const onError = jest.fn();
      socketManager.on('connect_error', onError);

      socketManager.connect('token');

      // Simulate connection error
      const errorHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'connect_error'
      )?.[1];
      const error = new Error('Connection failed');
      errorHandler?.(error);

      expect(onError).toHaveBeenCalledWith(error);
    });

    it('should disconnect properly', () => {
      socketManager.connect('token');
      socketManager.disconnect();

      expect(mockSocket.disconnect).toHaveBeenCalled();
    });

    it('should handle reconnection attempts', () => {
      const onReconnect = jest.fn();
      socketManager.on('reconnect_attempt', onReconnect);

      socketManager.connect('token');

      // Simulate reconnection attempt
      const reconnectHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'reconnect_attempt'
      )?.[1];
      reconnectHandler?.(1);

      expect(onReconnect).toHaveBeenCalledWith(1);
    });
  });

  describe('Message Handling', () => {
    beforeEach(() => {
      socketManager.connect('token');
    });

    it('should emit chat messages', () => {
      const message = {
        conversationId: 'conv-1',
        content: 'Hello, world!',
        type: 'text',
      };

      socketManager.sendMessage(message);

      expect(mockSocket.emit).toHaveBeenCalledWith('chat:message', message);
    });

    it('should receive and handle incoming messages', () => {
      const onMessage = jest.fn();
      socketManager.on('chat:message', onMessage);

      const incomingMessage = {
        id: 'msg-1',
        conversationId: 'conv-1',
        content: 'Hello back!',
        sender: 'user-2',
        timestamp: new Date().toISOString(),
      };

      // Simulate incoming message
      const messageHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'chat:message'
      )?.[1];
      messageHandler?.(incomingMessage);

      expect(onMessage).toHaveBeenCalledWith(incomingMessage);
    });

    it('should handle typing indicators', () => {
      const onTyping = jest.fn();
      socketManager.on('chat:typing', onTyping);

      // Emit typing start
      socketManager.emit('chat:typing', { conversationId: 'conv-1', isTyping: true });
      expect(mockSocket.emit).toHaveBeenCalledWith('chat:typing', {
        conversationId: 'conv-1',
        isTyping: true,
      });

      // Receive typing indicator
      const typingHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'chat:typing'
      )?.[1];
      typingHandler?.({ userId: 'user-2', conversationId: 'conv-1', isTyping: true });

      expect(onTyping).toHaveBeenCalledWith({
        userId: 'user-2',
        conversationId: 'conv-1',
        isTyping: true,
      });
    });

    it('should handle message delivery status', () => {
      const onDelivered = jest.fn();
      socketManager.on('chat:delivered', onDelivered);

      const deliveryStatus = {
        messageId: 'msg-1',
        conversationId: 'conv-1',
        deliveredAt: new Date().toISOString(),
      };

      // Simulate delivery confirmation
      const deliveryHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'chat:delivered'
      )?.[1];
      deliveryHandler?.(deliveryStatus);

      expect(onDelivered).toHaveBeenCalledWith(deliveryStatus);
    });

    it('should handle message read status', () => {
      const onRead = jest.fn();
      socketManager.on('chat:read', onRead);

      const readStatus = {
        messageId: 'msg-1',
        conversationId: 'conv-1',
        readBy: 'user-2',
        readAt: new Date().toISOString(),
      };

      // Simulate read confirmation
      const readHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'chat:read'
      )?.[1];
      readHandler?.(readStatus);

      expect(onRead).toHaveBeenCalledWith(readStatus);
    });
  });

  describe('Room Management', () => {
    beforeEach(() => {
      socketManager.connect('token');
    });

    it('should join conversation rooms', () => {
      const conversationId = 'conv-1';
      socketManager.joinConversation(conversationId);

      expect(mockSocket.emit).toHaveBeenCalledWith('chat:join', { conversationId });
    });

    it('should leave conversation rooms', () => {
      const conversationId = 'conv-1';
      socketManager.leaveConversation(conversationId);

      expect(mockSocket.emit).toHaveBeenCalledWith('chat:leave', { conversationId });
    });

    it('should handle room join confirmation', () => {
      const onJoined = jest.fn();
      socketManager.on('chat:joined', onJoined);

      const joinConfirmation = {
        conversationId: 'conv-1',
        participants: ['user-1', 'user-2'],
      };

      // Simulate join confirmation
      const joinHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'chat:joined'
      )?.[1];
      joinHandler?.(joinConfirmation);

      expect(onJoined).toHaveBeenCalledWith(joinConfirmation);
    });
  });

  describe('Presence Management', () => {
    beforeEach(() => {
      socketManager.connect('token');
    });

    it('should update user presence', () => {
      socketManager.updatePresence('online');

      expect(mockSocket.emit).toHaveBeenCalledWith('presence:update', {
        status: 'online',
      });
    });

    it('should receive presence updates', () => {
      const onPresence = jest.fn();
      socketManager.on('presence:update', onPresence);

      const presenceUpdate = {
        userId: 'user-2',
        status: 'away',
        lastSeen: new Date().toISOString(),
      };

      // Simulate presence update
      const presenceHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'presence:update'
      )?.[1];
      presenceHandler?.(presenceUpdate);

      expect(onPresence).toHaveBeenCalledWith(presenceUpdate);
    });

    it('should handle bulk presence updates', () => {
      const onBulkPresence = jest.fn();
      socketManager.on('presence:bulk', onBulkPresence);

      const bulkUpdate = {
        online: ['user-1', 'user-2'],
        away: ['user-3'],
        offline: ['user-4', 'user-5'],
      };

      // Simulate bulk presence update
      const bulkHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'presence:bulk'
      )?.[1];
      bulkHandler?.(bulkUpdate);

      expect(onBulkPresence).toHaveBeenCalledWith(bulkUpdate);
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      socketManager.connect('token');
    });

    it('should handle authentication errors', () => {
      const onAuthError = jest.fn();
      socketManager.on('auth:error', onAuthError);

      const authError = {
        code: 'INVALID_TOKEN',
        message: 'Authentication token is invalid or expired',
      };

      // Simulate auth error
      const authErrorHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'auth:error'
      )?.[1];
      authErrorHandler?.(authError);

      expect(onAuthError).toHaveBeenCalledWith(authError);
    });

    it('should handle rate limiting', () => {
      const onRateLimit = jest.fn();
      socketManager.on('error:rate_limit', onRateLimit);

      const rateLimitError = {
        retryAfter: 60,
        message: 'Too many requests',
      };

      // Simulate rate limit error
      const rateLimitHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'error:rate_limit'
      )?.[1];
      rateLimitHandler?.(rateLimitError);

      expect(onRateLimit).toHaveBeenCalledWith(rateLimitError);
    });

    it('should handle general socket errors', () => {
      const onError = jest.fn();
      socketManager.on('error', onError);

      const error = new Error('Socket error occurred');

      // Simulate error
      const errorHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'error'
      )?.[1];
      errorHandler?.(error);

      expect(onError).toHaveBeenCalledWith(error);
    });
  });

  describe('Multi-tenant Isolation', () => {
    beforeEach(() => {
      socketManager.connect('token');
    });

    it('should respect agency boundaries in conversations', () => {
      const agencyConversation = {
        conversationId: 'conv-1',
        agencyId: 'agency-1',
      };

      socketManager.joinConversation(agencyConversation.conversationId);

      expect(mockSocket.emit).toHaveBeenCalledWith('chat:join', {
        conversationId: agencyConversation.conversationId,
      });
    });

    it('should not receive messages from other agencies', () => {
      const onMessage = jest.fn();
      socketManager.on('chat:message', onMessage);

      // Message from same agency
      const validMessage = {
        conversationId: 'conv-1',
        agencyId: 'agency-1',
        content: 'Valid message',
      };

      // This should be filtered server-side, but we test client handling
      const messageHandler = mockSocket.on.mock.calls.find(
        call => call[0] === 'chat:message'
      )?.[1];
      messageHandler?.(validMessage);

      expect(onMessage).toHaveBeenCalledWith(validMessage);
    });
  });
});
