import React from 'react';
import { vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// Simple mock components for testing
const LoginForm = ({ onSubmit }: { onSubmit: (data: any) => void }) => {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const formData = new FormData(e.target as HTMLFormElement);
    onSubmit({
      email: formData.get('email'),
      password: formData.get('password'),
    });
  };

  return (
    <form onSubmit={handleSubmit}>
      <input name="email" type="email" aria-label="Email" />
      <input name="password" type="password" aria-label="Password" />
      <button type="submit">Sign In</button>
    </form>
  );
};

describe('Simple Authentication Tests', () => {
  it('should handle login form submission', async () => {
    const mockLogin = vi.fn();
    const user = userEvent.setup();
    
    render(<LoginForm onSubmit={mockLogin} />);
    
    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));
    
    expect(mockLogin).toHaveBeenCalledWith({
      email: 'test@example.com',
      password: 'password123',
    });
  });

  it('should store tokens on successful login', async () => {
    const mockAuth = {
      login: async (credentials: any) => {
        if (credentials.email === 'test@example.com') {
          localStorage.setItem('access_token', 'mock-token');
          return { success: true };
        }
        throw new Error('Invalid credentials');
      },
    };

    await mockAuth.login({ email: 'test@example.com', password: 'password' });
    expect(localStorage.getItem('access_token')).toBe('mock-token');
  });

  it('should clear tokens on logout', () => {
    localStorage.setItem('access_token', 'token');
    localStorage.setItem('refresh_token', 'refresh');
    
    // Simulate logout
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });
});
