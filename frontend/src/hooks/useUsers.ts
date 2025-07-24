import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usersService, CreateUserData, UpdateUserData } from '@/services/api/users';
import { QueryParams } from '@/types/api';
import { useToast } from '@/components/common/Toaster';

export const useUsers = (params?: QueryParams) => {
  return useQuery({
    queryKey: ['users', params],
    queryFn: () => usersService.getUsers(params),
  });
};

export const useUser = (userId: string) => {
  return useQuery({
    queryKey: ['users', userId],
    queryFn: () => usersService.getUser(userId),
    enabled: !!userId,
  });
};

export const useCreateUser = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (data: CreateUserData) => usersService.createUser(data),
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
      usersService.updateUser(userId, data),
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
    mutationFn: (userId: string) => usersService.deleteUser(userId),
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
    mutationFn: (userIds: string[]) => usersService.deleteUsers(userIds),
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
      usersService.toggleUserStatus(userId, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      success('User status updated');
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Failed to update user status');
    },
  });
};