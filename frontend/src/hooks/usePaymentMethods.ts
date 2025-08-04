import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { paymentMethodService } from '@/services/financial';
import { PaymentMethod } from '@/types/financial';
import { useToast } from '@/hooks/useToast';

export const usePaymentMethods = (modelId?: number, agencyId?: number) => {
  return useQuery({
    queryKey: ['payment-methods', modelId, agencyId],
    queryFn: () => paymentMethodService.getPaymentMethods(modelId, agencyId),
    enabled: !!(modelId || agencyId),
  });
};

export const usePaymentMethod = (id: number) => {
  return useQuery({
    queryKey: ['payment-method', id],
    queryFn: () => paymentMethodService.getPaymentMethod(id),
    enabled: !!id,
  });
};

export const useCreatePaymentMethod = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: (data: Partial<PaymentMethod>) => 
      paymentMethodService.createPaymentMethod(data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
      showToast('Payment method added successfully', 'success');
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to add payment method', 'error');
    },
  });
};

export const useUpdatePaymentMethod = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<PaymentMethod> }) =>
      paymentMethodService.updatePaymentMethod(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
      queryClient.invalidateQueries({ queryKey: ['payment-method', variables.id] });
      showToast('Payment method updated successfully', 'success');
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to update payment method', 'error');
    },
  });
};

export const useDeletePaymentMethod = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: (id: number) => paymentMethodService.deletePaymentMethod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
      showToast('Payment method deleted successfully', 'success');
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to delete payment method', 'error');
    },
  });
};

export const useSetPrimaryPaymentMethod = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: (id: number) => paymentMethodService.setPrimaryPaymentMethod(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
      showToast('Primary payment method updated', 'success');
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to set primary payment method', 'error');
    },
  });
};

export const useVerifyPaymentMethod = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: ({ id, verified, notes }: { id: number; verified: boolean; notes?: string }) =>
      paymentMethodService.verifyPaymentMethod(id, verified, notes),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['payment-methods'] });
      queryClient.invalidateQueries({ queryKey: ['payment-method', variables.id] });
      showToast(
        variables.verified ? 'Payment method verified' : 'Payment method verification removed',
        'success'
      );
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to verify payment method', 'error');
    },
  });
};