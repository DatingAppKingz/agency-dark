// Mock services for testing

export const apiClient = {
  get: jest.fn((url, config) => {
    if (url.includes('/test-headers')) {
      return Promise.resolve({ data: { success: true }, status: 200 });
    }
    if (url.includes('/files/file-agency-2')) {
      return Promise.resolve({ status: 403 });
    }
    if (url.includes('/search')) {
      return Promise.resolve({
        data: {
          results: [
            { type: 'model', id: 'model-1', agency_id: 'agency-1' },
            { type: 'chat', id: 'chat-1', agency_id: 'agency-1' },
          ],
        },
      });
    }
    return Promise.resolve({ data: {}, status: 200 });
  }),
  post: jest.fn(() => Promise.resolve({ data: {}, status: 200 })),
  put: jest.fn((url) => {
    if (url.includes('/models/model-agency-2')) {
      return Promise.resolve({ status: 403 });
    }
    return Promise.resolve({ data: {}, status: 200 });
  }),
  delete: jest.fn(() => Promise.resolve({ data: {}, status: 200 })),
};

export const authService = {
  login: jest.fn((credentials) => {
    if (credentials.email === 'wrong@example.com') {
      return Promise.reject(new Error('Invalid credentials'));
    }
    return Promise.resolve({
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      user: {
        id: '1',
        email: credentials.email,
        name: 'Test User',
        role: 'AGENCY_ADMIN',
      },
    });
  }),
  refreshToken: jest.fn(() =>
    Promise.resolve({
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
    })
  ),
  logout: jest.fn(() => Promise.resolve()),
};

export const userService = {
  getUsers: jest.fn(() =>
    Promise.resolve({
      data: [{ id: '1', email: 'test@example.com' }],
      total: 1,
      page: 1,
      limit: 10,
    })
  ),
  createUser: jest.fn((userData) =>
    Promise.resolve({
      id: '2',
      ...userData,
    })
  ),
  updateUser: jest.fn((id, updates) =>
    Promise.resolve({
      id,
      ...updates,
    })
  ),
  searchUsers: jest.fn(() => Promise.resolve({ data: [] })),
};

export const modelService = {
  getModels: jest.fn(() =>
    Promise.resolve({
      data: [{ id: 'model-1', name: 'Test Model', agency_id: 'agency-1' }],
      total: 1,
    })
  ),
  getModelById: jest.fn((id) =>
    Promise.resolve({
      id,
      name: 'Test Model',
      earnings: { total: 10000, monthly: 2000 },
      subscribers: 150,
    })
  ),
  updateModelStatus: jest.fn((id, status) =>
    Promise.resolve({
      id,
      status,
    })
  ),
};

export class SocketManager {
  static instance: SocketManager | null = null;
  
  static getInstance() {
    if (!this.instance) {
      this.instance = new SocketManager();
    }
    return this.instance;
  }
  
  connect = jest.fn();
  disconnect = jest.fn();
  on = jest.fn();
  off = jest.fn();
  emit = jest.fn();
  sendMessage = jest.fn();
  joinConversation = jest.fn();
  leaveConversation = jest.fn();
  updatePresence = jest.fn();
}

export const useAuthStore = {
  getState: jest.fn(() => ({
    user: null,
    isAuthenticated: false,
    permissions: [],
    setAuth: jest.fn(),
    logout: jest.fn(),
    refreshToken: jest.fn(),
    initializeAuth: jest.fn(),
  })),
};