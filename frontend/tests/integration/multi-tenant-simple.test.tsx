import { describe, it, expect, vi } from 'vitest';
import { filterByAgency, validateAgencyContext, canAccessResource } from '@/utils/multi-tenant';
import { User } from '@/types/auth';

describe('Multi-Tenant Isolation', () => {
  describe('Data Filtering', () => {
    it('should filter data by agency for agency-scoped users', () => {
      const user: User = {
        id: '1',
        email: 'owner@agency1.com',
        full_name: 'Agency Owner',
        role: 'agency_owner',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const data = [
        { id: '1', name: 'Model 1', agency_id: 'agency-1' },
        { id: '2', name: 'Model 2', agency_id: 'agency-1' },
        { id: '3', name: 'Model 3', agency_id: 'agency-2' },
        { id: '4', name: 'Model 4', agency_id: 'agency-2' },
      ];

      const filtered = filterByAgency(data, user);
      
      expect(filtered).toHaveLength(2);
      expect(filtered.every(item => item.agency_id === 'agency-1')).toBe(true);
    });

    it('should return all data for super_admin', () => {
      const user: User = {
        id: '1',
        email: 'super@admin.com',
        full_name: 'Super Admin',
        role: 'super_admin',
        is_active: true,
        is_verified: true,
        agency_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const data = [
        { id: '1', name: 'Model 1', agency_id: 'agency-1' },
        { id: '2', name: 'Model 2', agency_id: 'agency-1' },
        { id: '3', name: 'Model 3', agency_id: 'agency-2' },
        { id: '4', name: 'Model 4', agency_id: 'agency-2' },
      ];

      const filtered = filterByAgency(data, user);
      
      expect(filtered).toHaveLength(4);
    });

    it('should handle null agency_id for global resources', () => {
      const user: User = {
        id: '1',
        email: 'admin@agency1.com',
        full_name: 'Agency Admin',
        role: 'agency_admin',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const data = [
        { id: '1', name: 'Global Resource', agency_id: null },
        { id: '2', name: 'Agency Resource', agency_id: 'agency-1' },
        { id: '3', name: 'Other Agency Resource', agency_id: 'agency-2' },
      ];

      const filtered = filterByAgency(data, user, { includeGlobal: true });
      
      expect(filtered).toHaveLength(2);
      expect(filtered.some(item => item.agency_id === null)).toBe(true);
      expect(filtered.some(item => item.agency_id === 'agency-1')).toBe(true);
    });
  });

  describe('Agency Context Validation', () => {
    it('should validate correct agency context', () => {
      const user: User = {
        id: '1',
        email: 'user@agency1.com',
        full_name: 'User',
        role: 'member',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(validateAgencyContext(user, 'agency-1')).toBe(true);
      expect(validateAgencyContext(user, 'agency-2')).toBe(false);
    });

    it('should allow super_admin to access any agency context', () => {
      const user: User = {
        id: '1',
        email: 'super@admin.com',
        full_name: 'Super Admin',
        role: 'super_admin',
        is_active: true,
        is_verified: true,
        agency_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(validateAgencyContext(user, 'agency-1')).toBe(true);
      expect(validateAgencyContext(user, 'agency-2')).toBe(true);
      expect(validateAgencyContext(user, 'any-agency')).toBe(true);
    });
  });

  describe('Resource Access Control', () => {
    it('should restrict model access to assigned chatters', () => {
      const chatter: User = {
        id: '1',
        email: 'chatter@agency.com',
        full_name: 'Chatter',
        role: 'chatter',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        assigned_model_ids: ['model-1', 'model-2'],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(canAccessResource(chatter, 'model', 'model-1')).toBe(true);
      expect(canAccessResource(chatter, 'model', 'model-2')).toBe(true);
      expect(canAccessResource(chatter, 'model', 'model-3')).toBe(false);
    });

    it('should allow agency admins to access all agency models', () => {
      const admin: User = {
        id: '1',
        email: 'admin@agency.com',
        full_name: 'Admin',
        role: 'agency_admin',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const model = { id: 'model-1', agency_id: 'agency-1' };
      
      expect(canAccessResource(admin, 'model', 'model-1', model)).toBe(true);
    });

    it('should restrict financial data to own earnings for models', () => {
      const model: User = {
        id: 'model-1',
        email: 'model@agency.com',
        full_name: 'Model',
        role: 'model',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      expect(canAccessResource(model, 'earnings', 'model-1')).toBe(true);
      expect(canAccessResource(model, 'earnings', 'model-2')).toBe(false);
    });
  });

  describe('Cross-Tenant Security', () => {
    it('should prevent cross-agency data modification', () => {
      const user: User = {
        id: '1',
        email: 'admin@agency1.com',
        full_name: 'Admin',
        role: 'agency_admin',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const targetResource = { id: 'model-1', agency_id: 'agency-2' };
      
      expect(canAccessResource(user, 'model', 'model-1', targetResource)).toBe(false);
    });

    it('should validate agency reassignment attempts', () => {
      const user: User = {
        id: '1',
        email: 'owner@agency1.com',
        full_name: 'Owner',
        role: 'agency_owner',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const model = { id: 'model-1', agency_id: 'agency-1' };
      const newAgencyId = 'agency-2';
      
      // Agency owners cannot reassign models to different agencies
      expect(validateAgencyContext(user, newAgencyId)).toBe(false);
    });
  });

  describe('Impersonation', () => {
    it('should handle super_admin impersonating an agency', () => {
      const user: User = {
        id: '1',
        email: 'super@admin.com',
        full_name: 'Super Admin',
        role: 'super_admin',
        is_active: true,
        is_verified: true,
        agency_id: null,
        impersonating_agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      const data = [
        { id: '1', name: 'Model 1', agency_id: 'agency-1' },
        { id: '2', name: 'Model 2', agency_id: 'agency-1' },
        { id: '3', name: 'Model 3', agency_id: 'agency-2' },
      ];

      const filtered = filterByAgency(data, user);
      
      // When impersonating, should only see that agency's data
      expect(filtered).toHaveLength(2);
      expect(filtered.every(item => item.agency_id === 'agency-1')).toBe(true);
    });
  });
});