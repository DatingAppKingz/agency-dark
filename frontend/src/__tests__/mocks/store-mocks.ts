import { User } from '@/types/auth';

export const mockUser: User = {
  id: '1',
  email: 'test@example.com',
  full_name: 'Test User',
  role: 'model',
  is_active: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

export const mockAuthStore = {
  user: mockUser,
  token: 'mock-token',
  refreshToken: 'mock-refresh-token',
  isAuthenticated: true,
  isPending: false,
  login: jest.fn(),
  logout: jest.fn(),
  register: jest.fn(),
  updateUser: jest.fn(),
  checkAuth: jest.fn(),
  refreshAccessToken: jest.fn(),
};

export const mockChatStore = {
  conversations: [],
  messages: {},
  activeConversationId: null,
  typingStatuses: {},
  onlineUsers: new Set(),
  filters: {
    search: '',
    status: 'all' as const,
    assigned_to: 'all' as const,
  },
  setConversations: jest.fn(),
  addConversation: jest.fn(),
  updateConversation: jest.fn(),
  setActiveConversation: jest.fn(),
  setMessages: jest.fn(),
  addMessage: jest.fn(),
  updateMessage: jest.fn(),
  deleteMessage: jest.fn(),
  setTypingStatus: jest.fn(),
  setUserOnline: jest.fn(),
  setFilters: jest.fn(),
  getConversation: jest.fn(),
  getMessages: jest.fn(),
  getUnreadCount: jest.fn(() => 0),
};

export const mockSocketContext = {
  socket: {
    on: jest.fn(),
    off: jest.fn(),
    emit: jest.fn(),
    connected: true,
    id: 'mock-socket-id',
  },
  isConnected: true,
};
