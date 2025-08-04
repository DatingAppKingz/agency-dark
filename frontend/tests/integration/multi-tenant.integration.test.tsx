import { describe, it, expect, vi, beforeEach } from 'vitest';
import { server } from '../utils/test-server';
import { http, HttpResponse } from 'msw';
import { createMockUser } from '../utils/mock-factories';
import { useAuthStore } from '@/store/authStore';
import { filterByAgency, validateAgencyContext, canAccessResource } from '@/utils/multi-tenant';

describe('Multi-Tenant Integration Tests', () => {
  beforeEach(() => {
    // Clear auth store
    useAuthStore.getState().logout();
    localStorage.clear();
  });

  describe('Data Isolation', () => {
    it('should only show models from user\'s agency', async () => {
      const user = createMockUser({ 
        id: '1',
        agency_id: 'agency-1',
        role: 'agency_admin'
      });
      
      useAuthStore.getState().setAuth({
        user,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });

      server.use(
        http.get('/api/v1/models', ({ request }) => {
          const url = new URL(request.url);
          const agencyId = url.searchParams.get('agency_id');
          
          if (agencyId !== 'agency-1') {
            return HttpResponse.json(
              { detail: 'Forbidden' },
              { status: 403 }
            );
          }
          
          return HttpResponse.json({
            items: [
              { id: 'model-1', name: 'Model 1', agency_id: 'agency-1' },
              { id: 'model-2', name: 'Model 2', agency_id: 'agency-1' },
            ],
            total: 2,
          });
        })
      );

      const response = await fetch('/api/v1/models?agency_id=agency-1', {
        headers: { 'Authorization': 'Bearer valid-token' },
      });

      const data = await response.json();
      expect(data.items).toHaveLength(2);
      expect(data.items.every((m: any) => m.agency_id === 'agency-1')).toBe(true);
    });

    it('should prevent access to other agency\'s data via direct API calls', async () => {
      const user = createMockUser({ 
        id: '1',
        agency_id: 'agency-1',
        role: 'agency_admin'
      });
      
      useAuthStore.getState().setAuth({
        user,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });

      server.use(
        http.get('/api/v1/models/:id', ({ params }) => {
          const modelId = params.id as string;
          
          // Model from different agency
          if (modelId === 'model-from-agency-2') {
            return HttpResponse.json(
              { detail: 'Access denied: Resource belongs to different agency' },
              { status: 403 }
            );
          }
          
          return HttpResponse.json({
            id: modelId,
            name: 'Model',
            agency_id: 'agency-1',
          });
        })
      );

      // Try to access model from different agency
      const response = await fetch('/api/v1/models/model-from-agency-2', {
        headers: { 'Authorization': 'Bearer valid-token' },
      });

      expect(response.status).toBe(403);
    });

    it('SUPER_ADMIN should see all agencies\' data', async () => {
      const superAdmin = createMockUser({ 
        id: 'super-1',
        role: 'super_admin',
        agency_id: null,
      });
      
      useAuthStore.getState().setAuth({
        user: superAdmin,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });

      server.use(
        http.get('/api/v1/users', () => {
          return HttpResponse.json({
            items: [
              createMockUser({ id: '1', agency_id: 'agency-1' }),
              createMockUser({ id: '2', agency_id: 'agency-2' }),
            ],
            total: 2,
          });
        })
      );

      const response = await fetch('/api/v1/users', {
        headers: { 'Authorization': 'Bearer valid-token' },
      });

      const data = await response.json();
      expect(data.items).toHaveLength(2);
      expect(new Set(data.items.map((u: any) => u.agency_id)).size).toBe(2);
    });
  });

  describe('Agency Context Validation', () => {
    it('should validate correct agency context', () => {
      const user = createMockUser({
        id: '1',
        email: 'user@agency1.com',
        role: 'member',
        agency_id: 'agency-1',
      });

      expect(validateAgencyContext(user, 'agency-1')).toBe(true);
      expect(validateAgencyContext(user, 'agency-2')).toBe(false);
    });

    it('should allow super_admin to access any agency context', () => {
      const user = createMockUser({
        id: '1',
        role: 'super_admin',
        agency_id: null,
      });

      expect(validateAgencyContext(user, 'agency-1')).toBe(true);
      expect(validateAgencyContext(user, 'agency-2')).toBe(true);
      expect(validateAgencyContext(user, 'any-agency')).toBe(true);
    });
  });

  describe('Resource Access Control', () => {
    it('should restrict model access to assigned chatters', () => {
      const chatter = createMockUser({
        id: '1',
        role: 'chatter',
        agency_id: 'agency-1',
        assigned_model_ids: ['model-1', 'model-2'],
      });

      expect(canAccessResource(chatter, 'model', 'model-1')).toBe(true);
      expect(canAccessResource(chatter, 'model', 'model-2')).toBe(true);
      expect(canAccessResource(chatter, 'model', 'model-3')).toBe(false);
    });

    it('should allow agency admins to access all agency models', () => {
      const admin = createMockUser({
        id: '1',
        role: 'agency_admin',
        agency_id: 'agency-1',
      });

      const model = { id: 'model-1', agency_id: 'agency-1' };
      
      expect(canAccessResource(admin, 'model', 'model-1', model)).toBe(true);
    });
  });

  describe('Cross-Agency Protection', () => {
    it('should prevent updating resources from different agency', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'agency_admin'
      });
      
      useAuthStore.getState().setAuth({
        user,
        accessToken: 'valid-token',
        refreshToken: 'valid-refresh',
      });

      server.use(
        http.put('/api/v1/models/:id', ({ params }) => {
          const modelId = params.id as string;
          
          // Check if model belongs to user's agency
          if (modelId === 'model-agency-2') {
            return HttpResponse.json(
              { detail: 'Cannot modify resources from different agency' },
              { status: 403 }
            );
          }
          
          return HttpResponse.json({
            id: modelId,
            name: 'Updated Model',
            agency_id: 'agency-1',
          });
        })
      );

      const response = await fetch('/api/v1/models/model-agency-2', {
        method: 'PUT',
        headers: {
          'Authorization': 'Bearer valid-token',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: 'Hacked Name' }),
      });

      expect(response.status).toBe(403);
    });
  });

  describe('Data Filtering', () => {
    it('should filter data by agency for agency-scoped users', () => {
      const user = createMockUser({
        id: '1',
        role: 'agency_owner',
        agency_id: 'agency-1',
      });

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
      const user = createMockUser({
        id: '1',
        role: 'super_admin',
        agency_id: null,
      });

      const data = [
        { id: '1', name: 'Model 1', agency_id: 'agency-1' },
        { id: '2', name: 'Model 2', agency_id: 'agency-1' },
        { id: '3', name: 'Model 3', agency_id: 'agency-2' },
        { id: '4', name: 'Model 4', agency_id: 'agency-2' },
      ];

      const filtered = filterByAgency(data, user);
      
      expect(filtered).toHaveLength(4);
    });
  });
});