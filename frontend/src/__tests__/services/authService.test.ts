import { authService } from '@/services/auth/authService';
import { server } from '@/test-utils/test-server';
import { rest } from 'msw';
import { createMockUser } from '@/test-utils/mock-factories';

describe('AuthService', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
  });

  describe('login', () => {
    it('successfully logs in with valid credentials', async () => {
      const credentials = {
        email: 'test@example.com',
        password: 'password123',
      };

      const result = await authService.login(credentials);

      expect(result).toMatchObject({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: expect.objectContaining({
          email: 'test@example.com',
          role: 'agency_admin',
        }),
      });

      // Check tokens are stored
      expect(localStorage.getItem('auth_token')).toBe('mock-access-token');
      expect(localStorage.getItem('refresh_token')).toBe('mock-refresh-token');
    });

    it('handles login failure with invalid credentials', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/login', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid email or password' })
          );
        })
      );

      await expect(
        authService.login({
          email: 'wrong@example.com',
          password: 'wrongpassword',
        })
      ).rejects.toThrow();

      // Ensure no tokens are stored
      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });

    it('handles network errors during login', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/login', (req, res) => {
          return res.networkError('Network error');
        })
      );

      await expect(
        authService.login({
          email: 'test@example.com',
          password: 'password123',
        })
      ).rejects.toThrow();
    });
  });

  describe('logout', () => {
    it('successfully logs out and clears tokens', async () => {
      // Set initial tokens
      localStorage.setItem('auth_token', 'mock-token');
      localStorage.setItem('refresh_token', 'mock-refresh');
      localStorage.setItem('user', JSON.stringify(createMockUser()));

      await authService.logout();

      // Check all auth data is cleared
      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
      expect(localStorage.getItem('user')).toBeNull();
    });

    it('clears tokens even if API call fails', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/logout', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      localStorage.setItem('auth_token', 'mock-token');
      
      // Should not throw
      await authService.logout();
      
      expect(localStorage.getItem('auth_token')).toBeNull();
    });
  });

  describe('register', () => {
    it('successfully registers a new user', async () => {
      const registerData = {
        email: 'newuser@example.com',
        username: 'newuser',
        password: 'password123',
        password_confirm: 'password123',
      };

      const result = await authService.register(registerData);

      expect(result).toMatchObject({
        access_token: 'mock-access-token',
        user: expect.objectContaining({
          email: 'newuser@example.com',
          username: 'newuser',
        }),
      });

      // Check tokens are stored
      expect(localStorage.getItem('auth_token')).toBe('mock-access-token');
    });

    it('handles registration failure for existing email', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/register', (req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({ detail: 'Email already registered' })
          );
        })
      );

      await expect(
        authService.register({
          email: 'existing@example.com',
          username: 'newuser',
          password: 'password123',
          password_confirm: 'password123',
        })
      ).rejects.toThrow();
    });
  });

  describe('refreshToken', () => {
    it('successfully refreshes access token', async () => {
      localStorage.setItem('refresh_token', 'old-refresh-token');

      server.use(
        rest.post('http://localhost:8000/api/v1/auth/refresh', (req, res, ctx) => {
          return res(
            ctx.json({
              access_token: 'new-access-token',
              refresh_token: 'new-refresh-token',
            })
          );
        })
      );

      const result = await authService.refreshToken();

      expect(result).toEqual({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
      });

      expect(localStorage.getItem('auth_token')).toBe('new-access-token');
      expect(localStorage.getItem('refresh_token')).toBe('new-refresh-token');
    });

    it('handles refresh token failure', async () => {
      localStorage.setItem('refresh_token', 'invalid-refresh-token');

      server.use(
        rest.post('http://localhost:8000/api/v1/auth/refresh', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ detail: 'Invalid refresh token' }));
        })
      );

      await expect(authService.refreshToken()).rejects.toThrow();
      
      // Tokens should be cleared on refresh failure
      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
    });
  });

  describe('getCurrentUser', () => {
    it('returns current user when authenticated', async () => {
      localStorage.setItem('auth_token', 'valid-token');

      const user = await authService.getCurrentUser();

      expect(user).toMatchObject({
        id: '1',
        email: 'test@example.com',
        role: 'agency_admin',
      });
    });

    it('returns null when not authenticated', async () => {
      // No token set
      const user = await authService.getCurrentUser();
      expect(user).toBeNull();
    });

    it('handles unauthorized response', async () => {
      localStorage.setItem('auth_token', 'invalid-token');

      server.use(
        rest.get('http://localhost:8000/api/v1/auth/me', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ detail: 'Unauthorized' }));
        })
      );

      const user = await authService.getCurrentUser();
      expect(user).toBeNull();
    });
  });

  describe('Token management', () => {
    it('getAccessToken returns stored token', () => {
      localStorage.setItem('auth_token', 'test-token');
      expect(authService.getAccessToken()).toBe('test-token');
    });

    it('getRefreshToken returns stored refresh token', () => {
      localStorage.setItem('refresh_token', 'refresh-token');
      expect(authService.getRefreshToken()).toBe('refresh-token');
    });

    it('isAuthenticated returns true when token exists', () => {
      localStorage.setItem('auth_token', 'token');
      expect(authService.isAuthenticated()).toBe(true);
    });

    it('isAuthenticated returns false when no token', () => {
      expect(authService.isAuthenticated()).toBe(false);
    });

    it('setTokens stores both tokens', () => {
      authService.setTokens('access', 'refresh');
      expect(localStorage.getItem('auth_token')).toBe('access');
      expect(localStorage.getItem('refresh_token')).toBe('refresh');
    });

    it('clearTokens removes all auth data', () => {
      localStorage.setItem('auth_token', 'token');
      localStorage.setItem('refresh_token', 'refresh');
      localStorage.setItem('user', 'user-data');

      authService.clearTokens();

      expect(localStorage.getItem('auth_token')).toBeNull();
      expect(localStorage.getItem('refresh_token')).toBeNull();
      expect(localStorage.getItem('user')).toBeNull();
    });
  });

  describe('Password reset', () => {
    it('requests password reset successfully', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/forgot-password', (req, res, ctx) => {
          return res(ctx.json({ message: 'Password reset email sent' }));
        })
      );

      const result = await authService.requestPasswordReset('test@example.com');
      expect(result).toEqual({ message: 'Password reset email sent' });
    });

    it('resets password with valid token', async () => {
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/reset-password', (req, res, ctx) => {
          return res(ctx.json({ message: 'Password reset successful' }));
        })
      );

      const result = await authService.resetPassword('reset-token', 'newpassword123');
      expect(result).toEqual({ message: 'Password reset successful' });
    });
  });
});