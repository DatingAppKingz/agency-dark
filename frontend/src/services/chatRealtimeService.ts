import { realtimeService, useRealtimeEvent, useRealtimePresence } from './realtimeService';
import { useEffect, useState, useCallback, useRef } from 'react';

interface ChatMessage {
  id: string;
  conversationId: string;
  senderId: string;
  content: string;
  timestamp: Date;
  status: 'sending' | 'sent' | 'delivered' | 'read' | 'failed';
  metadata?: Record<string, any>;
}

interface TypingIndicator {
  userId: string;
  conversationId: string;
  isTyping: boolean;
}

interface ChatRoom {
  conversationId: string;
  participants: string[];
  lastActivity: Date;
  unreadCount: number;
}

class ChatRealtimeService {
  private typingTimeouts: Map<string, NodeJS.Timeout> = new Map();
  private messageRetryQueue: Map<string, ChatMessage> = new Map();
  private localMessageCache: Map<string, ChatMessage> = new Map();

  // Join a chat conversation
  async joinConversation(conversationId: string): Promise<void> {
    await realtimeService.joinRoom(`chat:${conversationId}`);
    await realtimeService.emitWithAck('chat:join', { conversationId });
  }

  // Leave a chat conversation
  async leaveConversation(conversationId: string): Promise<void> {
    await realtimeService.leaveRoom(`chat:${conversationId}`);
    await realtimeService.emitWithAck('chat:leave', { conversationId });
  }

  // Send a message
  async sendMessage(
    conversationId: string,
    content: string,
    metadata?: Record<string, any>
  ): Promise<ChatMessage> {
    const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const message: ChatMessage = {
      id: tempId,
      conversationId,
      senderId: 'current_user', // Should be replaced with actual user ID
      content,
      timestamp: new Date(),
      status: 'sending',
      metadata,
    };

    // Store in local cache for optimistic UI
    this.localMessageCache.set(tempId, message);

    try {
      // If offline, queue the message
      if (!realtimeService.isConnected()) {
        message.status = 'failed';
        this.messageRetryQueue.set(tempId, message);
        realtimeService.queueMessage('chat:send', {
          conversationId,
          content,
          metadata,
          tempId,
        });
        return message;
      }

      // Send message
      const response = await realtimeService.emitWithAck('chat:send', {
        conversationId,
        content,
        metadata,
        tempId,
      });

      // Update message with server response
      const serverMessage: ChatMessage = {
        ...message,
        id: response.id,
        status: 'sent',
        timestamp: new Date(response.timestamp),
      };

      // Update local cache
      this.localMessageCache.delete(tempId);
      this.localMessageCache.set(response.id, serverMessage);

      return serverMessage;
    } catch (error) {
      // Mark as failed and add to retry queue
      message.status = 'failed';
      this.messageRetryQueue.set(tempId, message);
      throw error;
    }
  }

  // Retry failed messages
  async retryFailedMessages(conversationId: string): Promise<void> {
    const failedMessages = Array.from(this.messageRetryQueue.values())
      .filter(msg => msg.conversationId === conversationId);

    for (const message of failedMessages) {
      try {
        await this.sendMessage(
          message.conversationId,
          message.content,
          message.metadata
        );
        this.messageRetryQueue.delete(message.id);
      } catch (error) {
        console.error('Failed to retry message:', error);
      }
    }
  }

  // Mark messages as read
  async markAsRead(conversationId: string, messageIds: string[]): Promise<void> {
    if (!realtimeService.isConnected()) {
      realtimeService.queueMessage('chat:read', { conversationId, messageIds });
      return;
    }

    await realtimeService.emitWithAck('chat:read', {
      conversationId,
      messageIds,
    });
  }

  // Send typing indicator
  async sendTypingIndicator(conversationId: string, isTyping: boolean): Promise<void> {
    // Clear existing timeout
    const timeoutKey = `${conversationId}_typing`;
    const existingTimeout = this.typingTimeouts.get(timeoutKey);
    if (existingTimeout) {
      clearTimeout(existingTimeout);
      this.typingTimeouts.delete(timeoutKey);
    }

    if (isTyping) {
      // Send typing indicator
      realtimeService.emit('chat:typing', {
        conversationId,
        isTyping: true,
      });

      // Auto-stop typing after 5 seconds
      const timeout = setTimeout(() => {
        this.sendTypingIndicator(conversationId, false);
      }, 5000);
      this.typingTimeouts.set(timeoutKey, timeout);
    } else {
      // Send stop typing
      realtimeService.emit('chat:typing', {
        conversationId,
        isTyping: false,
      });
    }
  }

  // Get local message (for optimistic UI)
  getLocalMessage(messageId: string): ChatMessage | null {
    return this.localMessageCache.get(messageId) || null;
  }

  // Clear conversation cache
  clearConversationCache(conversationId: string): void {
    // Remove messages for this conversation from cache
    Array.from(this.localMessageCache.entries()).forEach(([id, message]) => {
      if (message.conversationId === conversationId) {
        this.localMessageCache.delete(id);
      }
    });
  }
}

// Create singleton instance
export const chatRealtimeService = new ChatRealtimeService();

// React hooks for chat functionality

// Hook for real-time messages
export const useRealtimeMessages = (conversationId: string) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [optimisticMessages, setOptimisticMessages] = useState<ChatMessage[]>([]);

  // Handle new messages
  useRealtimeEvent<ChatMessage>('chat:message', (message) => {
    if (message.conversationId === conversationId) {
      setMessages(prev => [...prev, message]);
      // Remove from optimistic if it exists
      setOptimisticMessages(prev => 
        prev.filter(msg => msg.id !== message.id)
      );
    }
  }, [conversationId]);

  // Handle message updates (status changes)
  useRealtimeEvent<Partial<ChatMessage>>('chat:messageUpdate', (update) => {
    setMessages(prev => 
      prev.map(msg => 
        msg.id === update.id ? { ...msg, ...update } : msg
      )
    );
  }, []);

  // Handle message deletion
  useRealtimeEvent<{ messageId: string }>('chat:messageDeleted', ({ messageId }) => {
    setMessages(prev => prev.filter(msg => msg.id !== messageId));
  }, []);

  const sendMessage = useCallback(async (content: string, metadata?: Record<string, any>) => {
    const optimisticMessage = await chatRealtimeService.sendMessage(
      conversationId,
      content,
      metadata
    );
    
    // Add to optimistic messages for immediate UI update
    setOptimisticMessages(prev => [...prev, optimisticMessage]);
    
    return optimisticMessage;
  }, [conversationId]);

  const markAsRead = useCallback(async (messageIds: string[]) => {
    await chatRealtimeService.markAsRead(conversationId, messageIds);
  }, [conversationId]);

  return {
    messages: [...messages, ...optimisticMessages].sort(
      (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
    ),
    sendMessage,
    markAsRead,
  };
};

// Hook for typing indicators
export const useTypingIndicators = (conversationId: string) => {
  const [typingUsers, setTypingUsers] = useState<Set<string>>(new Set());
  const typingTimeouts = useRef<Map<string, NodeJS.Timeout>>(new Map());

  useRealtimeEvent<TypingIndicator>('chat:typing', (indicator) => {
    if (indicator.conversationId === conversationId) {
      const timeoutKey = `${indicator.userId}_typing`;
      
      // Clear existing timeout
      const existingTimeout = typingTimeouts.current.get(timeoutKey);
      if (existingTimeout) {
        clearTimeout(existingTimeout);
      }

      if (indicator.isTyping) {
        setTypingUsers(prev => new Set(prev).add(indicator.userId));
        
        // Auto-remove after 6 seconds (in case stop event is missed)
        const timeout = setTimeout(() => {
          setTypingUsers(prev => {
            const next = new Set(prev);
            next.delete(indicator.userId);
            return next;
          });
        }, 6000);
        
        typingTimeouts.current.set(timeoutKey, timeout);
      } else {
        setTypingUsers(prev => {
          const next = new Set(prev);
          next.delete(indicator.userId);
          return next;
        });
      }
    }
  }, [conversationId]);

  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      typingTimeouts.current.forEach(timeout => clearTimeout(timeout));
    };
  }, []);

  const sendTyping = useCallback(async (isTyping: boolean) => {
    await chatRealtimeService.sendTypingIndicator(conversationId, isTyping);
  }, [conversationId]);

  return {
    typingUsers: Array.from(typingUsers),
    sendTyping,
  };
};

// Hook for chat presence
export const useChatPresence = (participantIds: string[]) => {
  const presence = useRealtimePresence(participantIds);
  
  const onlineUsers = Array.from(presence.values())
    .filter(p => p.status === 'online')
    .map(p => p.userId);

  return {
    presence,
    onlineUsers,
    isUserOnline: (userId: string) => presence.get(userId)?.status === 'online',
  };
};

// Hook for unread counts
export const useUnreadCounts = () => {
  const [unreadCounts, setUnreadCounts] = useState<Map<string, number>>(new Map());

  useRealtimeEvent<{ conversationId: string; count: number }>('chat:unreadUpdate', ({ conversationId, count }) => {
    setUnreadCounts(prev => {
      const next = new Map(prev);
      next.set(conversationId, count);
      return next;
    });
  }, []);

  return unreadCounts;
};

// Hook for chat rooms/conversations list
export const useChatRooms = () => {
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const unreadCounts = useUnreadCounts();

  useRealtimeEvent<ChatRoom>('chat:roomUpdate', (room) => {
    setRooms(prev => {
      const index = prev.findIndex(r => r.conversationId === room.conversationId);
      if (index >= 0) {
        const next = [...prev];
        next[index] = room;
        return next;
      }
      return [...prev, room];
    });
  }, []);

  useRealtimeEvent<{ conversationId: string }>('chat:roomDeleted', ({ conversationId }) => {
    setRooms(prev => prev.filter(r => r.conversationId !== conversationId));
  }, []);

  const roomsWithUnread = rooms.map(room => ({
    ...room,
    unreadCount: unreadCounts.get(room.conversationId) || 0,
  }));

  return roomsWithUnread.sort((a, b) => 
    b.lastActivity.getTime() - a.lastActivity.getTime()
  );
};