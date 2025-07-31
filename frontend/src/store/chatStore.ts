import { create } from 'zustand';
import { Conversation, Message, ChatFilters, TypingStatus } from '@/types/chat';

interface ChatState {
  // Conversations
  conversations: Conversation[];
  activeConversationId: string | null;
  
  // Messages
  messages: Record<string, Message[]>; // conversationId -> messages
  
  // UI State
  filters: ChatFilters;
  typingStatuses: Record<string, boolean>; // userId -> isTyping
  onlineUsers: Set<string>;
  
  // Actions
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  updateConversation: (conversation: Conversation) => void;
  setActiveConversation: (conversationId: string | null) => void;
  
  setMessages: (conversationId: string, messages: Message[]) => void;
  addMessage: (message: Message) => void;
  updateMessage: (message: Message) => void;
  deleteMessage: (conversationId: string, messageId: string) => void;
  
  setFilters: (filters: Partial<ChatFilters>) => void;
  setTypingStatus: (status: TypingStatus) => void;
  setUserOnline: (userId: string, isOnline: boolean) => void;
  
  // Computed
  getConversation: (conversationId: string) => Conversation | undefined;
  getMessages: (conversationId: string) => Message[];
  getUnreadCount: () => number;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  conversations: [],
  activeConversationId: null,
  messages: {},
  filters: {
    search: '',
    status: 'all',
    assigned_to: 'me',
  },
  typingStatuses: {},
  onlineUsers: new Set(),

  // Conversation actions
  setConversations: (conversations) => set({ conversations }),
  
  addConversation: (conversation) => set((state) => ({
    conversations: [conversation, ...state.conversations],
  })),
  
  updateConversation: (conversation) => set((state) => ({
    conversations: state.conversations.map((c) =>
      c.id === conversation.id ? conversation : c
    ),
  })),
  
  setActiveConversation: (conversationId) => set({ activeConversationId: conversationId }),

  // Message actions
  setMessages: (conversationId, messages) => set((state) => ({
    messages: { ...state.messages, [conversationId]: messages },
  })),
  
  addMessage: (message) => set((state) => {
    const conversationMessages = state.messages[message.conversation_id] || [];
    return {
      messages: {
        ...state.messages,
        [message.conversation_id]: [...conversationMessages, message],
      },
    };
  }),
  
  updateMessage: (message) => set((state) => {
    const conversationMessages = state.messages[message.conversation_id] || [];
    return {
      messages: {
        ...state.messages,
        [message.conversation_id]: conversationMessages.map((m) =>
          m.id === message.id ? message : m
        ),
      },
    };
  }),
  
  deleteMessage: (conversationId, messageId) => set((state) => {
    const conversationMessages = state.messages[conversationId] || [];
    return {
      messages: {
        ...state.messages,
        [conversationId]: conversationMessages.filter((m) => m.id !== messageId),
      },
    };
  }),

  // UI actions
  setFilters: (filters) => set((state) => ({
    filters: { ...state.filters, ...filters },
  })),
  
  setTypingStatus: (status) => set((state) => ({
    typingStatuses: {
      ...state.typingStatuses,
      [status.user_id]: status.is_typing,
    },
  })),
  
  setUserOnline: (userId, isOnline) => set((state) => {
    const newOnlineUsers = new Set(state.onlineUsers);
    if (isOnline) {
      newOnlineUsers.add(userId);
    } else {
      newOnlineUsers.delete(userId);
    }
    return { onlineUsers: newOnlineUsers };
  }),

  // Computed getters
  getConversation: (conversationId) => {
    return get().conversations.find((c) => c.id === conversationId);
  },
  
  getMessages: (conversationId) => {
    return get().messages[conversationId] || [];
  },
  
  getUnreadCount: () => {
    return get().conversations.reduce((count, conv) => count + conv.unread_count, 0);
  },
}));
