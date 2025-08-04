import { screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render } from '../utils/enhanced-test-utils';
import LoginPage from '@/pages/auth/LoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { useAuthStore } from '@/store/authStore';

// Mock authService to avoid real API calls
vi.mock('@/services/auth/authService');

describe('Authentication Pages', () => {
  beforeEach(() => {
    // Reset auth state
    useAuthStore.setState({
      user: null,
      isAuthenticated: false,
      isPending: false,
      error: null,
    });
  });

  describe('Login Page', () => {
    it('renders login form elements', () => {
      render(<LoginPage />);
      
      expect(screen.getByRole('heading', { name: /welcome back/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    it('displays validation errors on submit with empty fields', async () => {
      const user = userEvent.setup();
      render(<LoginPage />);
      
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);
      
      // React Hook Form won't show errors for untouched fields
      // Need to interact with fields first
      const emailInput = screen.getByLabelText(/email address/i);
      const passwordInput = screen.getByLabelText(/password/i);
      
      await user.click(emailInput);
      await user.click(passwordInput);
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/invalid email address/i)).toBeInTheDocument();
      });
    });
  });

  describe('Register Page', () => {
    it('renders registration form elements', () => {
      render(<RegisterPage />);
      
      expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/agency name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    });

    it('validates password confirmation match', async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      
      const passwordInput = screen.getByLabelText(/^password/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'password456');
      
      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/passwords don't match/i)).toBeInTheDocument();
      });
    });
  });

  describe('Protected Route', () => {
    it('does not render protected content when not authenticated', () => {
      useAuthStore.setState({
        isAuthenticated: false,
        user: null,
        isPending: false,
      });
      
      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );
      
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('renders protected content when authenticated', () => {
      useAuthStore.setState({
        isAuthenticated: true,
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'agency_admin',
          is_active: true,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        isPending: false,
      });
      
      render(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      );
      
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });
  });
});