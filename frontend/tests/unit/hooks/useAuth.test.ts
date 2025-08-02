import { renderHook, act, waitFor } from '@testing-library/react';
import { useAuth } from '@/hooks/useAuth';
import { createWrapper } from '@/tests/utils/enhanced-test-utils';
import { server } from '@/tests/utils/test-server';
import { rest } from 'msw';

describe('useAuth Hook', () => {
  beforeEach(() => {
    localStorage.clear();
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
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/login', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid credentials' })
          );
        })
      );

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

      await act(async () => {
        await result.current.register({
          email: 'newuser@example.com',
          username: 'newuser',
          password: 'password123',
          password_confirm: 'password123',
        });
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(true);
        expect(result.current.user).toMatchObject({
          email: 'newuser@example.com',
          username: 'newuser',
        });
      });
    });

    it('handles registration error', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/register', (req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({ detail: 'Email already exists' })
          );
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        try {
          await result.current.register({
            email: 'existing@example.com',
            username: 'newuser',
            password: 'password123',
            password_confirm: 'password123',
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
      localStorage.setItem('auth_token', 'mock-token');
      
      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      // Simulate authenticated state
      act(() => {
        result.current.checkAuth();
      });

      await act(async () => {
        await result.current.logout();
      });

      await waitFor(() => {
        expect(result.current.isAuthenticated).toBe(false);
        expect(result.current.user).toBeNull();
        expect(localStorage.getItem('auth_token')).toBeNull();
      });
    });

    it('clears auth state even if API call fails', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/logout', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      localStorage.setItem('auth_token', 'mock-token');
      
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
      localStorage.setItem('auth_token', 'valid-token');

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
      localStorage.setItem('auth_token', 'expired-token');

      server.use(
        rest.get('http://localhost:8000/api/v1/auth/me', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ detail: 'Token expired' }));
        })
      );

      const { result } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.checkAuth();
      });

      expect(result.current.isAuthenticated).toBe(false);
      expect(result.current.user).toBeNull();
      expect(localStorage.getItem('auth_token')).toBeNull();
    });
  });

  describe('clearError', () => {
    it('clears error state', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/login', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ detail: 'Error message' }));
        })
      );

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
      localStorage.setItem('auth_token', 'valid-token');
      localStorage.setItem('user', JSON.stringify({
        id: '1',
        email: 'test@example.com',
        role: 'member',
      }));

      const { result, rerender } = renderHook(() => useAuth(), {
        wrapper: createWrapper(),
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