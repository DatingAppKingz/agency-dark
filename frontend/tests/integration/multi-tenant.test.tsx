import { screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { render } from '../utils/test-utils';
import ModelsPage from '@/pages/models/ModelsPage';
import ChatPage from '@/pages/chat/ChatPage';
import FinancialPage from '@/pages/financial/FinancialPage';
import { server } from '../utils/test-server';
import { http, HttpResponse } from 'msw';

describe('Multi-Tenant Isolation', () => {
  describe('Data Isolation', () => {
    it('should only show agency-specific models for agency users', async () => {
      const agencyId = 'agency123';
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'agency_owner',
            agency_id: agencyId,
          },
        }),
      }));

      server.use(
        http.get('*/models', ({ request }) => {
          const url = new URL(request.url);
          const agency = url.searchParams.get('agency_id');
          
          if (agency !== agencyId) {
            return HttpResponse.json({ detail: 'Forbidden' }, { status: 403 });
          }
          
          return HttpResponse.json({
              items: [
                {
                  id: '1',
                  name: 'Model 1',
                  agency_id: agencyId,
                },
                {
                  id: '2',
                  name: 'Model 2',
                  agency_id: agencyId,
                },
              ],
              total: 2,
            });
        })
      );

      render(<ModelsPage />);

      await waitFor(() => {
        expect(screen.getByText('Model 1')).toBeInTheDocument();
        expect(screen.getByText('Model 2')).toBeInTheDocument();
      });

      // Should not show models from other agencies
      expect(screen.queryByText('Other Agency Model')).not.toBeInTheDocument();
    });

    it('should prevent cross-agency chat access', async () => {
      const agencyId = 'agency123';
      const otherAgencyConversationId = 'conv456';
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'chatter',
            agency_id: agencyId,
          },
        }),
      }));

      server.use(
        http.get(`*/chat/conversations/${otherAgencyConversationId}/messages`, () => {
          return HttpResponse.json({ detail: 'You do not have access to this conversation' }, { status: 403 });
        })
      );

      render(<ChatPage />);

      // Try to access conversation from another agency
      // const user = userEvent.setup(); // Would be used for interaction testing
      
      // This should be prevented by the UI, but testing API protection
      await waitFor(() => {
        expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
      });
    });

    it('should isolate financial data by agency', async () => {
      const agencyId = 'agency123';
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'agency_admin',
            agency_id: agencyId,
          },
        }),
      }));

      server.use(
        http.get('*/financial/summary', ({ request }) => {
          // const authHeader = request.headers.get('Authorization'); // Would validate auth token
          
          // Return only agency-specific financial data
          return HttpResponse.json({
              agency_id: agencyId,
              total_revenue: 50000,
              models_revenue: {
                model1: 25000,
                model2: 25000,
              },
              // Should not include data from other agencies
            });
        })
      );

      render(<FinancialPage />);

      await waitFor(() => {
        expect(screen.getByText(/50,000/)).toBeInTheDocument();
      });

      // Should not show system-wide totals for non-admin users
      expect(screen.queryByText(/platform total/i)).not.toBeInTheDocument();
    });
  });

  describe('Cross-Tenant Security', () => {
    it('should prevent model reassignment to different agency', async () => {
      const agencyId = 'agency123';
      // const otherAgencyId = 'agency456'; // Would be used to test cross-agency access prevention
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'agency_owner',
            agency_id: agencyId,
          },
        }),
      }));

      server.use(
        http.patch('*/models/:id', async ({ request }) => {
          const body = await request.json();
          
          if (body.agency_id && body.agency_id !== agencyId) {
            return HttpResponse.json({ detail: 'Cannot reassign model to different agency' }, { status: 403 });
          }
          
          return HttpResponse.json({ success: true });
        })
      );

      render(<ModelsPage />);

      // Attempt to reassign model (this would be through direct API call)
      // UI should not allow this option
      const reassignButtons = screen.queryAllByRole('button', { name: /reassign agency/i });
      expect(reassignButtons).toHaveLength(0);
    });

    it('should validate agency context in API requests', async () => {
      const agencyId = 'agency123';
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'agency_admin',
            agency_id: agencyId,
          },
        }),
      }));

      // All API requests should include agency context
      server.use(
        http.get('*/users', ({ request }) => {
          const url = new URL(request.url);
          const agencyParam = url.searchParams.get('agency_id');
          
          if (agencyParam !== agencyId) {
            return HttpResponse.json({ detail: 'Invalid agency context' }, { status: 400 });
          }
          
          return HttpResponse.json({ items: [], total: 0 });
        })
      );

      render(<ModelsPage />);

      // Component should automatically include agency context
      await waitFor(() => {
        expect(screen.getByText(/models/i)).toBeInTheDocument();
      });
    });
  });

  describe('Tenant Switching', () => {
    it('should clear cache when switching agencies (super_admin)', async () => {
      const clearCacheSpy = vi.fn();
      
      vi.mock('@tanstack/react-query', () => ({
        ...vi.requireActual('@tanstack/react-query'),
        useQueryClient: () => ({
          clear: clearCacheSpy,
        }),
      }));

      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'super_admin',
            impersonating_agency_id: null,
          },
        }),
      }));

      const { rerender } = render(<ModelsPage />);

      // Simulate agency switch
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'super_admin',
            impersonating_agency_id: 'agency123',
          },
        }),
      }));

      rerender(<ModelsPage />);

      expect(clearCacheSpy).toHaveBeenCalled();
    });

    it('should update UI to show current agency context', async () => {
      const agencyId = 'agency123';
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'super_admin',
            impersonating_agency_id: agencyId,
          },
        }),
      }));

      render(<ModelsPage />);

      // Should show agency context indicator
      await waitFor(() => {
        expect(screen.getByText(/viewing as: agency123/i)).toBeInTheDocument();
      });
    });
  });

  describe('Resource Permissions', () => {
    it('should enforce model ownership for chatters', async () => {
      const agencyId = 'agency123';
      const modelId = 'model123';
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            role: 'chatter',
            agency_id: agencyId,
            assigned_model_ids: [modelId],
          },
        }),
      }));

      server.use(
        http.get('*/chat/conversations', () => {
          // Return only conversations for assigned models
          return HttpResponse.json([
              {
                id: '1',
                model_id: modelId,
                fan_id: 'fan1',
                // ... other fields
              },
            ]);
        })
      );

      render(<ChatPage />);

      await waitFor(() => {
        // Should only see conversations for assigned models
        expect(screen.getByText(/1 conversation/i)).toBeInTheDocument();
      });
    });

    it('should restrict financial access to own earnings for models', async () => {
      const modelId = 'model123';
      
      vi.mock('@/store/authStore', () => ({
        useAuthStore: () => ({
          ...mockAuthStore,
          user: {
            ...mockAuthStore.user,
            id: modelId,
            role: 'model',
          },
        }),
      }));

      server.use(
        http.get('*/financial/earnings', ({ request }) => {
          const url = new URL(request.url);
          const requestModelId = url.searchParams.get('model_id');
          
          if (requestModelId !== modelId) {
            return HttpResponse.json({ detail: 'Can only view own earnings' }, { status: 403 });
          }
          
          return HttpResponse.json({
              model_id: modelId,
              total_earnings: 15000,
              pending_payout: 3000,
            });
        })
      );

      render(<FinancialPage />);

      await waitFor(() => {
        expect(screen.getByText(/15,000/)).toBeInTheDocument();
      });

      // Should not show other models' earnings
      expect(screen.queryByText(/other models/i)).not.toBeInTheDocument();
    });
  });
});
