import { screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render } from '../../utils/test-utils';
import LoginPage from '@/pages/auth/LoginPage';
import RegisterPage from '@/pages/auth/RegisterPage';
import { server } from '../../utils/test-server';
import { rest } from 'msw';

// Enable API mocking
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Authentication Flow', () => {
  describe('Login', () => {
    it('should render login form', () => {
      render(<LoginPage />);
      
      expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });

    it('should show validation errors for empty fields', async () => {
      const user = userEvent.setup();
      render(<LoginPage />);
      
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/email is required/i)).toBeInTheDocument();
        expect(screen.getByText(/password is required/i)).toBeInTheDocument();
      });
    });

    it('should show validation error for invalid email', async () => {
      const user = userEvent.setup();
      render(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      await user.type(emailInput, 'invalid-email');
      
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
      });
    });

    it('should successfully login with valid credentials', async () => {
      const user = userEvent.setup();
      const mockPush = vi.fn();
      
      render(<LoginPage />, {
        router: { push: mockPush },
      });
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'password123');
      
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/dashboard');
      });
    });

    it('should handle login errors', async () => {
      server.use(
        rest.post('*/auth/login', (req, res, ctx) => {
          return res(
            ctx.status(401),
            ctx.json({ detail: 'Invalid credentials' })
          );
        })
      );

      const user = userEvent.setup();
      render(<LoginPage />);
      
      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/password/i);
      
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'wrongpassword');
      
      const submitButton = screen.getByRole('button', { name: /sign in/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
      });
    });
  });

  describe('Registration', () => {
    it('should render registration form', () => {
      render(<RegisterPage />);
      
      expect(screen.getByRole('heading', { name: /create account/i })).toBeInTheDocument();
      expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^password/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/role/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
    });

    it('should validate password match', async () => {
      const user = userEvent.setup();
      render(<RegisterPage />);
      
      const passwordInput = screen.getByLabelText(/^password/i);
      const confirmPasswordInput = screen.getByLabelText(/confirm password/i);
      
      await user.type(passwordInput, 'password123');
      await user.type(confirmPasswordInput, 'password456');
      
      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/passwords must match/i)).toBeInTheDocument();
      });
    });

    it('should successfully register with valid data', async () => {
      const user = userEvent.setup();
      const mockPush = vi.fn();
      
      render(<RegisterPage />, {
        router: { push: mockPush },
      });
      
      await user.type(screen.getByLabelText(/full name/i), 'Test User');
      await user.type(screen.getByLabelText(/email/i), 'test@example.com');
      await user.type(screen.getByLabelText(/^password/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');
      
      // Select role
      const roleSelect = screen.getByLabelText(/role/i);
      await user.click(roleSelect);
      await user.click(screen.getByRole('option', { name: /model/i }));
      
      // Accept terms
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i });
      await user.click(termsCheckbox);
      
      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/auth/login');
      });
    });

    it('should handle registration errors', async () => {
      server.use(
        rest.post('*/auth/register', (req, res, ctx) => {
          return res(
            ctx.status(400),
            ctx.json({ detail: 'Email already exists' })
          );
        })
      );

      const user = userEvent.setup();
      render(<RegisterPage />);
      
      await user.type(screen.getByLabelText(/full name/i), 'Test User');
      await user.type(screen.getByLabelText(/email/i), 'existing@example.com');
      await user.type(screen.getByLabelText(/^password/i), 'password123');
      await user.type(screen.getByLabelText(/confirm password/i), 'password123');
      
      const roleSelect = screen.getByLabelText(/role/i);
      await user.click(roleSelect);
      await user.click(screen.getByRole('option', { name: /model/i }));
      
      const termsCheckbox = screen.getByRole('checkbox', { name: /terms/i });
      await user.click(termsCheckbox);
      
      const submitButton = screen.getByRole('button', { name: /create account/i });
      await user.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/email already exists/i)).toBeInTheDocument();
      });
    });
  });

  describe('Protected Routes', () => {
    it('should redirect to login when accessing protected route without auth', () => {
      const mockPush = vi.fn();
      
      // Mock unauthenticated state
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          isAuthenticated: false,
          user: null,
        }),
      }));
      
      // Try to render a protected page
      render(<div>Protected Content</div>, {
        router: {
          pathname: '/dashboard',
          push: mockPush,
        },
      });
      
      expect(mockPush).toHaveBeenCalledWith('/auth/login');
    });
  });
});
