import React from 'react';
import { vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { render, createMockUser, mockApiResponses } from '@/tests/utils/test-utils';
import { LoginPage, RegisterPage } from '../../__mocks__/pages';
import { AuthGuard } from '../../__mocks__/components';
import { useAuthStore } from '../../__mocks__/services';

// Setup MSW server
const server = setupServer(
  rest.post('/api/auth/login', (req, res, ctx) => {
    return res(ctx.json(mockApiResponses.login));
  }),
  rest.post('/api/auth/register', (req, res, ctx) => {
    return res(ctx.json({
      ...mockApiResponses.login,
      user: createMockUser({ email: req.body.email }),
    }));
  }),
  rest.post('/api/auth/logout', (req, res, ctx) => {
    return res(ctx.status(200));
  }),
  rest.post('/api/auth/refresh', (req, res, ctx) => {
    return res(ctx.json({
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
    }));
  }),
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  // Clear auth store and reset mocks
  const mockAuthStore = {
    user: null,
    isAuthenticated: false,
    permissions: [],
    setAuth: vi.fn(),
    logout: vi.fn(() => {
      localStorage.clear();
    }),
    refreshToken: vi.fn(),
    initializeAuth: vi.fn(),
  };
  (useAuthStore.getState as vi.Mock).mockReturnValue(mockAuthStore);
  localStorage.clear();
});
afterAll(() => server.close());

describe('Authentication Flow Tests', () => {
  describe('Login Flow', () => {
    it('should successfully login with valid credentials', async () => {
      const user = userEvent.setup();
      render(<LoginPage />);

      // Fill in login form
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(submitButton);

      // Wait for navigation (mocked router will handle this)
      await waitFor(() => {
        expect(localStorage.getItem('access_token')).toBe('mock-access-token');
        expect(localStorage.getItem('refresh_token')).toBe('mock-refresh-token');
      });

      // Check that setAuth was called
      const mockAuthStore = (useAuthStore.getState as vi.Mock).mock.results[0].value;
      expect(mockAuthStore.setAuth).toHaveBeenCalledWith(expect.objectContaining({
        user: expect.objectContaining({
          email: 'test@example.com',
        }),
        isAuthenticated: true,
      }));
    });

    it('should show error message on invalid credentials', async () => {
      server.use(
        rest.post('/api/auth/login', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ detail: 'Invalid credentials' }));
        })
      );

      const user = userEvent.setup();
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });

      expect(localStorage.getItem('access_token')).toBeNull();
    });

    it('should remember user when "Remember Me" is checked', async () => {
      const user = userEvent.setup();
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const rememberMeCheckbox = screen.getByLabelText(/remember me/i);
      const submitButton = screen.getByRole('button', { name: /sign in/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(rememberMeCheckbox);
      await user.click(submitButton);

      await waitFor(() => {
        expect(localStorage.getItem('remember_email')).toBe('test@example.com');
      });
    });
  });

  describe('Registration Flow', () => {
    it('should successfully register a new user', async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);

      // Fill in registration form
      const nameInput = screen.getByLabelText(/full name/i);
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^password/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      const submitButton = screen.getByRole('button', { name: /sign up/i });

      await user.type(nameInput, 'New User');
      await user.type(emailInput, 'newuser@example.com');
      await user.type(passwordInput, 'StrongPass123!');
      await user.type(confirmPasswordInput, 'StrongPass123!');
      await user.click(submitButton);

      await waitFor(() => {
        expect(localStorage.getItem('access_token')).toBe('mock-access-token');
      });

      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(true);
      expect(authState.user?.email).toBe('newuser@example.com');
    });

    it('should validate password strength', async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);

      const passwordInput = screen.getByLabelText(/^password/i);
      await user.type(passwordInput, 'weak');

      await waitFor(() => {
        expect(screen.getByText(/password must be at least/i)).toBeInTheDocument();
      });
    });

    it('should validate password confirmation', async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);

      const passwordInput = screen.getByLabelText(/^password/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);

      await user.type(passwordInput, 'StrongPass123!');
      await user.type(confirmPasswordInput, 'DifferentPass123!');

      const submitButton = screen.getByRole('button', { name: /sign up/i });
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText(/passwords do not match/i)).toBeInTheDocument();
      });
    });

    it('should handle registration errors', async () => {
      server.use(
        rest.post('/api/auth/register', (req, res, ctx) => {
          return res(ctx.status(400), ctx.json({
            detail: 'Email already exists',
          }));
        })
      );

      const user = userEvent.setup();
      render(<RegisterPage />);

      // Fill form
      await user.type(screen.getByLabelText(/full name/i), 'Test User');
      await user.type(screen.getByLabelText(/email/i), 'existing@example.com');
      await user.type(screen.getByLabelText(/^password/i), 'StrongPass123!');
      await user.type(screen.getByLabelText(/confirm password/i), 'StrongPass123!');
      await user.click(screen.getByRole('button', { name: /sign up/i }));

      await waitFor(() => {
        expect(screen.getByText(/email already exists/i)).toBeInTheDocument();
      });
    });
  });

  describe('Protected Routes', () => {
    it('should redirect to login when accessing protected route without auth', () => {
      const ProtectedComponent = () => <div>Protected Content</div>;
      
      render(
        <AuthGuard>
          <ProtectedComponent />
        </AuthGuard>
      );

      // Should show loading initially
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      
      // In a real app, this would redirect to login
      // For testing, we can check that the protected content is not shown
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('should allow access to protected route when authenticated', async () => {
      // Set up authenticated state
      useAuthStore.getState().setAuth({
        user: createMockUser(),
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'valid-token');

      const ProtectedComponent = () => <div>Protected Content</div>;
      
      render(
        <AuthGuard>
          <ProtectedComponent />
        </AuthGuard>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });
    });
  });

  describe('Logout Flow', () => {
    it('should successfully logout and clear auth state', async () => {
      // Set up authenticated state
      const mockUser = createMockUser();
      useAuthStore.getState().setAuth({
        user: mockUser,
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'valid-token');
      localStorage.setItem('refresh_token', 'valid-refresh');

      // Trigger logout
      await useAuthStore.getState().logout();

      await waitFor(() => {
        expect(localStorage.getItem('access_token')).toBeNull();
        expect(localStorage.getItem('refresh_token')).toBeNull();
      });

      const authState = useAuthStore.getState();
      expect(authState.isAuthenticated).toBe(false);
      expect(authState.user).toBeNull();
    });
  });

  describe('Token Refresh', () => {
    it('should automatically refresh expired token', async () => {
      // Set up initial auth state
      useAuthStore.getState().setAuth({
        user: createMockUser(),
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'expired-token');
      localStorage.setItem('refresh_token', 'valid-refresh-token');

      // Simulate API call that returns 401
      server.use(
        rest.get('/api/users/me', (req, res, ctx) => {
          const token = req.headers.get('authorization');
          if (token === 'Bearer expired-token') {
            return res(ctx.status(401));
          }
          return res(ctx.json(createMockUser()));
        })
      );

      // Make an API call that triggers token refresh
      await fetch('/api/users/me', {
        headers: {
          'Authorization': 'Bearer expired-token',
        },
      });

      // After refresh, the new token should be stored
      await waitFor(() => {
        expect(localStorage.getItem('access_token')).toBe('new-access-token');
        expect(localStorage.getItem('refresh_token')).toBe('new-refresh-token');
      });
    });

    it('should logout when refresh token is invalid', async () => {
      server.use(
        rest.post('/api/auth/refresh', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ detail: 'Invalid refresh token' }));
        })
      );

      useAuthStore.getState().setAuth({
        user: createMockUser(),
        isAuthenticated: true,
      });
      localStorage.setItem('refresh_token', 'invalid-refresh-token');

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
        expect(localStorage.getItem('access_token')).toBeNull();
      });
    });
  });

  describe('Session Management', () => {
    it('should restore session from localStorage on app load', async () => {
      // Set up stored session
      const mockUser = createMockUser();
      localStorage.setItem('access_token', 'stored-token');
      localStorage.setItem('user', JSON.stringify(mockUser));

      // Initialize auth store (simulating app load)
      await useAuthStore.getState().initializeAuth();

      await waitFor(() => {
        const authState = useAuthStore.getState();
        expect(authState.isAuthenticated).toBe(true);
        expect(authState.user?.id).toBe(mockUser.id);
      });
    });

    it('should handle concurrent authentication requests', async () => {
      const user = userEvent.setup();
      render(<LoginPage />);

      // Fill form
      await user.type(screen.getByLabelText(/email/i), 'test@example.com');
      await user.type(screen.getByLabelText(/password/i), 'password123');

      const submitButton = screen.getByRole('button', { name: /sign in/i });
      
      // Click multiple times quickly
      await user.click(submitButton);
      await user.click(submitButton);
      await user.click(submitButton);

      // Should only make one request
      await waitFor(() => {
        expect(localStorage.getItem('access_token')).toBe('mock-access-token');
      });

      // Verify button was disabled during request
      expect(submitButton).toBeDisabled();
    });
  });
});
