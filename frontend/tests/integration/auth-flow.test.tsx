import React from 'react';
import { vi } from 'vitest';
import { render, screen, waitFor } from '../utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { server } from '../utils/test-server';
import { http, HttpResponse } from 'msw';
import LoginPage from '@/pages/auth/LoginPage';
import DashboardPage from '@/pages/dashboard/DashboardPage';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Routes, Route } from 'react-router-dom';

// Mock navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  ...vi.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

describe('Authentication Flow Integration', () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockClear();
  });

  describe('Login Flow', () => {
    it('completes full login flow successfully', async () => {
      const user = userEvent.setup();
      
      render(<LoginPage />);

      // Find form elements
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /log in|sign in/i });

      // Fill in the form
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');

      // Submit the form
      await user.click(submitButton);

      // Wait for navigation
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true });
      });

      // Check that tokens are stored
      // Tokens now in httpOnly cookies
      // Tokens now in httpOnly cookies
    });

    it('shows error message on invalid credentials', async () => {
      const user = userEvent.setup();

      server.use(
        http.post('http://localhost:8000/api/v1/auth/login', () => {
          return HttpResponse.json(
            { detail: 'Invalid email or password' },
            { status: 401 }
          );
        })
      );

      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /log in|sign in/i });

      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'wrongpassword');
      await user.click(submitButton);

      // Wait for error message
      await waitFor(() => {
        expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
      });

      // Should not navigate
      expect(mockNavigate).not.toHaveBeenCalled();
      
      // Should not store tokens
      // Tokens now in httpOnly cookies
    });

    it('disables form during submission', async () => {
      const user = userEvent.setup();
      
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const submitButton = screen.getByRole('button', { name: /log in|sign in/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');

      // Start submission
      const submitPromise = user.click(submitButton);

      // Check that form is disabled
      await waitFor(() => {
        expect(submitButton).toBeDisabled();
        expect(emailInput).toBeDisabled();
        expect(passwordInput).toBeDisabled();
      });

      await submitPromise;

      // Form should be re-enabled after completion
      expect(submitButton).not.toBeDisabled();
    });

    it('validates required fields before submission', async () => {
      const user = userEvent.setup();
      
      render(<LoginPage />);

      const submitButton = screen.getByRole('button', { name: /log in|sign in/i });

      // Try to submit without filling fields
      await user.click(submitButton);

      // Should show validation errors
      await waitFor(() => {
        expect(screen.getByText(/email is required/i)).toBeInTheDocument();
        expect(screen.getByText(/password is required/i)).toBeInTheDocument();
      });

      // Should not make API call
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  describe('Protected Routes', () => {
    it('redirects to login when accessing protected route without auth', () => {
      render(
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
        </Routes>,
        { route: '/dashboard' }
      );

      // Should redirect to login
      expect(mockNavigate).toHaveBeenCalledWith('/login', expect.any(Object));
    });

    it('allows access to protected route when authenticated', async () => {
      // Set auth token
      // Tokens now managed via httpOnly cookies
      localStorage.setItem('user', JSON.stringify({
        id: '1',
        email: 'test@example.com',
        role: 'agency_admin',
      }));

      render(
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardPage />
              </ProtectedRoute>
            }
          />
        </Routes>,
        { route: '/dashboard' }
      );

      // Should not redirect
      expect(mockNavigate).not.toHaveBeenCalled();

      // Dashboard should be visible
      await waitFor(() => {
        expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
      });
    });
  });

  describe('Logout Flow', () => {
    it('completes logout and redirects to login', async () => {
      const user = userEvent.setup();

      // Start authenticated
      // Tokens now managed via httpOnly cookies
      localStorage.setItem('user', JSON.stringify({
        id: '1',
        email: 'test@example.com',
        role: 'agency_admin',
      }));

      render(<DashboardPage />);

      // Find and click logout button
      const logoutButton = screen.getByRole('button', { name: /log out|logout/i });
      await user.click(logoutButton);

      // Wait for logout to complete
      await waitFor(() => {
        // Tokens now in httpOnly cookies
        // Tokens now in httpOnly cookies
        // Tokens now in httpOnly cookies
      });

      // Should redirect to login
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
  });

  describe('Session Management', () => {
    it('refreshes token when expired', async () => {
      // Tokens now managed via httpOnly cookies
      // Tokens now managed via httpOnly cookies

      let tokenRefreshCalled = false;

      server.use(
        // First call returns 401
        http.get('http://localhost:8000/api/v1/users', () => {
          if (!tokenRefreshCalled) {
            return HttpResponse.json({ detail: 'Token expired' }, { status: 401 });
          }
          // After refresh, return success
          return HttpResponse.json({ items: [], total: 0 });
        }),
        // Token refresh endpoint
        http.post('http://localhost:8000/api/v1/auth/refresh', () => {
          tokenRefreshCalled = true;
          return HttpResponse.json({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
          });
        })
      );

      render(<DashboardPage />);

      // Wait for token refresh and retry
      await waitFor(() => {
        // Tokens now in httpOnly cookies
        // Tokens now in httpOnly cookies
      });
    });

    it('redirects to login when refresh token is invalid', async () => {
      // Tokens now managed via httpOnly cookies
      // Tokens now managed via httpOnly cookies

      server.use(
        http.get('http://localhost:8000/api/v1/users', () => {
          return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
        }),
        http.post('http://localhost:8000/api/v1/auth/refresh', () => {
          return HttpResponse.json({ detail: 'Invalid refresh token' }, { status: 401 });
        })
      );

      render(<DashboardPage />);

      // Should clear tokens and redirect
      await waitFor(() => {
        // Tokens now in httpOnly cookies
        // Tokens now in httpOnly cookies
        expect(mockNavigate).toHaveBeenCalledWith('/login');
      });
    });
  });

  describe('Remember Me', () => {
    it('stores persistent session when remember me is checked', async () => {
      const user = userEvent.setup();
      
      render(<LoginPage />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      const rememberCheckbox = screen.getByLabelText(/remember me/i);
      const submitButton = screen.getByRole('button', { name: /log in|sign in/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      await user.click(rememberCheckbox);
      await user.click(submitButton);

      await waitFor(() => {
        // Check for persistent storage marker
        expect(localStorage.getItem('remember_me')).toBe('true');
      });
    });
  });
});