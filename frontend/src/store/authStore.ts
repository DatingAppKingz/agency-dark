import { create } from 'zustand';
import { authService } from '@/services/auth/authService';
import { User, LoginCredentials, RegisterData } from '@/types/auth';

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isPending: boolean;
  error: string | null;
  accessToken: string | null;
  refreshToken: string | null;
  permissions: string[];
  
  // Actions
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  clearError: () => void;
  setAuth: (data: { user: User; accessToken: string; refreshToken: string }) => void;
  refreshToken: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isPending: true,
  error: null,
  accessToken: null,
  refreshToken: null,
  permissions: [],

  login: async (credentials) => {
    set({ isPending: true, error: null });
    try {
      const response = await authService.login(credentials);
      set({
        user: response.user,
        isAuthenticated: true,
        isPending: false,
      });
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Login failed',
        isPending: false,
        isAuthenticated: false,
        user: null,
      });
      throw error;
    }
  },

  register: async (data) => {
    set({ isPending: true, error: null });
    try {
      const response = await authService.register(data);
      set({
        user: response.user,
        isAuthenticated: true,
        isPending: false,
      });
    } catch (error: any) {
      set({
        error: error.response?.data?.detail || 'Registration failed',
        isPending: false,
        isAuthenticated: false,
        user: null,
      });
      throw error;
    }
  },

  logout: async () => {
    set({ isPending: true });
    try {
      await authService.logout();
    } finally {
      set({
        user: null,
        isAuthenticated: false,
        isPending: false,
        error: null,
      });
    }
  },

  checkAuth: async () => {
    set({ isPending: true });
    try {
      const user = await authService.checkAuth();
      if (user) {
        // Also need to get the token from the API
        const token = authService.getAccessToken();
        if (token) {
          set({
            user,
            isAuthenticated: true,
            isPending: false,
          });
        } else {
          // Try to get a new token
          await authService.refreshToken();
          set({
            user,
            isAuthenticated: true,
            isPending: false,
          });
        }
      } else {
        set({
          user: null,
          isAuthenticated: false,
          isPending: false,
        });
      }
    } catch (error) {
      set({
        user: null,
        isAuthenticated: false,
        isPending: false,
      });
    }
  },

  clearError: () => {
    set({ error: null });
  },

  setAuth: (data) => {
    set({
      user: data.user,
      isAuthenticated: true,
      isPending: false,
      accessToken: data.accessToken,
      refreshToken: data.refreshToken,
      error: null,
    });
    // Tokens are now stored in httpOnly cookies by the backend
  },

  refreshToken: async () => {
    try {
      const response = await authService.refreshToken();
      // Tokens are automatically updated in cookies by the backend
      // We just need to update the user state if needed
      set({
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
      });
    } catch (error) {
      // If refresh fails, logout
      set({
        user: null,
        isAuthenticated: false,
        isPending: false,
        accessToken: null,
        refreshToken: null,
        permissions: [],
      });
      throw error;
    }
  },
}));
