import { User } from '@/types/auth';
import { Media } from '@/types/media';
import { Message, Conversation } from '@/types/chat';

// User factory
export const createMockUser = (overrides?: Partial<User>): User => ({
  id: '1',
  email: 'test@example.com',
  username: 'testuser',
  role: 'member',
  is_active: true,
  is_email_verified: true,
  two_factor_enabled: false,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

// Admin user factory
export const createMockAdminUser = (overrides?: Partial<User>): User => 
  createMockUser({
    role: 'agency_admin',
    email: 'admin@example.com',
    username: 'admin',
    ...overrides,
  });

// Model user factory
export const createMockModelUser = (overrides?: Partial<User>): User => 
  createMockUser({
    role: 'model',
    email: 'model@example.com',
    username: 'model1',
    ...overrides,
  });

// Media factory
export const createMockMedia = (overrides?: Partial<Media>): Media => ({
  id: '1',
  filename: 'test-image.jpg',
  original_filename: 'test-image.jpg',
  file_path: '/media/test-image.jpg',
  file_size: 1024000,
  mime_type: 'image/jpeg',
  media_type: 'image' as any,
  width: 1920,
  height: 1080,
  status: 'ready' as any,
  tags: [],
  visibility: 'private' as any,
  password_protected: false,
  agency_id: 'agency-1',
  uploaded_by: 'user-1',
  is_nsfw: false,
  view_count: 0,
  download_count: 0,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

// Message factory
export const createMockMessage = (overrides?: Partial<Message>): Message => ({
  id: '1',
  conversation_id: 'conv-1',
  sender_id: 'user-1',
  sender_type: 'model',
  content: 'Test message',
  message_type: 'text',
  created_at: new Date().toISOString(),
  ...overrides,
});

// Conversation factory
export const createMockConversation = (overrides?: Partial<Conversation>): Conversation => ({
  id: 'conv-1',
  model_id: 'model-1',
  fan_id: 'fan-1',
  status: 'active',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  last_message_at: new Date().toISOString(),
  unread_count: 0,
  is_priority: false,
  ...overrides,
});

// Analytics data factory
export const createMockAnalyticsData = () => ({
  revenue: {
    total: 10000,
    change: 15.5,
    period: 'month',
    chart_data: [
      { date: '2024-01-01', value: 8000 },
      { date: '2024-01-02', value: 8500 },
      { date: '2024-01-03', value: 9000 },
      { date: '2024-01-04', value: 10000 },
    ],
  },
  users: {
    total: 150,
    active: 120,
    new: 25,
    chart_data: [
      { date: '2024-01-01', active: 100, new: 10 },
      { date: '2024-01-02', active: 110, new: 15 },
      { date: '2024-01-03', active: 115, new: 20 },
      { date: '2024-01-04', active: 120, new: 25 },
    ],
  },
  messages: {
    total: 5000,
    sent: 4500,
    received: 500,
    response_rate: 90,
  },
});

// Form data factories
export const createMockLoginData = () => ({
  email: 'test@example.com',
  password: 'password123',
  remember_me: false,
});

export const createMockRegisterData = () => ({
  email: 'newuser@example.com',
  username: 'newuser',
  password: 'password123',
  password_confirm: 'password123',
  terms_accepted: true,
});

// API response factories
export const createMockPaginatedResponse = <T>(items: T[], total?: number) => ({
  items,
  total: total || items.length,
  page: 1,
  pages: Math.ceil((total || items.length) / 10),
  has_more: false,
});

export const createMockApiError = (status: number, detail: string) => ({
  response: {
    status,
    data: { detail },
  },
});

// File mock factory
export const createMockFile = (name = 'test.jpg', type = 'image/jpeg', size = 1024): File => {
  const file = new File(['test'], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
};