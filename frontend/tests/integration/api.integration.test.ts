import { rest } from 'msw';
import { vi } from 'vitest';
import { setupServer } from 'msw/node';
import { apiClient, authService, userService, modelService } from '@/tests/utils/mock-factories';
import { createMockUser, createMockModel, mockApiResponses } from '@/tests/utils/test-utils';

// Setup MSW server
const server = setupServer(
  rest.post('/api/auth/login', (req, res, ctx) => {
    return res(ctx.json(mockApiResponses.login));
  }),
  rest.get('/api/users', (req, res, ctx) => {
    return res(ctx.json(mockApiResponses.users));
  }),
  rest.get('/api/models', (req, res, ctx) => {
    return res(ctx.json(mockApiResponses.models));
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('API Integration Tests', () => {
  describe('Authentication API', () => {
    it('should successfully login with valid credentials', async () => {
      const credentials = { email: 'test@example.com', password: 'password123' };
      const response = await authService.login(credentials);
      
      expect(response.access_token).toBe('mock-access-token');
      expect(response.refresh_token).toBe('mock-refresh-token');
      expect(response.user.email).toBe('test@example.com');
    });

    it('should handle login errors', async () => {
      server.use(
        rest.post('/api/auth/login', (req, res, ctx) => {
          return res(ctx.status(401), ctx.json({ detail: 'Invalid credentials' }));
        })
      );

      await expect(authService.login({ email: 'wrong@example.com', password: 'wrong' }))
        .rejects.toThrow();
    });

    it('should refresh token when expired', async () => {
      server.use(
        rest.post('/api/auth/refresh', (req, res, ctx) => {
          return res(ctx.json({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
          }));
        })
      );

      const newTokens = await authService.refreshToken('old-refresh-token');
      expect(newTokens.access_token).toBe('new-access-token');
    });
  });

  describe('Users API', () => {
    it('should fetch users with pagination', async () => {
      const users = await userService.getUsers({ page: 1, limit: 10 });
      
      expect(users.data).toHaveLength(1);
      expect(users.total).toBe(1);
      expect(users.data[0].email).toBe('test@example.com');
    });

    it('should create a new user', async () => {
      const newUser = createMockUser({ id: '2', email: 'new@example.com' });
      
      server.use(
        rest.post('/api/users', (req, res, ctx) => {
          return res(ctx.json(newUser));
        })
      );

      const created = await userService.createUser({
        email: 'new@example.com',
        name: 'New User',
        password: 'password123',
        role: 'AGENCY_ADMIN',
      });

      expect(created.id).toBe('2');
      expect(created.email).toBe('new@example.com');
    });

    it('should update user details', async () => {
      const updatedUser = createMockUser({ name: 'Updated Name' });
      
      server.use(
        rest.put('/api/users/:id', (req, res, ctx) => {
          return res(ctx.json(updatedUser));
        })
      );

      const updated = await userService.updateUser('1', { name: 'Updated Name' });
      expect(updated.name).toBe('Updated Name');
    });

    it('should handle API errors gracefully', async () => {
      server.use(
        rest.get('/api/users', (req, res, ctx) => {
          return res(ctx.status(500), ctx.json({ detail: 'Internal Server Error' }));
        })
      );

      await expect(userService.getUsers({})).rejects.toThrow();
    });
  });

  describe('Models API', () => {
    it('should fetch models for agency', async () => {
      const models = await modelService.getModels({ agency_id: 'agency-1' });
      
      expect(models.data).toHaveLength(1);
      expect(models.data[0].name).toBe('Test Model');
    });

    it('should get model details by ID', async () => {
      const modelDetails = createMockModel({
        earnings: { total: 10000, monthly: 2000 },
        subscribers: 150,
      });

      server.use(
        rest.get('/api/models/:id', (req, res, ctx) => {
          return res(ctx.json(modelDetails));
        })
      );

      const model = await modelService.getModelById('model-1');
      expect(model.id).toBe('model-1');
      expect(model.earnings.total).toBe(10000);
    });

    it('should update model status', async () => {
      server.use(
        rest.patch('/api/models/:id', (req, res, ctx) => {
          return res(ctx.json(createMockModel({ status: 'inactive' })));
        })
      );

      const updated = await modelService.updateModelStatus('model-1', 'inactive');
      expect(updated.status).toBe('inactive');
    });
  });

  describe('API Client Configuration', () => {
    it('should add authorization header when token exists', async () => {
      localStorage.setItem('access_token', 'test-token');
      
      let capturedHeaders: any;
      server.use(
        rest.get('/api/test', (req, res, ctx) => {
          capturedHeaders = req.headers;
          return res(ctx.json({ success: true }));
        })
      );

      await apiClient.get('/test');
      expect(capturedHeaders.get('authorization')).toBe('Bearer test-token');
    });

    it('should handle request timeout', async () => {
      server.use(
        rest.get('/api/slow', (req, res, ctx) => {
          return res(ctx.delay(10000), ctx.json({}));
        })
      );

      const controller = new AbortController();
      setTimeout(() => controller.abort(), 100);

      await expect(
        apiClient.get('/slow', { signal: controller.signal })
      ).rejects.toThrow('canceled');
    });
  });

  describe('Error Handling', () => {
    it('should handle network errors', async () => {
      server.use(
        rest.get('/api/network-error', (req, res) => {
          return res.networkError('Network error');
        })
      );

      await expect(apiClient.get('/network-error')).rejects.toThrow();
    });

    it('should handle validation errors', async () => {
      server.use(
        rest.post('/api/users', (req, res, ctx) => {
          return res(ctx.status(422), ctx.json({
            detail: 'Validation Error',
            errors: {
              email: ['Email already exists'],
              password: ['Password too weak'],
            },
          }));
        })
      );

      try {
        await userService.createUser({
          email: 'existing@example.com',
          name: 'Test',
          password: '123',
          role: 'MODEL',
        });
      } catch (error: any) {
        expect(error.response.status).toBe(422);
        expect(error.response.data.errors.email).toContain('Email already exists');
      }
    });
  });

  describe('Pagination and Filtering', () => {
    it('should handle pagination parameters correctly', async () => {
      let capturedParams: any;
      server.use(
        rest.get('/api/users', (req, res, ctx) => {
          capturedParams = Object.fromEntries(req.url.searchParams);
          return res(ctx.json(mockApiResponses.users));
        })
      );

      await userService.getUsers({ page: 2, limit: 20, role: 'MODEL' });
      
      expect(capturedParams.page).toBe('2');
      expect(capturedParams.limit).toBe('20');
      expect(capturedParams.role).toBe('MODEL');
    });

    it('should handle search queries', async () => {
      let capturedSearch: any;
      server.use(
        rest.get('/api/users', (req, res, ctx) => {
          capturedSearch = req.url.searchParams.get('search');
          return res(ctx.json(mockApiResponses.users));
        })
      );

      await userService.searchUsers('john@example.com');
      expect(capturedSearch).toBe('john@example.com');
    });
  });
});
