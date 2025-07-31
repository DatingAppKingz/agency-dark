import { rest } from 'msw';
import { setupServer } from 'msw/node';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const handlers = [
  // Auth endpoints
  rest.post(`${API_URL}/api/v1/auth/login`, (req, res, ctx) => {
    return res(
      ctx.json({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        token_type: 'bearer',
        user: {
          id: '1',
          email: 'test@example.com',
          full_name: 'Test User',
          role: 'model',
          is_active: true,
        },
      })
    );
  }),

  rest.post(`${API_URL}/api/v1/auth/register`, (req, res, ctx) => {
    return res(
      ctx.json({
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'model',
        is_active: true,
      })
    );
  }),

  rest.post(`${API_URL}/api/v1/auth/logout`, (req, res, ctx) => {
    return res(ctx.json({ message: 'Logged out successfully' }));
  }),

  rest.get(`${API_URL}/api/v1/auth/me`, (req, res, ctx) => {
    const authHeader = req.headers.get('Authorization');
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return res(ctx.status(401), ctx.json({ detail: 'Unauthorized' }));
    }

    return res(
      ctx.json({
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'model',
        is_active: true,
      })
    );
  }),

  // Users endpoints
  rest.get(`${API_URL}/api/v1/users`, (req, res, ctx) => {
    return res(
      ctx.json({
        items: [
          {
            id: '1',
            email: 'user1@example.com',
            full_name: 'User One',
            role: 'model',
            is_active: true,
          },
          {
            id: '2',
            email: 'user2@example.com',
            full_name: 'User Two',
            role: 'chatter',
            is_active: true,
          },
        ],
        total: 2,
        page: 1,
        size: 10,
        pages: 1,
      })
    );
  }),

  rest.get(`${API_URL}/api/v1/users/:id`, (req, res, ctx) => {
    const { id } = req.params;
    return res(
      ctx.json({
        id,
        email: `user${id}@example.com`,
        full_name: `User ${id}`,
        role: 'model',
        is_active: true,
      })
    );
  }),

  // Chat endpoints
  rest.get(`${API_URL}/api/v1/chat/conversations`, (req, res, ctx) => {
    return res(
      ctx.json([
        {
          id: '1',
          fan_id: 'fan1',
          model_id: 'model1',
          fan: {
            id: 'fan1',
            name: 'John Doe',
            avatar_url: '/avatar1.jpg',
            is_online: true,
          },
          model: {
            id: 'model1',
            name: 'Jane Model',
            avatar_url: '/avatar2.jpg',
            is_online: true,
          },
          last_message: {
            id: 'msg1',
            content: 'Hello!',
            created_at: '2024-01-01T12:00:00Z',
          },
          unread_count: 2,
          is_pinned: false,
          is_archived: false,
          is_favorite: false,
          created_at: '2024-01-01T10:00:00Z',
          updated_at: '2024-01-01T12:00:00Z',
        },
      ])
    );
  }),

  rest.get(`${API_URL}/api/v1/chat/conversations/:id/messages`, (req, res, ctx) => {
    return res(
      ctx.json([
        {
          id: 'msg1',
          conversation_id: req.params.id,
          sender_id: 'user1',
          sender_type: 'fan',
          content: 'Hello!',
          created_at: '2024-01-01T12:00:00Z',
        },
        {
          id: 'msg2',
          conversation_id: req.params.id,
          sender_id: 'user2',
          sender_type: 'model',
          content: 'Hi there!',
          created_at: '2024-01-01T12:01:00Z',
        },
      ])
    );
  }),

  // Analytics endpoints
  rest.get(`${API_URL}/api/v1/analytics/platform`, (req, res, ctx) => {
    return res(
      ctx.json({
        revenue: {
          total: 125000,
          change: 12.5,
          chart_data: [],
        },
        users: {
          total: 3542,
          active: 2847,
          new: 156,
          change: 8.3,
        },
        messages: {
          total: 45291,
          average_per_user: 12.8,
          change: -2.1,
        },
      })
    );
  }),

  // Financial endpoints
  rest.get(`${API_URL}/api/v1/financial/summary`, (req, res, ctx) => {
    return res(
      ctx.json({
        total_earnings: 45000,
        pending_payout: 12000,
        last_payout: 8000,
        next_payout_date: '2024-02-01',
      })
    );
  }),
];

export const server = setupServer(...handlers);
