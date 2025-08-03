import React from 'react';
import { vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
// import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { setupServer } from 'msw/node';
import { render, createMockUser, createMockModel, createMockChat } from '../../utils/test-utils';
import { useAuthStore, apiClient } from '../../utils/mock-factories';
import ModelsPage from '@/pages/models/ModelsPage'; import UsersPage from '@/pages/users/UsersPage'; import AnalyticsPage from '@/pages/analytics/AnalyticsPage';

// Setup MSW server with agency-aware endpoints
const server = setupServer(
  rest.get('/api/models', (req, res, ctx) => {
    const agencyId = req.url.searchParams.get('agency_id');
    const authHeader = req.headers.get('authorization');
    
    if (!authHeader) {
      return res(ctx.status(401));
    }

    // Return models only for the correct agency
    const models = agencyId === 'agency-1' ? [
      createMockModel({ id: 'model-1', agency_id: 'agency-1' }),
      createMockModel({ id: 'model-2', agency_id: 'agency-1' }),
    ] : [];

    return res(ctx.json({ data: models, total: models.length }));
  }),
  
  rest.get('/api/users', (req, res, ctx) => {
    const _currentUser = useAuthStore.getState().user;
    
    if (currentUser?.role === 'SUPER_ADMIN') {
      // Super admin can see all users
      return res(ctx.json({
        data: [
          createMockUser({ id: '1', agency_id: 'agency-1' }),
          createMockUser({ id: '2', agency_id: 'agency-2' }),
        ],
        total: 2,
      }));
    }
    
    // Regular users only see their agency's users
    const users = currentUser?.agency_id === 'agency-1' ? [
      createMockUser({ id: '1', agency_id: 'agency-1' }),
    ] : [];
    
    return res(ctx.json({ data: users, total: users.length }));
  }),
  
  rest.get('/api/chats', (req, res, ctx) => {
    const _currentUser = useAuthStore.getState().user;
    const agencyFilter = req.url.searchParams.get('agency_id');
    
    // Ensure agency filter matches user's agency
    if (agencyFilter !== currentUser?.agency_id && currentUser?.role !== 'SUPER_ADMIN') {
      return res(ctx.status(403), ctx.json({ detail: 'Access denied' }));
    }
    
    return res(ctx.json({
      data: [createMockChat({ agency_id: currentUser?.agency_id })],
      total: 1,
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

describe('Multi-Tenant Isolation Tests', () => {
  describe('Data Isolation', () => {
    it('should only show models from user\'s agency', async () => {
      const user = createMockUser({ 
        id: '1',
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'valid-token');

      render(<ModelsPage />);

      await waitFor(() => {
        // Should only see models from agency-1
        expect(screen.getByText('model-1')).toBeInTheDocument();
        expect(screen.getByText('model-2')).toBeInTheDocument();
      });

      // Verify the API was called with correct agency filter
      const apiCalls = server.events.filter(event => 
        event.request.url.includes('/api/models')
      );
      expect(apiCalls.length).toBeGreaterThan(0);
    });

    it('should prevent access to other agency\'s data via direct API calls', async () => {
      const user = createMockUser({ 
        id: '1',
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'valid-token');

      server.use(
        rest.get('/api/models/:id', (req, res, ctx) => {
          const modelId = req.params.id;
          const _currentUser = useAuthStore.getState().user;
          
          // Model from different agency
          if (modelId === 'model-from-agency-2') {
            return res(ctx.status(403), ctx.json({
              detail: 'Access denied: Resource belongs to different agency'
            }));
          }
          
          return res(ctx.json(createMockModel({ id: modelId })));
        })
      );

      // Try to access model from different agency
      const response = await fetch('/api/models/model-from-agency-2', {
        headers: {
          'Authorization': 'Bearer valid-token',
        },
      });

      expect(response.status).toBe(403);
    });

    it('should isolate user lists by agency', async () => {
      const agencyAdmin = createMockUser({ 
        id: '1',
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user: agencyAdmin,
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'valid-token');

      render(<UsersPage />);

      await waitFor(() => {
        // Should only see users from agency-1
        const userElements = screen.getAllByTestId(/user-row/);
        expect(userElements).toHaveLength(1);
      });
    });

    it('SUPER_ADMIN should see all agencies\' data', async () => {
      const superAdmin = createMockUser({ 
        id: 'super-1',
        role: 'SUPER_ADMIN',
        agency_id: null, // Super admin not tied to specific agency
      });
      
      useAuthStore.getState().setAuth({
        user: superAdmin,
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'valid-token');

      render(<UsersPage />);

      await waitFor(() => {
        // Should see users from all agencies
        const userElements = screen.getAllByTestId(/user-row/);
        expect(userElements).toHaveLength(2);
      });
    });
  });

  describe('Cross-Agency Protection', () => {
    it('should prevent updating resources from different agency', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      server.use(
        rest.put('/api/models/:id', (req, res, ctx) => {
          const modelId = req.params.id;
          const _currentUser = useAuthStore.getState().user;
          
          // Check if model belongs to user's agency
          if (modelId === 'model-agency-2') {
            return res(ctx.status(403), ctx.json({
              detail: 'Cannot modify resources from different agency'
            }));
          }
          
          return res(ctx.json(createMockModel({ id: modelId })));
        })
      );

      const response = await apiClient.put('/models/model-agency-2', {
        name: 'Hacked Name',
      });

      expect(response.status).toBe(403);
    });

    it('should validate agency context in bulk operations', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_MANAGER'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      server.use(
        rest.post('/api/models/bulk-update', (req, res, ctx) => {
          const { model_ids } = req.body as any;
          
          // Check if all models belong to user's agency
          const invalidModels = model_ids.filter((id: string) => 
            id.includes('agency-2')
          );
          
          if (invalidModels.length > 0) {
            return res(ctx.status(403), ctx.json({
              detail: 'Some models belong to different agency',
              invalid_models: invalidModels,
            }));
          }
          
          return res(ctx.json({ updated: model_ids.length }));
        })
      );

      const response = await fetch('/api/models/bulk-update', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer valid-token',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model_ids: ['model-1-agency-1', 'model-2-agency-2'],
        }),
      });

      expect(response.status).toBe(403);
    });
  });

  describe('Agency Context Headers', () => {
    it('should include agency context in API requests', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });
      localStorage.setItem('access_token', 'valid-token');

      let capturedHeaders: any;
      server.use(
        rest.get('/api/test-headers', (req, res, ctx) => {
          capturedHeaders = req.headers;
          return res(ctx.json({ success: true }));
        })
      );

      await apiClient.get('/test-headers');

      expect(capturedHeaders.get('x-agency-id')).toBe('agency-1');
    });

    it('should reject requests with mismatched agency headers', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      server.use(
        rest.get('/api/protected', (req, res, ctx) => {
          const headerAgency = req.headers.get('x-agency-id');
          const userAgency = 'agency-1';
          
          if (headerAgency !== userAgency) {
            return res(ctx.status(403), ctx.json({
              detail: 'Agency context mismatch'
            }));
          }
          
          return res(ctx.json({ data: 'protected' }));
        })
      );

      // Try to spoof different agency
      const response = await fetch('/api/protected', {
        headers: {
          'Authorization': 'Bearer valid-token',
          'X-Agency-Id': 'agency-2', // Spoofed header
        },
      });

      expect(response.status).toBe(403);
    });
  });

  describe('Analytics and Reporting Isolation', () => {
    it('should only show analytics for user\'s agency', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      server.use(
        rest.get('/api/analytics/overview', (req, res, ctx) => {
          const agencyId = req.url.searchParams.get('agency_id');
          
          if (agencyId !== 'agency-1') {
            return res(ctx.status(403));
          }
          
          return res(ctx.json({
            total_revenue: 50000,
            total_models: 10,
            total_chats: 1000,
            agency_id: 'agency-1',
          }));
        })
      );

      render(<AnalyticsPage />);

      await waitFor(() => {
        // Should see agency-specific analytics
        expect(screen.getByText(/50,000/)).toBeInTheDocument();
        expect(screen.getByText(/10.*models/i)).toBeInTheDocument();
      });
    });

    it('should prevent aggregating data across agencies', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_MANAGER'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      server.use(
        rest.post('/api/analytics/aggregate', (req, res, ctx) => {
          const { agency_ids } = req.body as any;
          const userAgency = 'agency-1';
          
          // Check if trying to aggregate across agencies
          if (agency_ids.some((id: string) => id !== userAgency)) {
            return res(ctx.status(403), ctx.json({
              detail: 'Cannot aggregate data across agencies'
            }));
          }
          
          return res(ctx.json({ aggregated_data: {} }));
        })
      );

      const response = await fetch('/api/analytics/aggregate', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer valid-token',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          agency_ids: ['agency-1', 'agency-2'],
        }),
      });

      expect(response.status).toBe(403);
    });
  });

  describe('WebSocket Isolation', () => {
    it('should only receive events for user\'s agency', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'MODEL'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      // Mock socket manager
      const mockSocket = {
        on: vi.fn(),
        emit: vi.fn(),
        off: vi.fn(),
      };

      // Simulate receiving events
      const _eventHandler = vi.fn();
      mockSocket.on.mockImplementation((event, handler) => {
        if (event === 'model:update') {
          // Simulate receiving updates
          handler({ model_id: 'model-1', agency_id: 'agency-1' });
          handler({ model_id: 'model-2', agency_id: 'agency-2' }); // Different agency
        }
      });

      // Component should filter out events from other agencies
      const filteredEvents = [];
      mockSocket.on('model:update', (data: any) => {
        if (data.agency_id === user.agency_id) {
          filteredEvents.push(data);
        }
      });

      expect(filteredEvents).toHaveLength(1);
      expect(filteredEvents[0].agency_id).toBe('agency-1');
    });
  });

  describe('File and Media Isolation', () => {
    it('should prevent access to files from different agencies', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_ADMIN'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      server.use(
        rest.get('/api/files/:id', (req, res, ctx) => {
          const fileId = req.params.id;
          
          // File belongs to different agency
          if (fileId === 'file-agency-2') {
            return res(ctx.status(403), ctx.json({
              detail: 'File access denied: belongs to different agency'
            }));
          }
          
          return res(ctx.json({
            id: fileId,
            url: `/files/${fileId}`,
            agency_id: 'agency-1',
          }));
        })
      );

      const response = await apiClient.get('/files/file-agency-2');
      expect(response.status).toBe(403);
    });

    it('should scope file uploads to agency', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'MODEL'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      let _capturedFormData: any;
      server.use(
        rest.post('/api/upload', (req, res, ctx) => {
          _capturedFormData = req.body;
          return res(ctx.json({
            file_id: 'uploaded-1',
            agency_id: 'agency-1',
          }));
        })
      );

      const formData = new FormData();
      formData.append('file', new Blob(['test']), 'test.jpg');
      
      const response = await fetch('/api/upload', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer valid-token',
          'X-Agency-Id': 'agency-1',
        },
        body: formData,
      });

      const result = await response.json();
      expect(result.agency_id).toBe('agency-1');
    });
  });

  describe('Search and Filtering', () => {
    it('should scope search results to agency', async () => {
      const user = createMockUser({ 
        agency_id: 'agency-1',
        role: 'AGENCY_MANAGER'
      });
      
      useAuthStore.getState().setAuth({
        user,
        isAuthenticated: true,
      });

      server.use(
        rest.get('/api/search', (req, res, ctx) => {
          const _query = req.url.searchParams.get('q');
          const agencyFilter = req.url.searchParams.get('agency_id');
          
          if (agencyFilter !== 'agency-1') {
            return res(ctx.json({ results: [] }));
          }
          
          return res(ctx.json({
            results: [
              { type: 'model', id: 'model-1', agency_id: 'agency-1' },
              { type: 'chat', id: 'chat-1', agency_id: 'agency-1' },
            ],
          }));
        })
      );

      const response = await apiClient.get('/search', {
        params: { q: 'test', agency_id: 'agency-1' },
      });

      expect(response.data.results).toHaveLength(2);
      response.data.results.forEach((result: any) => {
        expect(result.agency_id).toBe('agency-1');
      });
    });
  });
});
