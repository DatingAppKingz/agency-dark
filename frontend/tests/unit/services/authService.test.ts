import { vi } from 'vitest';
import { server } from '../../utils/test-server';
import { http, HttpResponse } from 'msw';
import { createMockUser } from '../../utils/mock-factories';

// Unmock authService and axios for integration tests
vi.unmock('@/services/auth/authService');
vi.unmock('axios');

import { authService } from '@/services/auth/authService';

describe('AuthService', () => {
  beforeEach(() => {
    // Clear any mocked state
    vi.clearAllMocks();
  });

  describe('login', () => {
    it('successfully logs in with valid credentials', async () => {
      const mockUser = createMockUser({ email: 'test@example.com' });
      
      // Mock both the login and me endpoints
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json({
            access_token: 'mock-access-token',
            refresh_token: 'mock-refresh-token',
            token_type: 'bearer',
          });
        }),
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );
      
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
          role: 'model',
        }),
      });

      // Note: Tokens are now stored in httpOnly cookies and not accessible via JS
    });

    it('handles login failure with invalid credentials', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json(
            { detail: 'Invalid email or password' },
            { status: 401 }
          );
        })
      );

      await expect(
        authService.login({
          email: 'wrong@example.com',
          password: 'wrongpassword',
        })
      ).rejects.toThrow();
    });

    it('handles network errors during login', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.error();
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
    it('successfully logs out', async () => {
      await authService.logout();
      
      // The logout endpoint should be called
      // Tokens are cleared on the backend via httpOnly cookies
    });

    it('handles logout errors gracefully', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/logout', () => {
          return new HttpResponse(null, { status: 500 });
        })
      );

      // Should not throw even if API fails
      await expect(authService.logout()).resolves.not.toThrow();
    });
  });

  describe('register', () => {
    it('successfully registers a new user', async () => {
      const mockUser = createMockUser({ email: 'new@example.com' });
      
      server.use(
        http.post('http://localhost:8000/api/v1/auth/register', () => {
          return HttpResponse.json({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
            user: mockUser,
          });
        })
      );

      const result = await authService.register({
        email: 'new@example.com',
        password: 'password123',
        confirmPassword: 'password123',
      });

      expect(result).toMatchObject({
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        user: expect.objectContaining({
          email: 'new@example.com',
        }),
      });
    });

    it('handles registration failure for existing email', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/register', () => {
          return HttpResponse.json(
            { detail: 'Email already registered' },
            { status: 400 }
          );
        })
      );

      await expect(
        authService.register({
          email: 'existing@example.com',
          password: 'password123',
          confirmPassword: 'password123',
        })
      ).rejects.toThrow();
    });
  });

  describe('refreshToken', () => {
    it('successfully refreshes access token', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/refresh', () => {
          return HttpResponse.json({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
          });
        })
      );

      await expect(authService.refreshToken()).resolves.not.toThrow();
    });

    it('handles refresh token failure', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/refresh', () => {
          return HttpResponse.json(
            { detail: 'Invalid refresh token' },
            { status: 401 }
          );
        })
      );

      await expect(authService.refreshToken()).rejects.toThrow();
    });
  });

  describe('getCurrentUser', () => {
    it('returns current user when authenticated', async () => {
      const mockUser = createMockUser();
      
      server.use(
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json(mockUser);
        })
      );

      const user = await authService.checkAuth();

      expect(user).toMatchObject({
        id: mockUser.id,
        email: mockUser.email,
        role: mockUser.role,
      });
    });

    it('returns null when not authenticated', async () => {
      server.use(
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json(
            { detail: 'Not authenticated' },
            { status: 401 }
          );
        })
      );

      const user = await authService.checkAuth();
      expect(user).toBeNull();
    });

    it('handles unauthorized response', async () => {
      server.use(
        http.get('http://localhost:8000/api/v1/auth/me', () => {
          return HttpResponse.json(
            { detail: 'Unauthorized' },
            { status: 403 }
          );
        })
      );

      const user = await authService.checkAuth();
      expect(user).toBeNull();
    });
  });

  describe('Token management', () => {
    it('getAccessToken returns null (tokens in httpOnly cookies)', () => {
      // Tokens are now in httpOnly cookies and not accessible via JS
      expect(authService.getAccessToken()).toBeNull();
    });

    it('getRefreshToken returns null (tokens in httpOnly cookies)', () => {
      // Tokens are now in httpOnly cookies and not accessible via JS
      expect(authService.getRefreshToken()).toBeNull();
    });

    it('isAuthenticated returns false (should rely on auth store)', () => {
      // Since tokens are in httpOnly cookies, this method always returns false
      // The actual auth state should be managed by the auth store
      expect(authService.isAuthenticated()).toBe(false);
    });

    it('setTokens does nothing (tokens managed by backend)', () => {
      // This method is kept for backward compatibility but does nothing
      authService.setTokens('access', 'refresh');
      expect(authService.getAccessToken()).toBeNull();
    });

    it('clearTokens does nothing (tokens managed by backend)', () => {
      // This method is kept for backward compatibility but does nothing
      authService.clearTokens();
      expect(authService.getAccessToken()).toBeNull();
    });
  });

  describe('Password reset', () => {
    it('requests password reset successfully', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/password-reset/request', () => {
          return HttpResponse.json({ message: 'Reset email sent' });
        })
      );

      await expect(
        authService.forgotPassword('test@example.com')
      ).resolves.not.toThrow();
    });

    it('resets password with valid token', async () => {
      server.use(
        http.post('http://localhost:8000/api/v1/auth/password-reset/confirm', () => {
          return HttpResponse.json({ message: 'Password reset successfully' });
        })
      );

      const result = await authService.resetPassword('valid-token', 'newPassword123');
      expect(result).toEqual({ message: 'Password reset successfully' });
    });
  });
});