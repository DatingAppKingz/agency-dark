import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useAuthStore } from '@/store/authStore';
import { hasPermission } from '@/utils/rbac';

// Mock the auth store
vi.mock('@/store/authStore');

describe('Role-Based Access Control', () => {
  describe('Permission Checks', () => {
    it('should grant all permissions to super_admin', () => {
      const mockUser = {
        id: '1',
        email: 'admin@example.com',
        full_name: 'Super Admin',
        role: 'super_admin' as const,
        is_active: true,
        is_verified: true,
        agency_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(hasPermission(mockUser, 'users:read')).toBe(true);
      expect(hasPermission(mockUser, 'users:write')).toBe(true);
      expect(hasPermission(mockUser, 'agencies:manage')).toBe(true);
      expect(hasPermission(mockUser, 'models:manage')).toBe(true);
      expect(hasPermission(mockUser, 'financial:view_all')).toBe(true);
    });

    it('should grant limited permissions to models', () => {
      const mockUser = {
        id: '1',
        email: 'model@example.com',
        full_name: 'Model User',
        role: 'model' as const,
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(hasPermission(mockUser, 'users:read')).toBe(false);
      expect(hasPermission(mockUser, 'users:write')).toBe(false);
      expect(hasPermission(mockUser, 'chat:access')).toBe(true);
      expect(hasPermission(mockUser, 'financial:view_own')).toBe(true);
      expect(hasPermission(mockUser, 'financial:view_all')).toBe(false);
    });

    it('should grant agency management permissions to agency_owner', () => {
      const mockUser = {
        id: '1',
        email: 'owner@agency.com',
        full_name: 'Agency Owner',
        role: 'agency_owner' as const,
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(hasPermission(mockUser, 'models:manage')).toBe(true);
      expect(hasPermission(mockUser, 'financial:view_agency')).toBe(true);
      expect(hasPermission(mockUser, 'analytics:view_agency')).toBe(true);
      expect(hasPermission(mockUser, 'agencies:manage')).toBe(false); // Can't manage all agencies
      expect(hasPermission(mockUser, 'agency:settings')).toBe(true); // Can manage own agency
    });

    it('should grant appropriate permissions to agency_admin', () => {
      const mockUser = {
        id: '1',
        email: 'admin@agency.com',
        full_name: 'Agency Admin',
        role: 'agency_admin' as const,
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(hasPermission(mockUser, 'models:manage')).toBe(true);
      expect(hasPermission(mockUser, 'chat:manage_all')).toBe(true);
      expect(hasPermission(mockUser, 'financial:view_agency')).toBe(true);
      expect(hasPermission(mockUser, 'users:write')).toBe(false); // Can't create users globally
    });

    it('should grant chat permissions to chatters', () => {
      const mockUser = {
        id: '1',
        email: 'chatter@agency.com',
        full_name: 'Chatter',
        role: 'chatter' as const,
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(hasPermission(mockUser, 'chat:access')).toBe(true);
      expect(hasPermission(mockUser, 'chat:manage_assigned')).toBe(true);
      expect(hasPermission(mockUser, 'models:manage')).toBe(false);
      expect(hasPermission(mockUser, 'financial:view_agency')).toBe(false);
    });

    it('should grant basic permissions to members', () => {
      const mockUser = {
        id: '1',
        email: 'member@agency.com',
        full_name: 'Member',
        role: 'member' as const,
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(hasPermission(mockUser, 'dashboard:view')).toBe(true);
      expect(hasPermission(mockUser, 'analytics:view_basic')).toBe(true);
      expect(hasPermission(mockUser, 'chat:access')).toBe(false);
      expect(hasPermission(mockUser, 'financial:view_any')).toBe(false);
    });
  });

  describe('Component Rendering Based on Role', () => {
    it('should show admin UI elements for admin roles', () => {
      vi.mocked(useAuthStore).mockReturnValue({
        user: {
          id: '1',
          email: 'admin@example.com',
          full_name: 'Admin User',
          role: 'super_admin',
          is_active: true,
          is_verified: true,
          agency_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        isAuthenticated: true,
        isPending: false,
        error: null,
        token: 'mock-token',
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        checkAuth: vi.fn(),
        clearError: vi.fn(),
      });

      const AdminComponent = () => {
        const { user } = useAuthStore();
        return (
          <div>
            {hasPermission(user!, 'users:write') && (
              <button>Create User</button>
            )}
            {hasPermission(user!, 'agencies:manage') && (
              <button>Manage Agencies</button>
            )}
          </div>
        );
      };

      render(<AdminComponent />);
      
      expect(screen.getByText('Create User')).toBeInTheDocument();
      expect(screen.getByText('Manage Agencies')).toBeInTheDocument();
    });

    it('should hide admin UI elements for non-admin roles', () => {
      vi.mocked(useAuthStore).mockReturnValue({
        user: {
          id: '1',
          email: 'model@example.com',
          full_name: 'Model User',
          role: 'model',
          is_active: true,
          is_verified: true,
          agency_id: 'agency-1',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
        isAuthenticated: true,
        isPending: false,
        error: null,
        token: 'mock-token',
        login: vi.fn(),
        register: vi.fn(),
        logout: vi.fn(),
        checkAuth: vi.fn(),
        clearError: vi.fn(),
      });

      const AdminComponent = () => {
        const { user } = useAuthStore();
        return (
          <div>
            {hasPermission(user!, 'users:write') && (
              <button>Create User</button>
            )}
            {hasPermission(user!, 'agencies:manage') && (
              <button>Manage Agencies</button>
            )}
            {hasPermission(user!, 'chat:access') && (
              <button>Access Chat</button>
            )}
          </div>
        );
      };

      render(<AdminComponent />);
      
      expect(screen.queryByText('Create User')).not.toBeInTheDocument();
      expect(screen.queryByText('Manage Agencies')).not.toBeInTheDocument();
      expect(screen.getByText('Access Chat')).toBeInTheDocument();
    });
  });

  describe('Data Filtering by Role', () => {
    it('should filter data based on agency for agency roles', () => {
      const allData = [
        { id: '1', name: 'Model 1', agency_id: 'agency-1' },
        { id: '2', name: 'Model 2', agency_id: 'agency-1' },
        { id: '3', name: 'Model 3', agency_id: 'agency-2' },
      ];

      const user = {
        id: '1',
        email: 'owner@agency.com',
        full_name: 'Agency Owner',
        role: 'agency_owner' as const,
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Simulate data filtering
      const filteredData = user.role === 'super_admin' 
        ? allData 
        : allData.filter(item => item.agency_id === user.agency_id);

      expect(filteredData).toHaveLength(2);
      expect(filteredData.every(item => item.agency_id === 'agency-1')).toBe(true);
    });

    it('should show all data for super_admin', () => {
      const allData = [
        { id: '1', name: 'Model 1', agency_id: 'agency-1' },
        { id: '2', name: 'Model 2', agency_id: 'agency-1' },
        { id: '3', name: 'Model 3', agency_id: 'agency-2' },
      ];

      const user = {
        id: '1',
        email: 'super@admin.com',
        full_name: 'Super Admin',
        role: 'super_admin' as const,
        is_active: true,
        is_verified: true,
        agency_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Simulate data filtering
      const filteredData = user.role === 'super_admin' 
        ? allData 
        : allData.filter(item => item.agency_id === user.agency_id);

      expect(filteredData).toHaveLength(3);
    });
  });
});