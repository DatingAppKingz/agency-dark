import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { server } from '../utils/test-server';
import { http, HttpResponse } from 'msw';
import { createMockUser } from '../utils/mock-factories';
import { useAuthStore } from '@/store/authStore';
import LoginPage from '@/pages/auth/LoginPage';

// Mock the router
vi.mock('react-router-dom', () => ({
  ...vi.importActual('react-router-dom'),
  useNavigate: () => vi.fn(),
  useLocation: () => ({ 
    pathname: '/', 
    state: null,
    search: '',
    hash: ''
  }),
  Link: ({ children, to }: any) => <a href={to}>{children}</a>,
}));

describe('Authentication Integration Tests', () => {
  beforeEach(() => {
    // Clear auth store
    useAuthStore.getState().logout();
    localStorage.clear();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Login Flow', () => {
    it('should successfully login with valid credentials', async () => {
      const user = userEvent.setup();
      const mockUser = createMockUser({ email: 'test@example.com' });

      server.use(
        http.post('/api/v1/auth/login', async ({ request }) => {
          const body = await request.json() as any;
          if (body.email === 'test@example.com' && body.password === 'password123') {
            return HttpResponse.json({
              access_token: 'mock-access-token',
              refresh_token: 'mock-refresh-token',
              user: mockUser,
            });
          }
          return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
        })
      );

      render(<LoginPage />);

      // Fill in login form
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in|login/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      // Wait for login to complete
      // Note: Tokens are now stored in httpOnly cookies, not localStorage
      await waitFor(() => {
        const authState = useAuthStore.getState();
        expect(authState.isAuthenticated).toBe(true);
        expect(authState.user?.email).toBe('test@example.com');
      });
    });

    it('should show error message on invalid credentials', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('/api/v1/auth/login', () => {
          return HttpResponse.json(
            { detail: 'Invalid credentials' },
            { status: 401 }
          );
        })
      );

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in|login/i });

      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });

      // Tokens now in httpOnly cookies
    });
  });

  describe('Logout Flow', () => {
    it('should successfully logout and clear auth state', async () => {
      // Set up authenticated state
      const mockUser = createMockUser();
      useAuthStore.getState().setAuth({
        user: mockUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      localStorage.setItem('access_token', 'valid-token');
      // Tokens now managed via httpOnly cookies

      server.use(
        http.post('/api/v1/auth/logout', () => {
          return HttpResponse.json({ success: true });
        })
      );

      // Trigger logout
      await useAuthStore.getState().logout();

      await waitFor(() => {
        // Tokens are now cleared via httpOnly cookies by the backend
        const authState = useAuthStore.getState();
        expect(authState.isAuthenticated).toBe(false);
      });

      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(false);
      expect(authState.user).toBeNull();
    });
  });

  describe('Token Refresh', () => {
    it('should automatically refresh expired token', async () => {
      server.use(
        http.post('/api/v1/auth/refresh', () => {
          return HttpResponse.json({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
          });
        })
      );

      // Set up initial auth state
      useAuthStore.getState().setAuth({
        user: createMockUser(),
        accessToken: 'expired-token',
        refreshToken: 'valid-refresh-token',
      });
      // Tokens now managed via httpOnly cookies

      // Trigger refresh
      await useAuthStore.getState().refreshToken();

      await waitFor(() => {
        // Tokens are now managed via httpOnly cookies
        const authState = useAuthStore.getState();
        expect(authState.accessToken).toBe('new-access-token');
        expect(authState.refreshToken).toBe('new-refresh-token');
      });
    });

    it('should logout when refresh token is invalid', async () => {
      server.use(
        http.post('/api/v1/auth/refresh', () => {
          return HttpResponse.json(
            { detail: 'Invalid refresh token' },
            { status: 401 }
          );
        })
      );

      useAuthStore.getState().setAuth({
        user: createMockUser(),
        accessToken: 'expired-token',
        refreshToken: 'invalid-refresh-token',
      });
      // Tokens now managed via httpOnly cookies

      // Attempt to refresh token
      try {
        await useAuthStore.getState().refreshToken();
      } catch (error) {
        // Expected to fail
      }

      await waitFor(() => {
        const authState = useAuthStore.getState();
        expect(authState.isAuthenticated).toBe(false);
        expect(authState.user).toBeNull();
        // Tokens now in httpOnly cookies
      });
    });
  });
});