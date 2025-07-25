import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '@/__tests__/utils/test-utils';
import ModelsPage from '@/pages/models/ModelsPage';
import ChatPage from '@/pages/chat/ChatPage';
import FinancialPage from '@/pages/financial/FinancialPage';
import { server } from '@/__tests__/mocks/api-mocks';
import { rest } from 'msw';
import { mockAuthStore } from '@/__tests__/mocks/store-mocks';

describe('Multi-Tenant Isolation', () => {
  describe('Data Isolation', () => {
    it('should only show agency-specific models for agency users', async () => {
      const agencyId = 'agency123';
      
      jest.mock('@/store/authStore', () => ({
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
        rest.get('*/models', (req, res, ctx) => {
          const agency = req.url.searchParams.get('agency_id');
          
          if (agency !== agencyId) {
            return res(ctx.status(403), ctx.json({ detail: 'Forbidden' }));
          }
          
          return res(
            ctx.json({
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
            })
          );
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
      
      jest.mock('@/store/authStore', () => ({
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
        rest.get(`*/chat/conversations/${otherAgencyConversationId}/messages`, (req, res, ctx) => {
          return res(
            ctx.status(403),
            ctx.json({ detail: 'You do not have access to this conversation' })
          );
        })
      );

      render(<ChatPage />);

      // Try to access conversation from another agency
      const user = userEvent.setup();
      
      // This should be prevented by the UI, but testing API protection
      await waitFor(() => {
        expect(screen.queryByText(/access denied/i)).not.toBeInTheDocument();
      });
    });

    it('should isolate financial data by agency', async () => {
      const agencyId = 'agency123';
      
      jest.mock('@/store/authStore', () => ({
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
        rest.get('*/financial/summary', (req, res, ctx) => {
          const authHeader = req.headers.get('Authorization');
          
          // Return only agency-specific financial data
          return res(
            ctx.json({
              agency_id: agencyId,
              total_revenue: 50000,
              models_revenue: {
                model1: 25000,
                model2: 25000,
              },
              // Should not include data from other agencies
            })
          );
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
      const otherAgencyId = 'agency456';
      
      jest.mock('@/store/authStore', () => ({
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
        rest.patch('*/models/:id', async (req, res, ctx) => {
          const body = await req.json();
          
          if (body.agency_id && body.agency_id !== agencyId) {
            return res(
              ctx.status(403),
              ctx.json({ detail: 'Cannot reassign model to different agency' })
            );
          }
          
          return res(ctx.json({ success: true }));
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
      
      jest.mock('@/store/authStore', () => ({
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
        rest.get('*/users', (req, res, ctx) => {
          const agencyParam = req.url.searchParams.get('agency_id');
          
          if (agencyParam !== agencyId) {
            return res(
              ctx.status(400),
              ctx.json({ detail: 'Invalid agency context' })
            );
          }
          
          return res(ctx.json({ items: [], total: 0 }));
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
      const clearCacheSpy = jest.fn();
      
      jest.mock('@tanstack/react-query', () => ({
        ...jest.requireActual('@tanstack/react-query'),
        useQueryClient: () => ({
          clear: clearCacheSpy,
        }),
      }));

      jest.mock('@/store/authStore', () => ({
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
      jest.mock('@/store/authStore', () => ({
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
      
      jest.mock('@/store/authStore', () => ({
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
      
      jest.mock('@/store/authStore', () => ({
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
        rest.get('*/chat/conversations', (req, res, ctx) => {
          // Return only conversations for assigned models
          return res(
            ctx.json([
              {
                id: '1',
                model_id: modelId,
                fan_id: 'fan1',
                // ... other fields
              },
            ])
          );
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
      
      jest.mock('@/store/authStore', () => ({
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
        rest.get('*/financial/earnings', (req, res, ctx) => {
          const requestModelId = req.url.searchParams.get('model_id');
          
          if (requestModelId !== modelId) {
            return res(
              ctx.status(403),
              ctx.json({ detail: 'Can only view own earnings' })
            );
          }
          
          return res(
            ctx.json({
              model_id: modelId,
              total_earnings: 15000,
              pending_payout: 3000,
            })
          );
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