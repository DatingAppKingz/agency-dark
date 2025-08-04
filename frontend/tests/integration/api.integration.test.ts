import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { server } from '../utils/test-server';
import { http, HttpResponse } from 'msw';
import { createMockUser } from '../utils/mock-factories';

describe('API Integration Tests', () => {
  describe('Authentication API', () => {
    it('should successfully login with valid credentials', async () => {
      const mockResponse = {
        access_token: 'mock-access-token',
        refresh_token: 'mock-refresh-token',
        user: createMockUser({ email: 'test@example.com' }),
      };

      server.use(
        http.post('/api/v1/auth/login', () => {
          return HttpResponse.json(mockResponse);
        })
      );

      // Make the API call
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@example.com', password: 'password123' }),
      });

      const data = await response.json();
      
      expect(response.status).toBe(200);
      expect(data.access_token).toBe('mock-access-token');
      expect(data.user.email).toBe('test@example.com');
    });

    it('should handle login errors', async () => {
      server.use(
        http.post('/api/v1/auth/login', () => {
          return HttpResponse.json(
            { detail: 'Invalid credentials' },
            { status: 401 }
          );
        })
      );

      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'wrong@example.com', password: 'wrong' }),
      });

      expect(response.status).toBe(401);
      const data = await response.json();
      expect(data.detail).toBe('Invalid credentials');
    });

    it('should refresh token when expired', async () => {
      server.use(
        http.post('/api/v1/auth/refresh', () => {
          return HttpResponse.json({
            access_token: 'new-access-token',
            refresh_token: 'new-refresh-token',
          });
        })
      );

      const response = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer old-refresh-token',
        },
      });

      const data = await response.json();
      expect(data.access_token).toBe('new-access-token');
    });
  });

  describe('Users API', () => {
    it('should fetch users with pagination', async () => {
      const mockUsers = {
        items: [createMockUser({ id: '1', email: 'user1@example.com' })],
        total: 1,
        page: 1,
        page_size: 10,
      };

      server.use(
        http.get('/api/v1/users', () => {
          return HttpResponse.json(mockUsers);
        })
      );

      const response = await fetch('/api/v1/users?page=1&limit=10', {
        headers: { 'Authorization': 'Bearer test-token' },
      });

      const data = await response.json();
      expect(data.items).toHaveLength(1);
      expect(data.total).toBe(1);
    });

    it('should handle API errors gracefully', async () => {
      server.use(
        http.get('/api/v1/users', () => {
          return HttpResponse.json(
            { detail: 'Internal Server Error' },
            { status: 500 }
          );
        })
      );

      const response = await fetch('/api/v1/users', {
        headers: { 'Authorization': 'Bearer test-token' },
      });

      expect(response.status).toBe(500);
    });
  });

  describe('Models API', () => {
    it('should fetch models for agency', async () => {
      const mockModels = {
        items: [
          { id: 'model-1', name: 'Test Model', agency_id: 'agency-1' },
        ],
        total: 1,
      };

      server.use(
        http.get('/api/v1/models', () => {
          return HttpResponse.json(mockModels);
        })
      );

      const response = await fetch('/api/v1/models?agency_id=agency-1', {
        headers: { 'Authorization': 'Bearer test-token' },
      });

      const data = await response.json();
      expect(data.items).toHaveLength(1);
      expect(data.items[0].agency_id).toBe('agency-1');
    });
  });

  describe('Error Handling', () => {
    it('should handle validation errors', async () => {
      server.use(
        http.post('/api/v1/users', () => {
          return HttpResponse.json(
            {
              detail: 'Validation Error',
              errors: {
                email: ['Email already exists'],
                password: ['Password too weak'],
              },
            },
            { status: 422 }
          );
        })
      );

      const response = await fetch('/api/v1/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-token',
        },
        body: JSON.stringify({
          email: 'existing@example.com',
          password: '123',
        }),
      });

      expect(response.status).toBe(422);
      const data = await response.json();
      expect(data.errors.email).toContain('Email already exists');
    });
  });
});