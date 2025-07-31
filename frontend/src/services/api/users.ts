import apiClient from './client';
import { UserRole } from '@/types/auth';

export interface User {
  id: string;
  agency_id?: string;
  email: string;
  full_name?: string;
  username?: string;
  stage_name?: string;
  role: UserRole;
  is_active: boolean;
  is_verified: boolean;
  last_login?: string;
  created_at: string;
  avatar_url?: string;
}

export interface PaginatedUsers {
  data: User[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface CreateUserData {
  email: string;
  full_name: string;
  role: UserRole;
  password: string;
  agency_id?: string;
}

export interface UpdateUserData {
  email?: string;
  full_name?: string;
  role?: UserRole;
  is_active?: boolean;
  is_verified?: boolean;
}

export const userService = {
  async getUsers(params?: {
    role?: UserRole;
    agency_id?: string;
    is_active?: boolean;
    search?: string;
    page?: number;
    limit?: number;
  }): Promise<PaginatedUsers> {
    const response = await apiClient.get('/api/v1/users', {
      params: {
        ...params,
        per_page: params?.limit,
      }
    });
    return response.data;
  },

  async getUser(id: string): Promise<User> {
    const response = await apiClient.get(`/api/v1/users/${id}`);
    return response.data;
  },

  async createUser(data: CreateUserData): Promise<User> {
    const response = await apiClient.post('/api/v1/users', data);
    return response.data;
  },

  async updateUser(id: string, data: UpdateUserData): Promise<User> {
    const response = await apiClient.put(`/api/v1/users/${id}`, data);
    return response.data;
  },

  async deleteUser(id: string): Promise<void> {
    await apiClient.delete(`/api/v1/users/${id}`);
  },

  async deleteUsers(ids: string[]): Promise<void> {
    await apiClient.post('/api/v1/users/bulk-delete', { ids });
  },

  async toggleUserStatus(id: string, isActive: boolean): Promise<User> {
    const response = await apiClient.post(`/api/v1/users/${id}/${isActive ? 'activate' : 'deactivate'}`);
    return response.data;
  },

  async activateUser(id: string): Promise<User> {
    const response = await apiClient.post(`/api/v1/users/${id}/activate`);
    return response.data;
  },

  async deactivateUser(id: string): Promise<User> {
    const response = await apiClient.post(`/api/v1/users/${id}/deactivate`);
    return response.data;
  },

  async verifyUser(id: string): Promise<User> {
    const response = await apiClient.post(`/api/v1/users/${id}/verify`);
    return response.data;
  },
};
