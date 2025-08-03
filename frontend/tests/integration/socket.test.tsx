import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { io, Socket } from 'socket.io-client';
import { useSocket } from '@/providers/SocketProvider';
import { mockAuthStore } from '@/__tests__/mocks/store-mocks';

// Mock socket.io-client
vi.mock('socket.io-client');

describe('Socket.IO Connection', () => {
  let mockSocket: Partial<Socket>;

  beforeEach(() => {
    mockSocket = {
      connected: false,
      on: vi.fn(),
      off: vi.fn(),
      emit: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      id: 'mock-socket-id',
    };

    (io as vi.Mock).mockReturnValue(mockSocket);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Connection Management', () => {
    it('should establish socket connection when authenticated', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => mockAuthStore,
      }));

      renderHook(() => useSocket());

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
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          isAuthenticated: false,
          token: null,
        }),
      }));

      renderHook(() => useSocket());

      expect(io).not.toHaveBeenCalled();
    });

    it('should handle connection events', () => {
      renderHook(() => useSocket());

      // Simulate connection
      act(() => {
        const connectHandler = (mockSocket.on as vi.Mock).mock.calls.find(
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
      renderHook(() => useSocket());

      // Simulate disconnection
      act(() => {
        const disconnectHandler = (mockSocket.on as vi.Mock).mock.calls.find(
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
      renderHook(() => useSocket());

      // Simulate reconnect attempt
      act(() => {
        const reconnectHandler = (mockSocket.on as vi.Mock).mock.calls.find(
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
      renderHook(() => useSocket());
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
      const messageHandler = vi.fn();
      renderHook(() => useSocket());
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
        const handler = (mockSocket.on as vi.Mock).mock.calls.find(
          ([event]) => event === 'new_message'
        )?.[1];
        if (handler) {
          handler(incomingMessage);
        }
      });

      expect(messageHandler).toHaveBeenCalledWith(incomingMessage);
    });

    it('should emit typing status', () => {
      renderHook(() => useSocket());
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
      const typingHandler = vi.fn();
      renderHook(() => useSocket());
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
        const handler = (mockSocket.on as vi.Mock).mock.calls.find(
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
      renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.emit('join_conversation', { conversation_id: '123' });
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('join_conversation', {
        conversation_id: '123',
      });
    });

    it('should leave conversation room', () => {
      renderHook(() => useSocket());
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
      const errorHandler = vi.fn();
      renderHook(() => useSocket());
      const socket = result.current;

      act(() => {
        socket.on('connect_error', errorHandler);
      });

      const error = new Error('Connection failed');

      act(() => {
        const handler = (mockSocket.on as vi.Mock).mock.calls.find(
          ([event]) => event === 'connect_error'
        )?.[1];
        if (handler) {
          handler(error);
        }
      });

      expect(errorHandler).toHaveBeenCalledWith(error);
    });

    it('should handle authentication errors', () => {
      renderHook(() => useSocket());

      const authError = { message: 'Invalid token' };

      act(() => {
        const handler = (mockSocket.on as vi.Mock).mock.calls.find(
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
      const { unmount } = renderHook(() => useSocket());

      unmount();

      expect(mockSocket.off).toHaveBeenCalled();
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });

    it('should remove specific event listeners', () => {
      renderHook(() => useSocket());
      const socket = result.current;
      const handler = vi.fn();

      act(() => {
        socket.on('test_event', handler);
        socket.off('test_event', handler);
      });

      expect(mockSocket.off).toHaveBeenCalledWith('test_event', handler);
    });
  });
});
