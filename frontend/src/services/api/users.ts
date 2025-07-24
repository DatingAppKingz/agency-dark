import apiClient from './client';
import { User } from '@/types/auth';
import { PaginatedResponse, QueryParams } from '@/types/api';

export interface CreateUserData {
  email: string;
  password: string;
  full_name: string;
  role: string;
  is_active?: boolean;
}

export interface UpdateUserData {
  full_name?: string;
  role?: string;
  is_active?: boolean;
}

export const usersService = {
  // Get paginated users list
  async getUsers(params?: QueryParams): Promise<PaginatedResponse<User>> {
    const { data } = await apiClient.get('/users', { params });
    return data;
  },

  // Get single user by ID
  async getUser(userId: string): Promise<User> {
    const { data } = await apiClient.get(`/users/${userId}`);
    return data;
  },

  // Create new user
  async createUser(userData: CreateUserData): Promise<User> {
    const { data } = await apiClient.post('/users', userData);
    return data;
  },

  // Update user
  async updateUser(userId: string, userData: UpdateUserData): Promise<User> {
    const { data } = await apiClient.put(`/users/${userId}`, userData);
    return data;
  },

  // Delete user
  async deleteUser(userId: string): Promise<void> {
    await apiClient.delete(`/users/${userId}`);
  },

  // Bulk delete users
  async deleteUsers(userIds: string[]): Promise<void> {
    await apiClient.post('/users/bulk-delete', { user_ids: userIds });
  },

  // Toggle user status
  async toggleUserStatus(userId: string, isActive: boolean): Promise<User> {
    const { data } = await apiClient.patch(`/users/${userId}/status`, { 
      is_active: isActive 
    });
    return data;
  },

  // Reset user password
  async resetUserPassword(userId: string): Promise<{ temporary_password: string }> {
    const { data } = await apiClient.post(`/users/${userId}/reset-password`);
    return data;
  },
};