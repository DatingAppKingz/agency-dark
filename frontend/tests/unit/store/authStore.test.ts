import { renderHook, act } from '@testing-library/react';
import { vi } from 'vitest';
import { useAuthStore } from '@/store/authStore';
import { server } from '@/tests/utils/test-server';
import { rest } from 'msw';
import { createMockUser } from '@/tests/utils/mock-factories';

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

      server.use(
        rest.post('http://localhost:8000/api/v1/auth/login', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid credentials' })
          );
        })
      );

      await expect(
        act(async () => {
          await result.current.login({
            email: 'wrong@example.com',
            password: 'wrong',
          });
        })
      ).rejects.toThrow();

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.error).toBe('Invalid credentials');
      expect(result.current.isPending).toBe(false);
    });

    it('sets isPending during login process', async () => {
      const { result } = renderHook(() => useAuthStore());

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

      await act(async () => {
        await result.current.register({
          email: 'newuser@example.com',
          username: 'newuser',
          password: 'password123',
          password_confirm: 'password123',
        });
      });

      expect(result.current.user).toMatchObject({
        email: 'newuser@example.com',
        username: 'newuser',
      });
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('handles registration errors', async () => {
      const { result } = renderHook(() => useAuthStore());

      server.use(
        rest.post('http://localhost:8000/api/v1/auth/register', (req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({ detail: 'Username already taken' })
          );
        })
      );

      await expect(
        act(async () => {
          await result.current.register({
            email: 'test@example.com',
            username: 'taken',
            password: 'password123',
            password_confirm: 'password123',
          });
        })
      ).rejects.toThrow();

      expect(result.current.error).toBe('Username already taken');
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('logout action', () => {
    it('clears auth state on logout', async () => {
      const { result } = renderHook(() => useAuthStore());

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
      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('clears state even if API call fails', async () => {
      const { result } = renderHook(() => useAuthStore());

      server.use(
        rest.post('http://localhost:8000/api/v1/auth/logout', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      act(() => {
        useAuthStore.setState({
          user: createMockUser(),
          isAuthenticated: true,
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

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.isPending).toBe(false);
    });

    it('clears auth on 401 response', async () => {
      const { result } = renderHook(() => useAuthStore());

      localStorage.setItem('auth_token', 'invalid-token');

      server.use(
        rest.get('http://localhost:8000/api/v1/auth/me', (req, res, ctx) => {
          return res(ctx.status(401));
        })
      );

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
      expect(localStorage.getItem('auth_token')).toBeNull();
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

      await act(async () => {
        await result.current.login({
          email: 'test@example.com',
          password: 'password123',
        });
      });

      const storedUser = localStorage.getItem('user');
      expect(storedUser).toBeTruthy();
      
      const parsedUser = JSON.parse(storedUser!);
      expect(parsedUser.email).toBe('test@example.com');
    });

    it('recovers state from localStorage on init', () => {
      const mockUser = createMockUser();
      localStorage.setItem('user', JSON.stringify(mockUser));
      localStorage.setItem('auth_token', 'stored-token');

      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.checkAuth();
      });

      // State should be recovered from localStorage
      expect(result.current.user).toMatchObject({
        email: mockUser.email,
      });
    });
  });

  describe('Concurrent requests', () => {
    it('handles multiple login attempts correctly', async () => {
      const { result } = renderHook(() => useAuthStore());

      // Attempt multiple logins simultaneously
      const promises = [
        result.current.login({ email: 'user1@example.com', password: 'pass1' }),
        result.current.login({ email: 'user2@example.com', password: 'pass2' }),
      ];

      await act(async () => {
        await Promise.allSettled(promises);
      });

      // Last successful login should win
      expect(result.current.user?.email).toBe('test@example.com');
      expect(result.current.isAuthenticated).toBe(true);
    });
  });
});