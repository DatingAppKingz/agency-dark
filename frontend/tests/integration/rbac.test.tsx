import { screen } from '@testing-library/react';
import { vi } from 'vitest';
import { render } from '../../utils/test-utils';
import DashboardLayout from '@/layouts/DashboardLayout';
import UsersPage from '@/pages/users/UsersPage';
import ModelsPage from '@/pages/models/ModelsPage';
import FinancialPage from '@/pages/financial/FinancialPage';
import AnalyticsPage from '@/pages/analytics/AnalyticsPage';

describe('Role-Based Access Control', () => {
  describe('Navigation Visibility', () => {
    it('should show all menu items for super_admin', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'super_admin' },
        }),
      }));

      render(
        <DashboardLayout>
          <div>Content</div>
        </DashboardLayout>
      );

      expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/users/i)).toBeInTheDocument();
      expect(screen.getByText(/agencies/i)).toBeInTheDocument();
      expect(screen.getByText(/models/i)).toBeInTheDocument();
      expect(screen.getByText(/chat/i)).toBeInTheDocument();
      expect(screen.getByText(/financial/i)).toBeInTheDocument();
      expect(screen.getByText(/analytics/i)).toBeInTheDocument();
      expect(screen.getByText(/settings/i)).toBeInTheDocument();
    });

    it('should show limited menu items for model', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'model' },
        }),
      }));

      render(
        <DashboardLayout>
          <div>Content</div>
        </DashboardLayout>
      );

      expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/chat/i)).toBeInTheDocument();
      expect(screen.getByText(/financial/i)).toBeInTheDocument();
      expect(screen.getByText(/analytics/i)).toBeInTheDocument();
      expect(screen.getByText(/settings/i)).toBeInTheDocument();
      
      // Should not show admin items
      expect(screen.queryByText(/users/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/agencies/i)).not.toBeInTheDocument();
    });

    it('should show appropriate menu items for agency_owner', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'agency_owner' },
        }),
      }));

      render(
        <DashboardLayout>
          <div>Content</div>
        </DashboardLayout>
      );

      expect(screen.getByText(/dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/models/i)).toBeInTheDocument();
      expect(screen.getByText(/chat/i)).toBeInTheDocument();
      expect(screen.getByText(/financial/i)).toBeInTheDocument();
      expect(screen.getByText(/analytics/i)).toBeInTheDocument();
      expect(screen.getByText(/agency settings/i)).toBeInTheDocument();
    });
  });

  describe('Page Access Control', () => {
    it('should deny access to users page for non-admins', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'model' },
        }),
      }));

      render(<UsersPage />);

      expect(screen.getByText(/access denied/i)).toBeInTheDocument();
      expect(screen.getByText(/don't have permission/i)).toBeInTheDocument();
    });

    it('should allow access to users page for super_admin', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'super_admin' },
        }),
      }));

      render(<UsersPage />);

      expect(screen.getByText(/user management/i)).toBeInTheDocument();
      expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
    });

    it('should show role-specific analytics for different users', () => {
      // Test super_admin analytics
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'super_admin' },
        }),
      }));

      const { rerender } = render(<AnalyticsPage />);
      expect(screen.getByText(/platform overview/i)).toBeInTheDocument();

      // Test model analytics
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'model' },
        }),
      }));

      rerender(<AnalyticsPage />);
      expect(screen.getByText(/model performance/i)).toBeInTheDocument();
      expect(screen.queryByText(/platform overview/i)).not.toBeInTheDocument();
    });
  });

  describe('Feature Permissions', () => {
    it('should show create user button only for admins', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'super_admin' },
        }),
      }));

      render(<UsersPage />);
      expect(screen.getByRole('button', { name: /create user/i })).toBeInTheDocument();
    });

    it('should hide financial management for regular members', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'member' },
        }),
      }));

      render(<FinancialPage />);
      expect(screen.queryByText(/payout management/i)).not.toBeInTheDocument();
    });

    it('should show model assignment only for agency roles', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'agency_admin' },
        }),
      }));

      render(<ModelsPage />);
      expect(screen.getByRole('button', { name: /assign model/i })).toBeInTheDocument();
    });
  });

  describe('Data Filtering', () => {
    it('should filter data based on user role and permissions', async () => {
      // Agency owner should only see their agency's data
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'agency_owner',
            agency_id: 'agency123',
          },
        }),
      }));

      render(<ModelsPage />);

      // Wait for data to load
      await screen.findByText(/models/i);

      // Should show filtered data indicator
      expect(screen.getByText(/your agency/i)).toBeInTheDocument();
    });

    it('should show all data for super_admin', async () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'super_admin' },
        }),
      }));

      render(<ModelsPage />);

      await screen.findByText(/all models/i);
      expect(screen.getByText(/all agencies/i)).toBeInTheDocument();
    });
  });

  describe('Action Permissions', () => {
    it('should disable edit actions for read-only roles', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'member' },
        }),
      }));

      render(<ModelsPage />);

      const editButtons = screen.queryAllByRole('button', { name: /edit/i });
      editButtons.forEach(button => {
        expect(button).toBeDisabled();
      });
    });

    it('should enable all actions for admin roles', () => {
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: { ...mockAuthStore.user, role: 'super_admin' },
        }),
      }));

      render(<UsersPage />);

      expect(screen.getByRole('button', { name: /create/i })).toBeEnabled();
      expect(screen.getByRole('button', { name: /export/i })).toBeEnabled();
      expect(screen.getByRole('button', { name: /bulk actions/i })).toBeEnabled();
    });
  });
});
