import { renderHook, act } from '@testing-library/react';
import { io, Socket } from 'socket.io-client';
import { useSocket } from '@/providers/SocketProvider';
import { mockAuthStore } from '@/__tests__/mocks/store-mocks';

// Mock socket.io-client
jest.mock('socket.io-client');

describe('Socket.IO Connection', () => {
  let mockSocket: Partial<Socket>;

  beforeEach(() => {
    mockSocket = {
      connected: false,
      on: jest.fn(),
      off: jest.fn(),
      emit: jest.fn(),
      connect: jest.fn(),
      disconnect: jest.fn(),
      id: 'mock-socket-id',
    };

    (io as jest.Mock).mockReturnValue(mockSocket);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Connection Management', () => {
    it('should establish socket connection when authenticated', () => {
      jest.mock('@/store/authStore', () => ({
        useAuthStore: () => mockAuthStore,
      }));

      const { result } = renderHook(() => useSocket());

      expect(io).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          auth: {
            token: mockAuthStore.token,
          },
        })
      );
    });

    it('should not connect when not authenticated', () => {
      jest.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          isAuthenticated: false,
          token: null,
        }),
      }));

      const { result } = renderHook(() => useSocket());

      expect(io).not.toHaveBeenCalled();
    });

    it('should handle connection events', () => {
      const { result } = renderHook(() => useSocket());

      // Simulate connection
      act(() => {
        const connectHandler = (mockSocket.on as jest.Mock).mock.calls.find(
          ([event]) => event === 'connect'
        )?.[1];
        if (connectHandler) {
          mockSocket.connected = true;
          connectHandler();
        }
      });

      expect(mockSocket.connected).toBe(true);
    });

    it('should handle disconnection events', () => {
      const { result } = renderHook(() => useSocket());

      // Simulate disconnection
      act(() => {
        const disconnectHandler = (mockSocket.on as jest.Mock).mock.calls.find(
          ([event]) => event === 'disconnect'
        )?.[1];
        if (disconnectHandler) {
          mockSocket.connected = false;
          disconnectHandler();
        }
      });

      expect(mockSocket.connected).toBe(false);
    });

    it('should handle reconnection attempts', () => {
      const { result } = renderHook(() => useSocket());

      // Simulate reconnect attempt
      act(() => {
        const reconnectHandler = (mockSocket.on as jest.Mock).mock.calls.find(
          ([event]) => event === 'reconnect_attempt'
        )?.[1];
        if (reconnectHandler) {
          reconnectHandler(1);
        }
      });

      // Should log reconnection attempt
      expect(mockSocket.on).toHaveBeenCalledWith('reconnect_attempt', expect.any(Function));
    });
  });

  describe('Message Handling', () => {
    it('should emit chat messages', () => {
      const { result } = renderHook(() => useSocket());
      const socket = result.current;

      const message = {
        conversation_id: '123',
        content: 'Hello',
      };

      act(() => {
        socket.emit('send_message', message);
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('send_message', message);
    });

    it('should handle incoming messages', () => {
      const messageHandler = jest.fn();
      const { result } = renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.on('new_message', messageHandler);
      });

      // Simulate incoming message
      const incomingMessage = {
        id: '1',
        content: 'New message',
        sender_id: 'user1',
      };

      act(() => {
        const handler = (mockSocket.on as jest.Mock).mock.calls.find(
          ([event]) => event === 'new_message'
        )?.[1];
        if (handler) {
          handler(incomingMessage);
        }
      });

      expect(messageHandler).toHaveBeenCalledWith(incomingMessage);
    });

    it('should emit typing status', () => {
      const { result } = renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.emit('typing', {
          conversation_id: '123',
          is_typing: true,
        });
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('typing', {
        conversation_id: '123',
        is_typing: true,
      });
    });

    it('should handle typing status updates', () => {
      const typingHandler = jest.fn();
      const { result } = renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.on('typing_status', typingHandler);
      });

      const typingStatus = {
        user_id: 'user1',
        conversation_id: '123',
        is_typing: true,
      };

      act(() => {
        const handler = (mockSocket.on as jest.Mock).mock.calls.find(
          ([event]) => event === 'typing_status'
        )?.[1];
        if (handler) {
          handler(typingStatus);
        }
      });

      expect(typingHandler).toHaveBeenCalledWith(typingStatus);
    });
  });

  describe('Room Management', () => {
    it('should join conversation room', () => {
      const { result } = renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.emit('join_conversation', { conversation_id: '123' });
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('join_conversation', {
        conversation_id: '123',
      });
    });

    it('should leave conversation room', () => {
      const { result } = renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.emit('leave_conversation', { conversation_id: '123' });
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('leave_conversation', {
        conversation_id: '123',
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle connection errors', () => {
      const errorHandler = jest.fn();
      const { result } = renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.on('connect_error', errorHandler);
      });

      const error = new Error('Connection failed');

      act(() => {
        const handler = (mockSocket.on as jest.Mock).mock.calls.find(
          ([event]) => event === 'connect_error'
        )?.[1];
        if (handler) {
          handler(error);
        }
      });

      expect(errorHandler).toHaveBeenCalledWith(error);
    });

    it('should handle authentication errors', () => {
      const { result } = renderHook(() => useSocket());

      const authError = { message: 'Invalid token' };

      act(() => {
        const handler = (mockSocket.on as jest.Mock).mock.calls.find(
          ([event]) => event === 'auth_error'
        )?.[1];
        if (handler) {
          handler(authError);
        }
      });

      // Should disconnect on auth error
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });
  });

  describe('Cleanup', () => {
    it('should cleanup event listeners on unmount', () => {
      const { result, unmount } = renderHook(() => useSocket());

      unmount();

      expect(mockSocket.off).toHaveBeenCalled();
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });

    it('should remove specific event listeners', () => {
      const { result } = renderHook(() => useSocket());
      const socket = result.current;
      const handler = jest.fn();

      act(() => {
        socket.on('test_event', handler);
        socket.off('test_event', handler);
      });

      expect(mockSocket.off).toHaveBeenCalledWith('test_event', handler);
    });
  });
});