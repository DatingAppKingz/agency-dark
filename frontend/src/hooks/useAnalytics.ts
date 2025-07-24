import { useQuery } from '@tanstack/react-query';
import { analyticsService } from '@/services/api/analytics';

export const useDashboardStats = () => {
  return useQuery({
    queryKey: ['analytics', 'dashboard'],
    queryFn: () => analyticsService.getDashboardStats(),
    refetchInterval: 60000, // Refresh every minute
  });
};

export const useAgencyStats = () => {
  return useQuery({
    queryKey: ['analytics', 'agencies'],
    queryFn: () => analyticsService.getAgencyStats(),
    refetchInterval: 300000, // Refresh every 5 minutes
  });
};

export const useModelPerformance = (period: 'day' | 'week' | 'month' = 'month') => {
  return useQuery({
    queryKey: ['analytics', 'models', period],
    queryFn: () => analyticsService.getModelPerformance(period),
  });
};

export const useRevenueChart = (period: 'day' | 'week' | 'month' = 'month') => {
  return useQuery({
    queryKey: ['analytics', 'revenue-chart', period],
    queryFn: () => analyticsService.getRevenueChart(period),
  });
};

export const useMessageChart = (period: 'day' | 'week' | 'month' = 'month') => {
  return useQuery({
    queryKey: ['analytics', 'message-chart', period],
    queryFn: () => analyticsService.getMessageChart(period),
  });
};