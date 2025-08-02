import React from 'react';
import { render, screen, waitFor, within } from '@/tests/utils/enhanced-test-utils';
import userEvent from '@testing-library/user-event';
import { server } from '@/tests/utils/test-server';
import { rest } from 'msw';
import App from '@/App';

// Mock for navigation tracking
const navigationHistory: string[] = [];

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => (path: string) => {
    navigationHistory.push(path);
  },
}));

describe('User Journey E2E Test', () => {
  beforeEach(() => {
    localStorage.clear();
    navigationHistory.length = 0;
  });

  it('completes full user journey from login to task completion', async () => {
    const user = userEvent.setup();
    
    // Render the full app
    render(<App />);

    // Step 1: Login
    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), 'admin@agency.com');
    await user.type(screen.getByLabelText(/password/i), 'admin123');
    await user.click(screen.getByRole('button', { name: /log in/i }));

    // Wait for dashboard to load
    await waitFor(() => {
      expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
    }, { timeout: 5000 });

    // Step 2: Navigate to Models page
    const modelsLink = screen.getByRole('link', { name: /models/i });
    await user.click(modelsLink);

    await waitFor(() => {
      expect(screen.getByText(/models management/i)).toBeInTheDocument();
    });

    // Step 3: Create a new model
    const addModelButton = screen.getByRole('button', { name: /add model|new model/i });
    await user.click(addModelButton);

    // Fill model form
    const dialog = screen.getByRole('dialog');
    const nameInput = within(dialog).getByLabelText(/name|username/i);
    const emailInput = within(dialog).getByLabelText(/email/i);
    
    await user.type(nameInput, 'newmodel');
    await user.type(emailInput, 'newmodel@example.com');
    
    // Submit form
    const saveButton = within(dialog).getByRole('button', { name: /save|create/i });
    await user.click(saveButton);

    // Wait for success message
    await waitFor(() => {
      expect(screen.getByText(/model created successfully/i)).toBeInTheDocument();
    });

    // Step 4: Navigate to Analytics
    const analyticsLink = screen.getByRole('link', { name: /analytics/i });
    await user.click(analyticsLink);

    await waitFor(() => {
      expect(screen.getByText(/analytics overview/i)).toBeInTheDocument();
    });

    // Verify analytics data is displayed
    expect(screen.getByText(/revenue/i)).toBeInTheDocument();
    expect(screen.getByText(/\$10,000/)).toBeInTheDocument();
    expect(screen.getByText(/active users/i)).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();

    // Step 5: Upload media
    const mediaLink = screen.getByRole('link', { name: /media/i });
    await user.click(mediaLink);

    await waitFor(() => {
      expect(screen.getByText(/media library/i)).toBeInTheDocument();
    });

    const uploadButton = screen.getByRole('button', { name: /upload/i });
    await user.click(uploadButton);

    // Mock file upload
    const file = new File(['test'], 'test-image.jpg', { type: 'image/jpeg' });
    const input = screen.getByLabelText(/drag & drop/i).parentElement?.querySelector('input[type="file"]');
    
    if (input) {
      await user.upload(input as HTMLInputElement, file);
    }

    // Wait for upload to complete
    await waitFor(() => {
      expect(screen.getByText('test-image.jpg')).toBeInTheDocument();
    });

    // Step 6: Check notifications
    const notificationBell = screen.getByRole('button', { name: /notifications/i });
    await user.click(notificationBell);

    // Verify notification dropdown
    await waitFor(() => {
      expect(screen.getByText(/no new notifications/i)).toBeInTheDocument();
    });

    // Step 7: Update settings
    const settingsLink = screen.getByRole('link', { name: /settings/i });
    await user.click(settingsLink);

    await waitFor(() => {
      expect(screen.getByText(/account settings/i)).toBeInTheDocument();
    });

    // Change language preference
    const languageSelect = screen.getByLabelText(/language/i);
    await user.click(languageSelect);
    await user.click(screen.getByRole('option', { name: /spanish/i }));

    // Save settings
    const saveSettingsButton = screen.getByRole('button', { name: /save changes/i });
    await user.click(saveSettingsButton);

    await waitFor(() => {
      expect(screen.getByText(/settings saved/i)).toBeInTheDocument();
    });

    // Step 8: Logout
    const userMenu = screen.getByRole('button', { name: /user menu/i });
    await user.click(userMenu);

    const logoutButton = screen.getByRole('menuitem', { name: /log out/i });
    await user.click(logoutButton);

    // Should return to login page
    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument();
    });

    // Verify all auth data is cleared
    expect(localStorage.getItem('auth_token')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
  });

  describe('Error Handling Journey', () => {
    it('handles network errors gracefully throughout the journey', async () => {
      const user = userEvent.setup();
      
      render(<App />);

      // Login successfully first
      await user.type(screen.getByLabelText(/email/i), 'admin@agency.com');
      await user.type(screen.getByLabelText(/password/i), 'admin123');
      await user.click(screen.getByRole('button', { name: /log in/i }));

      await waitFor(() => {
        expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
      });

      // Simulate network error for next request
      server.use(
        rest.get('http://localhost:8000/api/v1/models', (req, res) => {
          return res.networkError('Network error');
        })
      );

      // Try to navigate to models
      const modelsLink = screen.getByRole('link', { name: /models/i });
      await user.click(modelsLink);

      // Should show error message
      await waitFor(() => {
        expect(screen.getByText(/network error|connection error/i)).toBeInTheDocument();
      });

      // Should have retry option
      const retryButton = screen.getByRole('button', { name: /retry/i });
      expect(retryButton).toBeInTheDocument();

      // Fix the network and retry
      server.use(
        rest.get('http://localhost:8000/api/v1/models', (req, res, ctx) => {
          return res(ctx.json({ items: [], total: 0 }));
        })
      );

      await user.click(retryButton);

      // Should load successfully
      await waitFor(() => {
        expect(screen.queryByText(/network error/i)).not.toBeInTheDocument();
        expect(screen.getByText(/models management/i)).toBeInTheDocument();
      });
    });
  });

  describe('Role-Based Journey', () => {
    it('shows different features based on user role', async () => {
      const user = userEvent.setup();

      // Mock login as regular member
      server.use(
        rest.post('http://localhost:8000/api/v1/auth/login', (req, res, ctx) => {
          return res(
            ctx.json({
              access_token: 'member-token',
              refresh_token: 'member-refresh',
              user: {
                id: '2',
                email: 'member@example.com',
                username: 'member',
                role: 'member',
                is_active: true,
              },
            })
          );
        })
      );

      render(<App />);

      // Login as member
      await user.type(screen.getByLabelText(/email/i), 'member@example.com');
      await user.type(screen.getByLabelText(/password/i), 'member123');
      await user.click(screen.getByRole('button', { name: /log in/i }));

      await waitFor(() => {
        expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
      });

      // Member should not see admin features
      expect(screen.queryByRole('link', { name: /users management/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: /api keys/i })).not.toBeInTheDocument();
      
      // But should see their own features
      expect(screen.getByRole('link', { name: /my profile/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /messages/i })).toBeInTheDocument();
    });
  });

  describe('Persistence Journey', () => {
    it('maintains user session across page refreshes', async () => {
      const user = userEvent.setup();
      
      const { unmount } = render(<App />);

      // Login
      await user.type(screen.getByLabelText(/email/i), 'admin@agency.com');
      await user.type(screen.getByLabelText(/password/i), 'admin123');
      await user.click(screen.getByRole('button', { name: /log in/i }));

      await waitFor(() => {
        expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
      });

      // Navigate to a specific page
      const modelsLink = screen.getByRole('link', { name: /models/i });
      await user.click(modelsLink);

      await waitFor(() => {
        expect(screen.getByText(/models management/i)).toBeInTheDocument();
      });

      // Simulate page refresh by unmounting and remounting
      unmount();
      
      // Re-render app
      render(<App />);

      // Should still be authenticated and on the same page
      await waitFor(() => {
        expect(screen.getByText(/models management/i)).toBeInTheDocument();
        expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument(); // Not on login page
      });
    });
  });
});