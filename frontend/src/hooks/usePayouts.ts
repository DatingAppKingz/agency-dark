import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { payoutService } from '@/services/financial';
import { Payout } from '@/types/financial';
import { useToast } from '@/hooks/useToast';

interface PayoutFilters {
  status?: string;
  modelId?: number;
  startDate?: string;
  endDate?: string;
  limit?: number;
  offset?: number;
}

export const usePayouts = (filters?: PayoutFilters) => {
  return useQuery({
    queryKey: ['payouts', filters],
    queryFn: () => payoutService.getPayouts(filters),
  });
};

export const usePayout = (id: number) => {
  return useQuery({
    queryKey: ['payout', id],
    queryFn: () => payoutService.getPayout(id),
    enabled: !!id,
  });
};

export const usePayoutEarnings = (payoutId: number) => {
  return useQuery({
    queryKey: ['payout-earnings', payoutId],
    queryFn: () => payoutService.getPayoutEarnings(payoutId),
    enabled: !!payoutId,
  });
};

export const useCreatePayout = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: (data: {
      model_id: number;
      period_start: string;
      period_end: string;
      payment_method_id: number;
      adjustments?: number;
      notes?: string;
      scheduled_date?: string;
    }) => payoutService.createPayout(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['payouts'] });
      queryClient.invalidateQueries({ queryKey: ['earnings'] });
      showToast('Payout created successfully', 'success');
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to create payout', 'error');
    },
  });
};

export const useUpdatePayout = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Payout> }) =>
      payoutService.updatePayout(id, data),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['payouts'] });
      queryClient.invalidateQueries({ queryKey: ['payout', variables.id] });
      showToast('Payout updated successfully', 'success');
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to update payout', 'error');
    },
  });
};

export const useApprovePayout = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: ({ id, approved, notes }: { id: number; approved: boolean; notes?: string }) =>
      payoutService.approvePayout(id, approved, notes),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['payouts'] });
      queryClient.invalidateQueries({ queryKey: ['payout', variables.id] });
      showToast(
        variables.approved ? 'Payout approved' : 'Payout rejected',
        variables.approved ? 'success' : 'warning'
      );
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to process payout approval', 'error');
    },
  });
};

export const useBulkPayoutAction = () => {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  return useMutation({
    mutationFn: ({
      payoutIds,
      action,
      notes,
    }: {
      payoutIds: number[];
      action: 'approve' | 'process' | 'cancel';
      notes?: string;
    }) => payoutService.bulkPayoutAction(payoutIds, action, notes),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['payouts'] });
      showToast(
        `${data.success} payouts ${data.action}ed successfully`,
        data.errors > 0 ? 'warning' : 'success'
      );
    },
    onError: (error: any) => {
      showToast(error.response?.data?.detail || 'Failed to perform bulk action', 'error');
    },
  });
};