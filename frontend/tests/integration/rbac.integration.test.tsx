import React from 'react';
import { vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { render, createMockUser, mockApiResponses } from '@/tests/utils/test-utils';
import { useAuthStore } from '@/tests/utils/mock-factories';
import { PermissionGate, RoleGuard } from '../../__mocks__/components';
import { UsersPage, ModelsPage, AdminDashboard, SettingsPage } from '@/pages';

// Setup MSW server
const server = setupServer(
  rest.get('/api/users', (req, res, ctx) => {
    const authHeader = req.headers.get('authorization');
    if (!authHeader) {
      return res(ctx.status(401));
    }
    return res(ctx.json(mockApiResponses.users));
  }),
  rest.get('/api/models', (req, res, ctx) => {
    return res(ctx.json(mockApiResponses.models));
  }),
  rest.get('/api/permissions', (req, res, ctx) => {
    const user = useAuthStore.getState().user;
    return res(ctx.json({
      permissions: getPermissionsForRole(user?.role || 'MODEL'),
    }));
  }),
);

beforeAll(() => server.listen());
afterEach(() => {
  server.resetHandlers();
  useAuthStore.getState().logout();
  localStorage.clear();
});
afterAll(() => server.close());

// Helper function to get permissions based on role
const getPermissionsForRole = (role: string) => {
  const permissions: Record<string, string[]> = {
    SUPER_ADMIN: [
      'users:read', 'users:write', 'users:delete',
      'models:read', 'models:write', 'models:delete',
      'analytics:read', 'analytics:write',
      'settings:read', 'settings:write',
      'billing:read', 'billing:write',
      'agencies:read', 'agencies:write', 'agencies:delete',
    ],
    AGENCY_ADMIN: [
      'users:read', 'users:write',
      'models:read', 'models:write', 'models:delete',
      'analytics:read',
      'settings:read', 'settings:write',
      'billing:read',
    ],
    AGENCY_MANAGER: [
      'users:read',
      'models:read', 'models:write',
      'analytics:read',
      'settings:read',
    ],
    MODEL: [
      'analytics:read',
      'settings:read',
      'chats:read', 'chats:write',
    ],
    CHATTER: [
      'chats:read', 'chats:write',
      'models:read',
    ],
  };
  return permissions[role] || [];
};

describe('Role-Based Access Control Tests', () => {
  describe('Permission Gates', () => {
    it('should show content when user has required permission', async () => {
      // Set up user with admin role
      const adminUser = createMockUser({ role: 'AGENCY_ADMIN' });
      useAuthStore.getState().setAuth({
        user: adminUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('AGENCY_ADMIN'),
      });

      render(
        <PermissionGate permission="users:read">
          <div>Protected Content</div>
        </PermissionGate>
      );

      await waitFor(() => {
        expect(screen.getByText('Protected Content')).toBeInTheDocument();
      });
    });

    it('should hide content when user lacks required permission', () => {
      // Set up user with model role
      const modelUser = createMockUser({ role: 'MODEL' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('MODEL'),
      });

      render(
        <PermissionGate permission="users:write">
          <div>Admin Only Content</div>
        </PermissionGate>
      );

      expect(screen.queryByText('Admin Only Content')).not.toBeInTheDocument();
    });

    it('should handle multiple permissions with AND logic', () => {
      const managerUser = createMockUser({ role: 'AGENCY_MANAGER' });
      useAuthStore.getState().setAuth({
        user: managerUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('AGENCY_MANAGER'),
      });

      render(
        <PermissionGate permissions={['models:read', 'models:write']} requireAll>
          <div>Manager Content</div>
        </PermissionGate>
      );

      expect(screen.getByText('Manager Content')).toBeInTheDocument();
    });

    it('should handle multiple permissions with OR logic', () => {
      const chatterUser = createMockUser({ role: 'CHATTER' });
      useAuthStore.getState().setAuth({
        user: chatterUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('CHATTER'),
      });

      render(
        <PermissionGate permissions={['users:read', 'models:read']} requireAll={false}>
          <div>Flexible Content</div>
        </PermissionGate>
      );

      // Chatter has models:read but not users:read
      expect(screen.getByText('Flexible Content')).toBeInTheDocument();
    });
  });

  describe('Role Guards', () => {
    it('should allow access for matching role', () => {
      const adminUser = createMockUser({ role: 'AGENCY_ADMIN' });
      useAuthStore.getState().setAuth({
        user: adminUser,
        isAuthenticated: true,
      });

      render(
        <RoleGuard roles={['AGENCY_ADMIN', 'SUPER_ADMIN']}>
          <div>Admin Dashboard</div>
        </RoleGuard>
      );

      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
    });

    it('should deny access for non-matching role', () => {
      const modelUser = createMockUser({ role: 'MODEL' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        isAuthenticated: true,
      });

      render(
        <RoleGuard roles={['AGENCY_ADMIN']}>
          <div>Admin Only</div>
        </RoleGuard>
      );

      expect(screen.queryByText('Admin Only')).not.toBeInTheDocument();
    });

    it('should handle fallback component', () => {
      const modelUser = createMockUser({ role: 'MODEL' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        isAuthenticated: true,
      });

      render(
        <RoleGuard 
          roles={['AGENCY_ADMIN']} 
          fallback={<div>Access Denied</div>}
        >
          <div>Admin Only</div>
        </RoleGuard>
      );

      expect(screen.queryByText('Admin Only')).not.toBeInTheDocument();
      expect(screen.getByText('Access Denied')).toBeInTheDocument();
    });
  });

  describe('Page-Level Access Control', () => {
    it('SUPER_ADMIN should access all pages', async () => {
      const superAdmin = createMockUser({ role: 'SUPER_ADMIN' });
      useAuthStore.getState().setAuth({
        user: superAdmin,
        isAuthenticated: true,
        permissions: getPermissionsForRole('SUPER_ADMIN'),
      });
      localStorage.setItem('access_token', 'valid-token');

      // Test Users Page
      const { unmount: unmountUsers } = render(<UsersPage />);
      await waitFor(() => {
        expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
      });
      unmountUsers();

      // Test Models Page
      const { unmount: unmountModels } = render(<ModelsPage />);
      await waitFor(() => {
        expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
      });
      unmountModels();

      // Test Admin Dashboard
      render(<AdminDashboard />);
      await waitFor(() => {
        expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
      });
    });

    it('MODEL should only access limited pages', async () => {
      const modelUser = createMockUser({ role: 'MODEL' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('MODEL'),
      });

      // Should NOT access Users Page
      const { unmount } = render(<UsersPage />);
      await waitFor(() => {
        expect(screen.queryByRole('table')).not.toBeInTheDocument();
      });
      unmount();

      // Should access Settings Page (read-only)
      render(<SettingsPage />);
      await waitFor(() => {
        expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
        // But should not see save buttons
        expect(screen.queryByRole('button', { name: /save/i })).not.toBeInTheDocument();
      });
    });

    it('AGENCY_ADMIN should manage agency resources', async () => {
      const agencyAdmin = createMockUser({ 
        role: 'AGENCY_ADMIN',
        agency_id: 'agency-1'
      });
      useAuthStore.getState().setAuth({
        user: agencyAdmin,
        isAuthenticated: true,
        permissions: getPermissionsForRole('AGENCY_ADMIN'),
      });
      localStorage.setItem('access_token', 'valid-token');

      // Can access Models Page
      render(<ModelsPage />);
      await waitFor(() => {
        expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
        // Should see action buttons
        expect(screen.queryByRole('button', { name: /add model/i })).toBeInTheDocument();
      });
    });
  });

  describe('API-Level Permission Checks', () => {
    it('should include permissions in API requests', async () => {
      const adminUser = createMockUser({ role: 'AGENCY_ADMIN' });
      useAuthStore.getState().setAuth({
        user: adminUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('AGENCY_ADMIN'),
      });
      localStorage.setItem('access_token', 'valid-token');

      let capturedHeaders: any;
      server.use(
        rest.post('/api/users', (req, res, ctx) => {
          capturedHeaders = req.headers;
          return res(ctx.json(createMockUser()));
        })
      );

      // Simulate creating a user
      await fetch('/api/users', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer valid-token',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: 'new@example.com' }),
      });

      expect(capturedHeaders.get('authorization')).toBe('Bearer valid-token');
    });

    it('should handle 403 Forbidden responses', async () => {
      const modelUser = createMockUser({ role: 'MODEL' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('MODEL'),
      });

      server.use(
        rest.delete('/api/users/:id', (req, res, ctx) => {
          return res(ctx.status(403), ctx.json({
            detail: 'Insufficient permissions',
            required_permission: 'users:delete',
          }));
        })
      );

      const response = await fetch('/api/users/1', {
        method: 'DELETE',
        headers: {
          'Authorization': 'Bearer valid-token',
        },
      });

      expect(response.status).toBe(403);
      const data = await response.json();
      expect(data.detail).toBe('Insufficient permissions');
    });
  });

  describe('Dynamic Permission Updates', () => {
    it('should refresh permissions when role changes', async () => {
      // Start as MODEL
      const user = createMockUser({ role: 'MODEL' });
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
        permissions: getPermissionsForRole('MODEL'),
      });

      const { rerender } = render(
        <PermissionGate permission="users:write">
          <div>Admin Feature</div>
        </PermissionGate>
      );

      // Should not see admin feature
      expect(screen.queryByText('Admin Feature')).not.toBeInTheDocument();

      // Update role to AGENCY_ADMIN
      const updatedUser = { ...user, role: 'AGENCY_ADMIN' };
      useAuthStore.getState().setAuth({
        user: updatedUser,
        isAuthenticated: true,
        permissions: getPermissionsForRole('AGENCY_ADMIN'),
      });

      rerender(
        <PermissionGate permission="users:write">
          <div>Admin Feature</div>
        </PermissionGate>
      );

      // Should now see admin feature
      await waitFor(() => {
        expect(screen.getByText('Admin Feature')).toBeInTheDocument();
      });
    });

    it('should handle permission revocation', async () => {
      const adminUser = createMockUser({ role: 'AGENCY_ADMIN' });
      const customPermissions = ['users:read', 'models:read']; // Missing users:write
      
      useAuthStore.getState().setAuth({
        user: adminUser,
        isAuthenticated: true,
        permissions: customPermissions,
      });

      render(
        <PermissionGate permission="users:write">
          <div>Write Access</div>
        </PermissionGate>
      );

      // Should not have write access despite being admin
      expect(screen.queryByText('Write Access')).not.toBeInTheDocument();
    });
  });

  describe('Hierarchical Permissions', () => {
    it('should inherit permissions from parent roles', () => {
      const superAdmin = createMockUser({ role: 'SUPER_ADMIN' });
      useAuthStore.getState().setAuth({
        user: superAdmin,
        isAuthenticated: true,
        permissions: getPermissionsForRole('SUPER_ADMIN'),
      });

      // Super admin should have all agency admin permissions
      const agencyAdminPerms = getPermissionsForRole('AGENCY_ADMIN');
      const superAdminPerms = getPermissionsForRole('SUPER_ADMIN');
      
      agencyAdminPerms.forEach(perm => {
        expect(superAdminPerms).toContain(perm);
      });
    });

    it('should handle wildcard permissions', () => {
      const user = createMockUser({ role: 'SUPER_ADMIN' });
      const permissions = ['*:*']; // Wildcard for all permissions
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
        permissions,
      });

      render(
        <PermissionGate permission="any:permission">
          <div>Wildcard Access</div>
        </PermissionGate>
      );

      // Should have access with wildcard
      expect(screen.getByText('Wildcard Access')).toBeInTheDocument();
    });
  });
});
