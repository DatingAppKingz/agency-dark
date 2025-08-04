import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { server } from '../utils/test-server';
import { http, HttpResponse } from 'msw';
import { createMockUser } from '../utils/mock-factories';
import { useAuthStore } from '@/store/authStore';
import { hasPermission, hasRole, hasAnyPermission, hasAllPermissions } from '@/utils/rbac';
import React from 'react';

// Mock permission component
const PermissionGate: React.FC<{
  permission?: string;
  permissions?: string[];
  requireAll?: boolean;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}> = ({ permission, permissions, requireAll = true, children, fallback = null }) => {
  const user = useAuthStore.getState().user;
  const userPermissions = useAuthStore.getState().permissions || [];

  let hasAccess = false;
  if (permission) {
    hasAccess = hasPermission(userPermissions, permission);
  } else if (permissions) {
    hasAccess = requireAll 
      ? hasAllPermissions(userPermissions, permissions)
      : hasAnyPermission(userPermissions, permissions);
  }

  return hasAccess ? <>{children}</> : <>{fallback}</>;
};

// Mock role guard component
const RoleGuard: React.FC<{
  roles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}> = ({ roles, children, fallback = null }) => {
  const user = useAuthStore.getState().user;
  const hasAccess = user && hasRole(user, roles);
  return hasAccess ? <>{children}</> : <>{fallback}</>;
};

// Helper function to get permissions based on role
const getPermissionsForRole = (role: string): string[] => {
  const permissions: Record<string, string[]> = {
    super_admin: [
      'users:read', 'users:write', 'users:delete',
      'models:read', 'models:write', 'models:delete',
      'analytics:read', 'analytics:write',
      'settings:read', 'settings:write',
      'billing:read', 'billing:write',
      'agencies:read', 'agencies:write', 'agencies:delete',
    ],
    agency_admin: [
      'users:read', 'users:write',
      'models:read', 'models:write', 'models:delete',
      'analytics:read',
      'settings:read', 'settings:write',
      'billing:read',
    ],
    agency_manager: [
      'users:read',
      'models:read', 'models:write',
      'analytics:read',
      'settings:read',
    ],
    model: [
      'analytics:read',
      'settings:read',
      'chats:read', 'chats:write',
    ],
    chatter: [
      'chats:read', 'chats:write',
      'models:read',
    ],
  };
  return permissions[role] || [];
};

describe('Role-Based Access Control Tests', () => {
  beforeEach(() => {
    // Clear auth store
    useAuthStore.getState().logout();
    localStorage.clear();
  });

  describe('Permission Gates', () => {
    it('should show content when user has required permission', async () => {
      // Set up user with admin role
      const adminUser = createMockUser({ role: 'agency_admin' });
      useAuthStore.getState().setAuth({
        user: adminUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      useAuthStore.setState({ permissions: getPermissionsForRole('agency_admin') });

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
      const modelUser = createMockUser({ role: 'model' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      useAuthStore.setState({ permissions: getPermissionsForRole('model') });

      render(
        <PermissionGate permission="users:write">
          <div>Admin Only Content</div>
        </PermissionGate>
      );

      expect(screen.queryByText('Admin Only Content')).not.toBeInTheDocument();
    });

    it('should handle multiple permissions with AND logic', () => {
      const managerUser = createMockUser({ role: 'agency_manager' });
      useAuthStore.getState().setAuth({
        user: managerUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      useAuthStore.setState({ permissions: getPermissionsForRole('agency_manager') });

      render(
        <PermissionGate permissions={['models:read', 'models:write']} requireAll>
          <div>Manager Content</div>
        </PermissionGate>
      );

      expect(screen.getByText('Manager Content')).toBeInTheDocument();
    });

    it('should handle multiple permissions with OR logic', () => {
      const chatterUser = createMockUser({ role: 'chatter' });
      useAuthStore.getState().setAuth({
        user: chatterUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      useAuthStore.setState({ permissions: getPermissionsForRole('chatter') });

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
      const adminUser = createMockUser({ role: 'agency_admin' });
      useAuthStore.getState().setAuth({
        user: adminUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });

      render(
        <RoleGuard roles={['agency_admin', 'super_admin']}>
          <div>Admin Dashboard</div>
        </RoleGuard>
      );

      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
    });

    it('should deny access for non-matching role', () => {
      const modelUser = createMockUser({ role: 'model' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });

      render(
        <RoleGuard roles={['agency_admin']}>
          <div>Admin Only</div>
        </RoleGuard>
      );

      expect(screen.queryByText('Admin Only')).not.toBeInTheDocument();
    });

    it('should handle fallback component', () => {
      const modelUser = createMockUser({ role: 'model' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });

      render(
        <RoleGuard 
          roles={['agency_admin']} 
          fallback={<div>Access Denied</div>}
        >
          <div>Admin Only</div>
        </RoleGuard>
      );

      expect(screen.queryByText('Admin Only')).not.toBeInTheDocument();
      expect(screen.getByText('Access Denied')).toBeInTheDocument();
    });
  });

  describe('API-Level Permission Checks', () => {
    it('should handle 403 Forbidden responses', async () => {
      const modelUser = createMockUser({ role: 'model' });
      useAuthStore.getState().setAuth({
        user: modelUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      useAuthStore.setState({ permissions: getPermissionsForRole('model') });

      server.use(
        http.delete('/api/v1/users/:id', () => {
          return HttpResponse.json(
            {
              detail: 'Insufficient permissions',
              required_permission: 'users:delete',
            },
            { status: 403 }
          );
        })
      );

      const response = await fetch('/api/v1/users/1', {
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
      const user = createMockUser({ role: 'model' });
      useAuthStore.getState().setAuth({
        user,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      useAuthStore.setState({ permissions: getPermissionsForRole('model') });

      const { rerender } = render(
        <PermissionGate permission="users:write">
          <div>Admin Feature</div>
        </PermissionGate>
      );

      // Should not see admin feature
      expect(screen.queryByText('Admin Feature')).not.toBeInTheDocument();

      // Update role to AGENCY_ADMIN
      const updatedUser = { ...user, role: 'agency_admin' };
      useAuthStore.getState().setAuth({
        user: updatedUser,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      useAuthStore.setState({ permissions: getPermissionsForRole('agency_admin') });

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
  });

  describe('Hierarchical Permissions', () => {
    it('should inherit permissions from parent roles', () => {
      const superAdmin = createMockUser({ role: 'super_admin' });
      useAuthStore.getState().setAuth({
        user: superAdmin,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });
      const superAdminPerms = getPermissionsForRole('super_admin');
      const agencyAdminPerms = getPermissionsForRole('agency_admin');
      
      // Super admin should have all agency admin permissions
      agencyAdminPerms.forEach(perm => {
        expect(superAdminPerms).toContain(perm);
      });
    });
  });
});