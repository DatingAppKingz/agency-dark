import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { apiKeysService } from '@/services/api/apiKeys';
import {
  ApiKeyCreateRequest,
  ApiKeyUpdateRequest,
  ApiKeyRotateRequest,
  ApiKeyFilters
} from '@/types/apiKeys';

type ApiError = {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

const QUERY_KEY = 'apiKeys';

export const useApiKeys = (filters?: ApiKeyFilters) => {
  return useQuery({
    queryKey: [QUERY_KEY, filters],
    queryFn: () => apiKeysService.list(filters) });
};

export const useApiKey = (id: string | null) => {
  return useQuery({
    queryKey: [QUERY_KEY, id],
    queryFn: () => id ? apiKeysService.get(id) : null,
    enabled: !!id });
};

export const useApiKeyUsageStats = (id: string | null, days: number = 30) => {
  return useQuery({
    queryKey: [QUERY_KEY, 'usage', id, days],
    queryFn: () => id ? apiKeysService.getUsageStats(id, days) : null,
    enabled: !!id });
};

export const useApiKeyAuditLogs = (id: string | null) => {
  return useQuery({
    queryKey: [QUERY_KEY, 'audit', id],
    queryFn: () => id ? apiKeysService.getAuditLogs(id) : null,
    enabled: !!id });
};

export const useCreateApiKey = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: ApiKeyCreateRequest) => apiKeysService.create(data),
    onSuccess: (newKey) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success(`API key "${newKey.name}" created successfully`);
    },
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || 'Failed to create API key');
    } });
};

export const useUpdateApiKey = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ApiKeyUpdateRequest }) => 
      apiKeysService.update(id, data),
    onSuccess: (updatedKey) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, updatedKey.id] });
      toast.success('API key updated successfully');
    },
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || 'Failed to update API key');
    } });
};

export const useRotateApiKey = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ApiKeyRotateRequest }) => 
      apiKeysService.rotate(id, data),
    onSuccess: (rotatedKey) => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY, rotatedKey.id] });
      toast.success('API key rotated successfully. Please update your integrations.');
    },
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || 'Failed to rotate API key');
    } });
};

export const useDeleteApiKey = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (id: string) => apiKeysService.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
      toast.success('API key deleted successfully');
    },
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || 'Failed to delete API key');
    } });
};

export const useValidateApiKey = () => {
  return useMutation({
    mutationFn: ({ provider, key }: { provider: string; key: string }) => 
      apiKeysService.validate(provider, key),
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || 'Failed to validate API key');
    } });
};

export const useTestApiKey = () => {
  return useMutation({
    mutationFn: (id: string) => apiKeysService.testConnection(id),
    onSuccess: (result) => {
      if (result.success) {
        toast.success(result.message || 'API key connection successful');
      } else {
        toast.error(result.message || 'API key connection failed');
      }
    },
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || 'Failed to test API key');
    } });
};

export const useProviderScopes = (provider: string | null) => {
  return useQuery({
    queryKey: [QUERY_KEY, 'scopes', provider],
    queryFn: () => provider ? apiKeysService.getProviderScopes(provider) : null,
    enabled: !!provider });
};
