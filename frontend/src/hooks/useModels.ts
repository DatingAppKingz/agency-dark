import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { modelsService } from '@/services/api/models';
import { QueryParams } from '@/types/api';
import { CreateModelProfileData, UpdateModelProfileData, ModelPreferences } from '@/types/models';
import { useToast } from '@/components/common/Toaster';

type ApiError = {
  response?: {
    data?: {
      detail?: string;
    };
  };
};

export const useModels = (params?: QueryParams) => {
  return useQuery({
    queryKey: ['models', params],
    queryFn: () => modelsService.getModels(params),
    select: (data) => data?.data || [],
  });
};

export const useModel = (modelId: string) => {
  return useQuery({
    queryKey: ['models', modelId],
    queryFn: () => modelsService.getModel(modelId),
    enabled: !!modelId,
  });
};

export const useCreateModel = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (data: CreateModelProfileData) => modelsService.createModel(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      success('Model profile created successfully');
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to create model profile');
    },
  });
};

export const useUpdateModel = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({ modelId, data }: { modelId: string; data: UpdateModelProfileData }) =>
      modelsService.updateModel(modelId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['models', variables.modelId] });
      success('Model profile updated successfully');
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to update model profile');
    },
  });
};

export const useDeleteModel = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (modelId: string) => modelsService.deleteModel(modelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      success('Model profile deleted successfully');
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to delete model profile');
    },
  });
};

export const useToggleModelStatus = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({ modelId, isActive }: { modelId: string; isActive: boolean }) =>
      modelsService.toggleModelStatus(modelId, isActive),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      success('Model status updated');
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to update model status');
    },
  });
};

export const useModelStats = (modelId: string, period: 'day' | 'week' | 'month' = 'month') => {
  return useQuery({
    queryKey: ['models', modelId, 'stats', period],
    queryFn: () => modelsService.getStats(modelId, period),
    enabled: !!modelId,
  });
};

export const useModelPreferences = (modelId: string) => {
  return useQuery({
    queryKey: ['models', modelId, 'preferences'],
    queryFn: () => modelsService.getPreferences(modelId),
    enabled: !!modelId,
  });
};

export const useUpdateModelPreferences = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({ modelId, preferences }: { modelId: string; preferences: Partial<ModelPreferences> }) =>
      modelsService.updatePreferences(modelId, preferences),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['models', variables.modelId, 'preferences'] });
      success('Preferences updated successfully');
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to update preferences');
    },
  });
};

export const useUploadAvatar = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({ modelId, file }: { modelId: string; file: File }) =>
      modelsService.uploadAvatar(modelId, file),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['models', variables.modelId] });
      success('Avatar uploaded successfully');
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to upload avatar');
    },
  });
};

export const useUploadCover = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: ({ modelId, file }: { modelId: string; file: File }) =>
      modelsService.uploadCover(modelId, file),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['models', variables.modelId] });
      success('Cover image uploaded successfully');
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to upload cover image');
    },
  });
};

export const useBulkUpdateModels = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (data: any) => modelsService.bulkUpdate(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      success(`Successfully updated ${response.successful} models`);
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to update models');
    },
  });
};

export const useBulkDeleteModels = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (data: { model_ids: number[]; permanent: boolean }) =>
      modelsService.bulkDelete(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      success(`Successfully deleted ${response.successful} models`);
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to delete models');
    },
  });
};

export const useApproveModel = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();

  return useMutation({
    mutationFn: (data: {
      model_id: number;
      approved: boolean;
      rejection_reason?: string;
      notes?: string;
    }) => modelsService.approveModel(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['models'] });
      queryClient.invalidateQueries({ queryKey: ['pending-models'] });
      success(response.message);
    },
    onError: (err: ApiError) => {
      error(err.response?.data?.detail || 'Failed to process model approval');
    },
  });
};

export const usePendingModels = (params?: { limit?: number; offset?: number }) => {
  return useQuery({
    queryKey: ['pending-models', params],
    queryFn: () => modelsService.getPendingModels(params),
  });
};
