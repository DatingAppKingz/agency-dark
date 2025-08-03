import { rest } from 'msw';

const API_URL = 'http://localhost:8000/api/v1';

// Default handlers for common API endpoints
export const handlers = [
  // Auth endpoints
  rest.post(`${API_URL}/auth/login`, (req, res, ctx) => {
    return res(
      ctx.json({
        access_token: 'mock-access-token',
        token_type: 'bearer',
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'agency_admin',
          is_active: true,
          is_verified: true,
          agency_id: 'agency-1',
          created_at: new Date().toISOString(),
          verified_at: new Date().toISOString(),
        },
      })
    );
  }),

  rest.post(`${API_URL}/auth/logout`, (req, res, ctx) => {
    return res(ctx.status(200));
  }),

  rest.post(`${API_URL}/auth/register`, (req, res, ctx) => {
    return res(
      ctx.json({
        access_token: 'mock-access-token',
        token_type: 'bearer',
        user: {
          id: '2',
          email: 'newuser@example.com',
          full_name: 'New User',
          role: 'model',
          is_active: true,
          is_verified: false,
          agency_id: 'agency-1',
          created_at: new Date().toISOString(),
          verified_at: null,
        },
      })
    );
  }),

  rest.get(`${API_URL}/auth/me`, (req, res, ctx) => {
    const authHeader = req.headers.get('Authorization');
    if (!authHeader || !authHeader.includes('Bearer')) {
      return res(ctx.status(401), ctx.json({ detail: 'Unauthorized' }));
    }
    
    return res(
      ctx.json({
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'agency_admin',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        verified_at: new Date().toISOString(),
      })
    );
  }),

  // Users endpoints
  rest.get(`${API_URL}/users`, (req, res, ctx) => {
    return res(
      ctx.json({
        items: [
          {
            id: '1',
            email: 'user1@example.com',
            full_name: 'User One',
            role: 'agency_admin',
            is_active: true,
            is_verified: true,
            agency_id: 'agency-1',
            created_at: new Date().toISOString(),
          },
          {
            id: '2',
            email: 'user2@example.com',
            full_name: 'User Two',
            role: 'model',
            is_active: true,
            is_verified: false,
            agency_id: 'agency-1',
            created_at: new Date().toISOString(),
          },
        ],
        total: 2,
        page: 1,
        pages: 1,
      })
    );
  }),

  rest.get(`${API_URL}/users/:id`, (req, res, ctx) => {
    const { id } = req.params;
    return res(
      ctx.json({
        id,
        email: `user${id}@example.com`,
        full_name: `User ${id}`,
        role: 'model',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
      })
    );
  }),

  // Models endpoints
  rest.get(`${API_URL}/models`, (req, res, ctx) => {
    return res(
      ctx.json({
        items: [
          {
            id: '1',
            full_name: 'Model One',
            email: 'model1@example.com',
            display_name: 'Model One',
            bio: 'Test model bio',
            is_active: true,
            is_verified: true,
          },
        ],
        total: 1,
        page: 1,
        pages: 1,
      })
    );
  }),

  // Analytics endpoints
  rest.get(`${API_URL}/analytics/overview`, (req, res, ctx) => {
    return res(
      ctx.json({
        revenue: {
          total: 10000,
          change: 15.5,
          period: 'month',
        },
        users: {
          total: 150,
          active: 120,
          new: 25,
        },
        messages: {
          total: 5000,
          sent: 4500,
          received: 500,
        },
      })
    );
  }),

  // Media endpoints
  rest.get(`${API_URL}/media`, (req, res, ctx) => {
    return res(
      ctx.json({
        items: [
          {
            id: '1',
            filename: 'test-image.jpg',
            original_filename: 'test-image.jpg',
            file_path: '/media/test-image.jpg',
            file_size: 1024000,
            mime_type: 'image/jpeg',
            media_type: 'image',
            status: 'ready',
            tags: ['test'],
            visibility: 'private',
            agency_id: 'agency-1',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ],
        total: 1,
        has_more: false,
      })
    );
  }),

  rest.post(`${API_URL}/media/upload`, (req, res, ctx) => {
    return res(
      ctx.json({
        id: '2',
        filename: 'uploaded-file.jpg',
        original_filename: 'uploaded-file.jpg',
        file_path: '/media/uploaded-file.jpg',
        file_size: 2048000,
        mime_type: 'image/jpeg',
        media_type: 'image',
        status: 'processing',
        created_at: new Date().toISOString(),
      })
    );
  }),

  // Health check
  rest.get(`${API_URL}/health`, (req, res, ctx) => {
    return res(
      ctx.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
      })
    );
  }),

  // Catch-all for unhandled requests
  rest.get('*', (req, res, ctx) => {
    console.warn(`Unhandled GET request: ${req.url}`);
    return res(ctx.status(404));
  }),
  
  rest.post('*', (req, res, ctx) => {
    console.warn(`Unhandled POST request: ${req.url}`);
    return res(ctx.status(404));
  }),
];

// Error response handlers for testing error scenarios
export const errorHandlers = {
  unauthorized: rest.get('*', (req, res, ctx) => {
    return res(ctx.status(401), ctx.json({ detail: 'Unauthorized' }));
  }),
  
  serverError: rest.get('*', (req, res, ctx) => {
    return res(ctx.status(500), ctx.json({ detail: 'Internal server error' }));
  }),
  
  networkError: rest.get('*', (req, res, ctx) => {
    return res.networkError('Network error');
  }),
};