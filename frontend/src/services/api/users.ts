import apiClient from './client';
import { User } from '@/types/auth';
import { PaginatedResponse, QueryParams } from '@/types/api';

export interface CreateUserData {
  email: string;
  password: string;
  full_name: string;
  role: string;
  agency_id?: string;
  is_active?: boolean;
}

export interface UpdateUserData {
  full_name?: string;
  role?: string;
  is_active?: boolean;
}

export const usersService = {
  // Get current user info
  async getCurrentUser(): Promise<User> {
    const { data } = await apiClient.get('/auth/me');
    return data;
  },

  // Register new user (only endpoint available)
  async createUser(userData: CreateUserData): Promise<User> {
    const { data } = await apiClient.post('/auth/register', userData);
    return data;
  },

  // Note: The following methods are placeholders until backend implements user management endpoints
  // For now, they return mock data or throw not implemented errors

  async getUsers(params?: QueryParams): Promise<PaginatedResponse<User>> {
    // TODO: Implement when backend provides user listing endpoint
    console.warn('User listing not yet implemented in backend');
    return {
      data: [],
      total: 0,
      page: params?.page || 1,
      pages: 0,
    };
  },

  async getUser(userId: string): Promise<User> {
    // TODO: Implement when backend provides user detail endpoint
    throw new Error('User detail endpoint not yet implemented');
  },

  async updateUser(userId: string, userData: UpdateUserData): Promise<User> {
    // TODO: Implement when backend provides user update endpoint
    throw new Error('User update endpoint not yet implemented');
  },

  async deleteUser(userId: string): Promise<void> {
    // TODO: Implement when backend provides user delete endpoint
    throw new Error('User delete endpoint not yet implemented');
  },

  async deleteUsers(userIds: string[]): Promise<void> {
    // TODO: Implement when backend provides bulk delete endpoint
    throw new Error('Bulk delete endpoint not yet implemented');
  },

  async toggleUserStatus(userId: string, isActive: boolean): Promise<User> {
    // TODO: Implement when backend provides status toggle endpoint
    throw new Error('Status toggle endpoint not yet implemented');
  },

  async resetUserPassword(userId: string): Promise<{ temporary_password: string }> {
    // TODO: Implement when backend provides password reset endpoint
    throw new Error('Password reset endpoint not yet implemented');
  },
};