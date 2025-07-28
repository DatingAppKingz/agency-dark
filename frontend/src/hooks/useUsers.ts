import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { userService, CreateUserData, UpdateUserData } from '@/services/api/users';
import { QueryParams } from '@/types/api';
import { useToast } from '@/components/common/Toaster';

export const useUsers = (params?: QueryParams) => {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => userService.getUsers(params),
  });
};

export const useUser = (userId: string) => {
  return useQuery({
    queryKey: ['users', userId],
    queryFn: () => userService.getUser(userId),
    enabled: !!userId,
  });
};

export const useCreateUser = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (data: CreateUserData) => userService.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      success('User created successfully');
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Failed to create user');
    },
  });
};

export const useUpdateUser = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: UpdateUserData }) =>
      userService.updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      success('User updated successfully');
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Failed to update user');
    },
  });
};

export const useDeleteUser = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (userId: string) => userService.deleteUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      success('User deleted successfully');
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Failed to delete user');
    },
  });
};

export const useDeleteUsers = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (userIds: string[]) => userService.deleteUsers(userIds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      success('Users deleted successfully');
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Failed to delete users');
    },
  });
};

export const useToggleUserStatus = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({ userId, isActive }: { userId: string; isActive: boolean }) =>
      userService.toggleUserStatus(userId, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      success('User status updated');
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Failed to update user status');
    },
  });
};