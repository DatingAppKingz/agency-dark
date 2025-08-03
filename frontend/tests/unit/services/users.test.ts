import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { userService, User, CreateUserData, UpdateUserData } from '@/services/api/users';
import apiClient from '@/services/api/client';
import { UserRole } from '@/types/auth';

// Mock dependencies
vi.mock('@/services/api/client');
const mockedApiClient = apiClient as any;

describe('User Service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getUsers', () => {
    it('should fetch paginated users', async () => {
      const mockResponse = {
        data: [
          {
            id: 'user1',
            email: 'user1@example.com',
            full_name: 'User One',
            role: UserRole.ADMIN,
            is_active: true,
            is_verified: true,
            created_at: '2025-01-31T10:00:00Z'
          },
          {
            id: 'user2',
            email: 'user2@example.com',
            full_name: 'User Two',
            role: UserRole.MODEL,
            is_active: true,
            is_verified: false,
            created_at: '2025-01-31T11:00:00Z'
          }
        ],
        total: 2,
        page: 1,
        per_page: 20,
        pages: 1
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockResponse });

      const result = await userService.getUsers();

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/users', {
        params: { per_page: undefined }
      });
      expect(result).toEqual(mockResponse);
    });

    it('should fetch users with filters', async () => {
      const params = {
        role: UserRole.MODEL,
        agency_id: 'agency123',
        is_active: true,
        search: 'jane',
        page: 2,
        limit: 50
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: { data: [], total: 0 } });

      await userService.getUsers(params);

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/users', {
        params: {
          role: UserRole.MODEL,
          agency_id: 'agency123',
          is_active: true,
          search: 'jane',
          page: 2,
          limit: 50,
          per_page: 50
        }
      });
    });

    it('should handle empty params', async () => {
      mockedApiClient.get.mockResolvedValueOnce({ data: { data: [] } });

      await userService.getUsers({});

      expect(mockedApiClient.get).toHaveBeenCalledWith('/api/v1/users', {
        params: { per_page: undefined }
      });
    });
  });

  describe('getUser', () => {
    it('should fetch a single user by ID', async () => {
      const userId = 'user123';
      const mockUser: User = {
        id: userId,
        email: 'user@example.com',
        full_name: 'Test User',
        username: 'testuser',
        role: UserRole.ADMIN,
        is_active: true,
        is_verified: true,
        created_at: '2025-01-31T10:00:00Z',
        last_login: '2025-01-31T15:00:00Z'
      };

      mockedApiClient.get.mockResolvedValueOnce({ data: mockUser });

      const result = await userService.getUser(userId);

      expect(mockedApiClient.get).toHaveBeenCalledWith(`/api/v1/users/${userId}`);
      expect(result).toEqual(mockUser);
    });

    it('should handle 404 errors', async () => {
      const error = {
        response: { status: 404, data: { message: 'User not found' } }
      };
      mockedApiClient.get.mockRejectedValueOnce(error);

      await expect(userService.getUser('nonexistent')).rejects.toMatchObject(error);
    });
  });

  describe('createUser', () => {
    it('should create a new user', async () => {
      const createData: CreateUserData = {
        email: 'newuser@example.com',
        full_name: 'New User',
        role: UserRole.MODEL,
        password: 'securePassword123!',
        agency_id: 'agency456'
      };

      const mockCreatedUser: User = {
        id: 'user789',
        ...createData,
        is_active: true,
        is_verified: false,
        created_at: new Date().toISOString()
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockCreatedUser });

      const result = await userService.createUser(createData);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/users', createData);
      expect(result).toEqual(mockCreatedUser);
    });

    it('should create user without agency_id', async () => {
      const createData: CreateUserData = {
        email: 'admin@example.com',
        full_name: 'Admin User',
        role: UserRole.ADMIN,
        password: 'adminPass123!'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: {} });

      await userService.createUser(createData);

      expect(mockedApiClient.post).toHaveBeenCalledWith('/api/v1/users', createData);
    });

    it('should handle validation errors', async () => {
      const error = {
        response: {
          status: 400,
          data: { message: 'Email already exists' }
        }
      };
      mockedApiClient.post.mockRejectedValueOnce(error);

      await expect(userService.createUser({
        email: 'existing@example.com',
        full_name: 'Test',
        role: UserRole.MODEL,
        password: 'pass123'
      })).rejects.toMatchObject(error);
    });
  });

  describe('updateUser', () => {
    it('should update user data', async () => {
      const userId = 'user123';
      const updateData: UpdateUserData = {
        email: 'updated@example.com',
        full_name: 'Updated Name',
        is_active: false
      };

      const mockUpdatedUser: User = {
        id: userId,
        email: updateData.email!,
        full_name: updateData.full_name,
        role: UserRole.MODEL,
        is_active: updateData.is_active!,
        is_verified: true,
        created_at: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.put.mockResolvedValueOnce({ data: mockUpdatedUser });

      const result = await userService.updateUser(userId, updateData);

      expect(mockedApiClient.put).toHaveBeenCalledWith(`/api/v1/users/${userId}`, updateData);
      expect(result).toEqual(mockUpdatedUser);
    });

    it('should update single field', async () => {
      const userId = 'user123';
      const updateData: UpdateUserData = { is_verified: true };

      mockedApiClient.put.mockResolvedValueOnce({ data: {} });

      await userService.updateUser(userId, updateData);

      expect(mockedApiClient.put).toHaveBeenCalledWith(
        `/api/v1/users/${userId}`,
        { is_verified: true }
      );
    });
  });

  describe('deleteUser', () => {
    it('should delete a user', async () => {
      const userId = 'user123';
      mockedApiClient.delete.mockResolvedValueOnce({});

      await userService.deleteUser(userId);

      expect(mockedApiClient.delete).toHaveBeenCalledWith(`/api/v1/users/${userId}`);
    });

    it('should handle deletion errors', async () => {
      const error = new Error('Deletion failed');
      mockedApiClient.delete.mockRejectedValueOnce(error);

      await expect(userService.deleteUser('user123')).rejects.toThrow('Deletion failed');
    });
  });

  describe('deleteUsers', () => {
    it('should bulk delete multiple users', async () => {
      const userIds = ['user1', 'user2', 'user3'];
      mockedApiClient.post.mockResolvedValueOnce({});

      await userService.deleteUsers(userIds);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/api/v1/users/bulk-delete',
        { ids: userIds }
      );
    });

    it('should handle empty array', async () => {
      mockedApiClient.post.mockResolvedValueOnce({});

      await userService.deleteUsers([]);

      expect(mockedApiClient.post).toHaveBeenCalledWith(
        '/api/v1/users/bulk-delete',
        { ids: [] }
      );
    });
  });

  describe('toggleUserStatus', () => {
    it('should activate user when isActive is true', async () => {
      const userId = 'user123';
      const mockActivatedUser: User = {
        id: userId,
        email: 'user@example.com',
        role: UserRole.MODEL,
        is_active: true,
        is_verified: true,
        created_at: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockActivatedUser });

      const result = await userService.toggleUserStatus(userId, true);

      expect(mockedApiClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/activate`);
      expect(result).toEqual(mockActivatedUser);
    });

    it('should deactivate user when isActive is false', async () => {
      const userId = 'user123';
      const mockDeactivatedUser: User = {
        id: userId,
        email: 'user@example.com',
        role: UserRole.MODEL,
        is_active: false,
        is_verified: true,
        created_at: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockDeactivatedUser });

      const result = await userService.toggleUserStatus(userId, false);

      expect(mockedApiClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/deactivate`);
      expect(result).toEqual(mockDeactivatedUser);
    });
  });

  describe('activateUser', () => {
    it('should activate a user', async () => {
      const userId = 'user123';
      const mockUser: User = {
        id: userId,
        email: 'user@example.com',
        role: UserRole.MODEL,
        is_active: true,
        is_verified: true,
        created_at: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockUser });

      const result = await userService.activateUser(userId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/activate`);
      expect(result).toEqual(mockUser);
      expect(result.is_active).toBe(true);
    });
  });

  describe('deactivateUser', () => {
    it('should deactivate a user', async () => {
      const userId = 'user123';
      const mockUser: User = {
        id: userId,
        email: 'user@example.com',
        role: UserRole.MODEL,
        is_active: false,
        is_verified: true,
        created_at: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockUser });

      const result = await userService.deactivateUser(userId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/deactivate`);
      expect(result).toEqual(mockUser);
      expect(result.is_active).toBe(false);
    });
  });

  describe('verifyUser', () => {
    it('should verify a user', async () => {
      const userId = 'user123';
      const mockUser: User = {
        id: userId,
        email: 'user@example.com',
        role: UserRole.MODEL,
        is_active: true,
        is_verified: true,
        created_at: '2025-01-31T10:00:00Z'
      };

      mockedApiClient.post.mockResolvedValueOnce({ data: mockUser });

      const result = await userService.verifyUser(userId);

      expect(mockedApiClient.post).toHaveBeenCalledWith(`/api/v1/users/${userId}/verify`);
      expect(result).toEqual(mockUser);
      expect(result.is_verified).toBe(true);
    });
  });

  describe('error handling', () => {
    it('should propagate network errors', async () => {
      const networkError = new Error('Network failure');
      mockedApiClient.get.mockRejectedValueOnce(networkError);

      await expect(userService.getUsers()).rejects.toThrow('Network failure');
    });

    it('should handle API validation errors', async () => {
      const validationError = {
        response: {
          status: 422,
          data: {
            message: 'Validation failed',
            errors: {
              email: ['Email is required'],
              password: ['Password must be at least 8 characters']
            }
          }
        }
      };
      mockedApiClient.post.mockRejectedValueOnce(validationError);

      await expect(userService.createUser({
        email: '',
        full_name: 'Test',
        role: UserRole.MODEL,
        password: 'short'
      })).rejects.toMatchObject(validationError);
    });

    it('should handle authorization errors', async () => {
      const authError = {
        response: {
          status: 403,
          data: { message: 'Insufficient permissions' }
        }
      };
      mockedApiClient.delete.mockRejectedValueOnce(authError);

      await expect(userService.deleteUser('user123')).rejects.toMatchObject(authError);
    });
  });
});