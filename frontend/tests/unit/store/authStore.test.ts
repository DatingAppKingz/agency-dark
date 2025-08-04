import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { useAuthStore } from '@/store/authStore';
import { server } from '../../utils/test-server';
import { http, HttpResponse } from 'msw';
import { createMockUser } from '../../utils/mock-factories';
import { authService } from '@/services/auth/authService';

// Mock the authService
vi.mock('@/services/auth/authService');

describe('AuthStore', () => {
  beforeEach(() => {
    // Reset store state
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isPending: true,
      error: null,
    });
    localStorage.clear();
    vi.clearAllMocks();
  });

  describe('Initial state', () => {
    it('starts with default values', () => {
      const { result } = renderHook(() => useAuthStore());

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isPending).toBe(true);
      expect(result.current.error).toBeNull();
    });
  });

  describe('login action', () => {
    it('updates state on successful login', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.login.mockResolvedValueOnce({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'agency_admin',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });

      await act(async () => {
        await result.current.login({
          email: 'test@example.com',
          password: 'password123',
        });
      });

      expect(result.current.user).toMatchObject({
        email: 'test@example.com',
        role: 'agency_admin',
      });
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isPending).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('sets error state on failed login', async () => {
      const { result } = renderHook(() => useAuthStore());

      const error = new Error('Invalid credentials') as any;
      error.response = {
        data: {
          detail: 'Invalid credentials'
        }
      };
      authService.login.mockRejectedValueOnce(error);

      await act(async () => {
        try {
          await result.current.login({
            email: 'wrong@example.com',
            password: 'wrongpassword',
          });
        } catch (error) {
          // Expected to throw
        }
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe('Invalid credentials');
      expect(result.current.isPending).toBe(false);
    });

    it('sets isPending during login process', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.login.mockResolvedValueOnce({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'agency_admin',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });

      const loginPromise = act(async () => {
        const promise = result.current.login({
          email: 'test@example.com',
          password: 'password123',
        });

        // Check pending state immediately after starting login
        expect(result.current.isPending).toBe(true);

        await promise;
      });

      await loginPromise;

      expect(result.current.isPending).toBe(false);
    });
  });

  describe('register action', () => {
    it('updates state on successful registration', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.register.mockResolvedValueOnce({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: {
          id: '2',
          email: 'newuser@example.com',
          full_name: 'New User',
          role: 'member',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });

      await act(async () => {
        await result.current.register({
          email: 'newuser@example.com',
          full_name: 'New User',
          password: 'password123',
        });
      });

      expect(result.current.user).toMatchObject({
        email: 'newuser@example.com',
        full_name: 'New User',
      });
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('handles registration errors', async () => {
      const { result } = renderHook(() => useAuthStore());

      const error = new Error('Email already exists') as any;
      error.response = {
        data: {
          detail: 'Email already exists'
        }
      };
      authService.register.mockRejectedValueOnce(error);

      await act(async () => {
        try {
          await result.current.register({
            email: 'existing@example.com',
            full_name: 'Test User',
            password: 'password123',
          });
        } catch (error) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Email already exists');
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('logout action', () => {
    it('clears auth state on logout', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.logout.mockResolvedValueOnce(undefined);

      // Set initial authenticated state
      act(() => {
        useAuthStore.setState({
          user: createMockUser(),
          isAuthenticated: true,
          isPending: false,
          error: null,
        });
      });

      localStorage.setItem('auth_token', 'mock-token');
      localStorage.setItem('refresh_token', 'mock-refresh');

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });

    it.skip('clears state even if API call fails', async () => {
      const { result } = renderHook(() => useAuthStore());
      
      // Configure mock to throw error
      authService.logout = vi.fn().mockRejectedValueOnce('Network error');

      act(() => {
        useAuthStore.setState({
          user: createMockUser(),
          isAuthenticated: true,
          isPending: false,
        });
      });

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('checkAuth action', () => {
    it('loads user when valid token exists', async () => {
      const { result } = renderHook(() => useAuthStore());

      const mockUser = {
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'agency_admin' as const,
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      authService.checkAuth.mockResolvedValueOnce(mockUser);
      authService.getAccessToken.mockReturnValueOnce('valid-token');

      localStorage.setItem('auth_token', 'valid-token');

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toMatchObject({
        email: 'test@example.com',
      });
      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.isPending).toBe(false);
    });

    it('remains unauthenticated with no token', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.checkAuth.mockResolvedValueOnce(null);

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isPending).toBe(false);
    });

    it('clears auth on 401 response', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.checkAuth.mockRejectedValueOnce(new Error('Unauthorized'));

      localStorage.setItem('auth_token', 'invalid-token');

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('clearError action', () => {
    it('clears error state', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        useAuthStore.setState({ error: 'Some error' });
      });

      expect(result.current.error).toBe('Some error');

      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('State persistence', () => {
    it('persists user data in localStorage', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.login.mockResolvedValueOnce({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'agency_admin',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      });

      await act(async () => {
        await result.current.login({
          email: 'test@example.com',
          password: 'password123',
        });
      });

      expect(result.current.user?.email).toBe('test@example.com');
    });

    it('recovers state from localStorage on init', async () => {
      const mockUser = createMockUser();
      localStorage.setItem('user', JSON.stringify(mockUser));
      localStorage.setItem('auth_token', 'stored-token');

      authService.checkAuth.mockResolvedValueOnce(mockUser);
      authService.getAccessToken.mockReturnValueOnce('stored-token');

      const { result } = renderHook(() => useAuthStore());

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toMatchObject({
        email: mockUser.email,
      });
      expect(result.current.isAuthenticated).toBe(true);
    });
  });

  describe('Concurrent requests', () => {
    it('handles multiple login attempts correctly', async () => {
      const { result } = renderHook(() => useAuthStore());

      authService.login
        .mockResolvedValueOnce({
          access_token: 'token1',
          refresh_token: 'refresh1',
          user: {
            id: '1',
            email: 'user1@example.com',
            full_name: 'User 1',
            role: 'member',
            is_active: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        })
        .mockResolvedValueOnce({
          access_token: 'token2',
          refresh_token: 'refresh2',
          user: {
            id: '2',
            email: 'user2@example.com',
            full_name: 'User 2',
            role: 'member',
            is_active: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        });

      // Attempt multiple logins simultaneously
      const promises = [
        result.current.login({ email: 'user1@example.com', password: 'pass1' }),
        result.current.login({ email: 'user2@example.com', password: 'pass2' }),
      ];

      await act(async () => {
        await Promise.allSettled(promises);
      });

      // Both logins should complete, last one sets the state
      expect(result.current.user).toBeTruthy();
      expect(result.current.isAuthenticated).toBe(true);
    });
  });
});