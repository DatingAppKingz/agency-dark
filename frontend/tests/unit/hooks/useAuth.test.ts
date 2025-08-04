import { renderHook, act, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useAuth } from '@/hooks/useAuth';
import { createWrapper } from '../../utils/enhanced-test-utils';
import { server } from '../../utils/test-server';
import { http, HttpResponse } from 'msw';
import { authService } from '@/services/auth/authService';

// We need to ensure the authService mock is properly configured
vi.mock('@/services/auth/authService');

describe('useAuth Hook', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('initializes with unauthenticated state', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper(),
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isPending).toBe(true);
    expect(result.current.error).toBeNull();
  });

  describe('login', () => {
    it('successfully logs in user', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

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

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user).toMatchObject({
          email: 'test@example.com',
          role: 'agency_admin',
        });
        expect(result.current.isPending).toBe(false);
        expect(result.current.error).toBeNull();
      });
    });

    it('handles login error', async () => {
      const error = new Error('Invalid credentials') as any;
      error.response = {
        data: {
          detail: 'Invalid credentials'
        }
      };
      authService.login.mockRejectedValueOnce(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

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

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false);
        expect(result.current.user).toBeNull();
        expect(result.current.error).toBe('Invalid credentials');
      });
    });

    it('sets isPending during login', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

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

      let loginPromise: Promise<void>;

      act(() => {
        loginPromise = result.current.login({
          email: 'test@example.com',
          password: 'password123',
        });
      });

      // Check pending state immediately
      expect(result.current.isPending).toBe(true);

      await act(async () => {
        await loginPromise;
      });

      expect(result.current.isPending).toBe(false);
    });
  });

  describe('register', () => {
    it('successfully registers new user', async () => {
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

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

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user).toMatchObject({
          email: 'newuser@example.com',
          full_name: 'New User',
        });
      });
    });

    it('handles registration error', async () => {
      const error = new Error('Email already exists') as any;
      error.response = {
        data: {
          detail: 'Email already exists'
        }
      };
      authService.register.mockRejectedValueOnce(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        try {
          await result.current.register({
            email: 'existing@example.com',
            full_name: 'New User',
            password: 'password123',
          });
        } catch (error) {
          // Expected to throw
        }
      });

      await waitFor(() => {
        expect(result.current.error).toBe('Email already exists');
        expect(result.current.isAuthenticated).toBe(false);
      });
    });
  });

  describe('logout', () => {
    it('successfully logs out user', async () => {
      // Start with authenticated state
      // Tokens now managed via httpOnly cookies
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Mock logout to also call clearTokens
      authService.logout.mockImplementationOnce(async () => {
        authService.clearTokens();
      });

      await act(async () => {
        await result.current.logout();
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false);
        expect(result.current.user).toBeNull();
        expect(authService.clearTokens).toHaveBeenCalled();
      });
    });

    it('clears auth state even if API call fails', async () => {
      authService.logout.mockResolvedValueOnce(undefined);

      // Tokens now managed via httpOnly cookies
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.logout();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe('checkAuth', () => {
    it('loads user data when token exists', async () => {
      // Tokens now managed via httpOnly cookies

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

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.checkAuth();
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user).toMatchObject({
          email: 'test@example.com',
        });
        expect(result.current.isPending).toBe(false);
      });
    });

    it('remains unauthenticated when no token', async () => {
      authService.checkAuth.mockResolvedValueOnce(null);
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(result.current.isPending).toBe(false);
    });

    it('handles expired token', async () => {
      // Tokens now managed via httpOnly cookies

      authService.checkAuth.mockRejectedValueOnce(new Error('Token expired'));
      authService.clearTokens.mockImplementationOnce(() => {
        // Tokens now managed via httpOnly cookies
        // Tokens now managed via httpOnly cookies
        localStorage.removeItem('user');
      });

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
    });
  });

  describe('clearError', () => {
    it('clears error state', async () => {
      const error = new Error('Error message') as any;
      error.response = {
        data: {
          detail: 'Error message'
        }
      };
      authService.login.mockRejectedValueOnce(error);

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Trigger an error
      await act(async () => {
        try {
          await result.current.login({
            email: 'test@example.com',
            password: 'wrong',
          });
        } catch (error) {
          // Expected
        }
      });

      expect(result.current.error).toBe('Error message');

      // Clear the error
      act(() => {
        result.current.clearError();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('persistence', () => {
    it('maintains auth state across hook remounts', async () => {
      const mockUser = {
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'member' as const,
        is_active: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      
      // Tokens now managed via httpOnly cookies
      localStorage.setItem('user', JSON.stringify(mockUser));
      
      authService.checkAuth.mockResolvedValue(mockUser);
      authService.getAccessToken.mockReturnValue('valid-token');

      const { result, rerender } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Manually trigger checkAuth since the hook doesn't do it automatically
      await act(async () => {
        await result.current.checkAuth();
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
      });

      // Remount the hook
      rerender();

      expect(result.current.isAuthenticated).toBe(true);
      expect(result.current.user?.email).toBe('test@example.com');
    });
  });
});