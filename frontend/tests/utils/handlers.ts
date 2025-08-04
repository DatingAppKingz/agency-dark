import { http, HttpResponse } from 'msw';

const API_URL = 'http://localhost:8000/api/v1';

// Default handlers for common API endpoints
export const handlers = [
  // Auth endpoints
  http.post(`${API_URL}/auth/login`, () => {
    return HttpResponse.json({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
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
      });
  }),

  http.post(`${API_URL}/auth/logout`, () => {
    return new HttpResponse(null, { status: 200 });
  }),

  http.post(`${API_URL}/auth/register`, () => {
    return HttpResponse.json({
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
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
      });
  }),

  http.post(`${API_URL}/auth/refresh`, () => {
    return HttpResponse.json({
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
    });
  }),

  http.post(`${API_URL}/auth/forgot-password`, () => {
    return HttpResponse.json({
      message: 'Password reset email sent',
    });
  }),

  http.post(`${API_URL}/auth/reset-password`, () => {
    return HttpResponse.json({
      message: 'Password reset successful',
    });
  }),

  http.post(`${API_URL}/auth/password-reset/confirm`, () => {
    return HttpResponse.json({
      message: 'Password reset successful',
    });
  }),

  http.get(`${API_URL}/auth/me`, ({ request }) => {
    const authHeader = request.headers.get('Authorization');
    if (!authHeader || !authHeader.includes('Bearer')) {
      return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
    }
    
    return HttpResponse.json({
        id: '1',
        email: 'test@example.com',
        full_name: 'Test User',
        role: 'agency_admin',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
        verified_at: new Date().toISOString(),
      });
  }),

  // Users endpoints
  http.get(`${API_URL}/users`, () => {
    return HttpResponse.json({
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
      });
  }),

  http.get(`${API_URL}/users/:id`, ({ params }) => {
    const { id } = params;
    return HttpResponse.json({
        id,
        email: `user${id}@example.com`,
        full_name: `User ${id}`,
        role: 'model',
        is_active: true,
        is_verified: true,
        agency_id: 'agency-1',
        created_at: new Date().toISOString(),
      });
  }),

  // Models endpoints
  http.get(`${API_URL}/models`, () => {
    return HttpResponse.json({
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
      });
  }),

  // Analytics endpoints
  http.get(`${API_URL}/analytics/overview`, () => {
    return HttpResponse.json({
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
      });
  }),

  // Media endpoints
  http.get(`${API_URL}/media`, () => {
    return HttpResponse.json({
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
      });
  }),

  http.post(`${API_URL}/media/upload`, () => {
    return HttpResponse.json({
        id: '2',
        filename: 'uploaded-file.jpg',
        original_filename: 'uploaded-file.jpg',
        file_path: '/media/uploaded-file.jpg',
        file_size: 2048000,
        mime_type: 'image/jpeg',
        media_type: 'image',
        status: 'processing',
        created_at: new Date().toISOString(),
      });
  }),

  // Health check
  http.get(`${API_URL}/health`, () => {
    return HttpResponse.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
      });
  }),

  // Translations endpoints
  http.get(`${API_URL}/translations/export/:lang`, () => {
    return HttpResponse.json({
      translations: {
        common: {
          login: 'Login',
          logout: 'Logout',
          save: 'Save',
          cancel: 'Cancel',
        },
      },
    });
  }),

  // Handle different port in test environment
  http.get('http://localhost:3000/api/v1/translations/export/:lang', () => {
    return HttpResponse.json({
      translations: {
        common: {
          login: 'Login',
          logout: 'Logout',
          save: 'Save',
          cancel: 'Cancel',
        },
      },
    });
  }),

  // Catch-all for unhandled requests
  http.get('*', ({ request }) => {
    console.warn(`Unhandled GET request: ${request.url}`);
    return new HttpResponse(null, { status: 404 });
  }),
  
  http.post('*', ({ request }) => {
    console.warn(`Unhandled POST request: ${request.url}`);
    return new HttpResponse(null, { status: 404 });
  }),
];

// Error response handlers for testing error scenarios
export const errorHandlers = {
  unauthorized: http.get('*', () => {
    return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
  }),
  
  serverError: http.get('*', () => {
    return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
  }),
  
  networkError: http.get('*', () => {
    return HttpResponse.error();
  }),
};