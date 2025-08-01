import { useState, useEffect, useCallback, useRef } from 'react';
import realtimeAnalyticsService, {
  MetricType,
  TimeWindow,
  RealtimeMetrics,
  MetricSummary,
  MetricUpdate
} from '../services/analytics/realtimeAnalytics';
import { useAuth } from './useAuth';
import { toast } from 'react-hot-toast';

interface UseRealtimeAnalyticsOptions {
  agencyId: string;
  modelId?: string;
  autoConnect?: boolean;
  metrics?: MetricType[];
  onError?: (error: Error) => void;
}

interface UseRealtimeAnalyticsReturn {
  isConnected: boolean;
  isLoading: boolean;
  metrics: RealtimeMetrics;
  summary: MetricSummary | null;
  error: Error | null;
  connect: () => Promise<void>;
  disconnect: () => void;
  subscribe: (metrics: MetricType[]) => void;
  unsubscribe: (metrics: MetricType[]) => void;
  trackMetric: (update: MetricUpdate) => Promise<void>;
  refreshSummary: () => Promise<void>;
  getHistoricalMetrics: (
    metricTypes: MetricType[],
    window?: TimeWindow,
    limit?: number
  ) => Promise<RealtimeMetrics>;
}

export const useRealtimeAnalytics = ({
  agencyId,
  modelId,
  autoConnect = true,
  metrics = [MetricType.REVENUE, MetricType.SUBSCRIBERS],
  onError
}: UseRealtimeAnalyticsOptions): UseRealtimeAnalyticsReturn => {
  const { user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [realtimeMetrics, setRealtimeMetrics] = useState<RealtimeMetrics>({});
  const [summary, setSummary] = useState<MetricSummary | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const connectionRef = useRef(false);
  const subscribedMetricsRef = useRef<MetricType[]>([]);

  // Handle connection
  const connect = useCallback(async () => {
    if (connectionRef.current || !user?.token) {
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      
      await realtimeAnalyticsService.connect(agencyId, modelId, user.token);
      connectionRef.current = true;

      // Subscribe to initial metrics
      if (metrics.length > 0) {
        realtimeAnalyticsService.subscribe(metrics);
        subscribedMetricsRef.current = metrics;
      }
    } catch (err) {
      const error = err as Error;
      setError(error);
      if (onError) {
        onError(error);
      } else {
        toast.error(`Failed to connect: ${error.message}`);
      }
    }
  }, [agencyId, modelId, user?.token, metrics, onError]);

  // Handle disconnection
  const disconnect = useCallback(() => {
    if (!connectionRef.current) {
      return;
    }

    realtimeAnalyticsService.disconnect();
    connectionRef.current = false;
    setIsConnected(false);
    subscribedMetricsRef.current = [];
  }, []);

  // Subscribe to metrics
  const subscribe = useCallback((newMetrics: MetricType[]) => {
    const metricsToSubscribe = newMetrics.filter(
      m => !subscribedMetricsRef.current.includes(m)
    );

    if (metricsToSubscribe.length > 0) {
      realtimeAnalyticsService.subscribe(metricsToSubscribe);
      subscribedMetricsRef.current = [...subscribedMetricsRef.current, ...metricsToSubscribe];
    }
  }, []);

  // Unsubscribe from metrics
  const unsubscribe = useCallback((metricsToRemove: MetricType[]) => {
    realtimeAnalyticsService.unsubscribe(metricsToRemove);
    subscribedMetricsRef.current = subscribedMetricsRef.current.filter(
      m => !metricsToRemove.includes(m)
    );
  }, []);

  // Track a metric
  const trackMetric = useCallback(async (update: MetricUpdate) => {
    try {
      await realtimeAnalyticsService.trackMetric(update);
    } catch (err) {
      const error = err as Error;
      toast.error(`Failed to track metric: ${error.message}`);
      throw error;
    }
  }, []);

  // Refresh summary
  const refreshSummary = useCallback(async () => {
    try {
      const newSummary = await realtimeAnalyticsService.getAnalyticsSummary();
      setSummary(newSummary);
    } catch (err) {
      const error = err as Error;
      toast.error(`Failed to refresh summary: ${error.message}`);
      throw error;
    }
  }, []);

  // Get historical metrics
  const getHistoricalMetrics = useCallback(async (
    metricTypes: MetricType[],
    window: TimeWindow = TimeWindow.HOUR,
    limit: number = 100
  ): Promise<RealtimeMetrics> => {
    try {
      const dimensions = modelId ? { model_id: modelId } : { agency_id: agencyId };
      return await realtimeAnalyticsService.getRealtimeMetrics(
        metricTypes,
        window,
        limit,
        dimensions
      );
    } catch (err) {
      const error = err as Error;
      toast.error(`Failed to get historical metrics: ${error.message}`);
      throw error;
    }
  }, [agencyId, modelId]);

  // Setup event listeners
  useEffect(() => {
    const handleConnected = () => {
      setIsConnected(true);
      setIsLoading(false);
      toast.success('Connected to real-time analytics');
    };

    const handleDisconnected = () => {
      setIsConnected(false);
      if (connectionRef.current) {
        toast.warning('Disconnected from real-time analytics');
      }
    };

    const handleInitial = (data: MetricSummary) => {
      setSummary(data);
      setIsLoading(false);
    };

    const handleUpdate = (metrics: RealtimeMetrics) => {
      setRealtimeMetrics(prev => ({
        ...prev,
        ...metrics
      }));
    };

    const handleError = (err: Error) => {
      setError(err);
      if (onError) {
        onError(err);
      } else {
        toast.error(`Analytics error: ${err.message}`);
      }
    };

    const handleMaxReconnect = () => {
      setError(new Error('Maximum reconnection attempts reached'));
      toast.error('Unable to establish real-time connection');
    };

    // Add event listeners
    realtimeAnalyticsService.on('connected', handleConnected);
    realtimeAnalyticsService.on('disconnected', handleDisconnected);
    realtimeAnalyticsService.on('initial', handleInitial);
    realtimeAnalyticsService.on('update', handleUpdate);
    realtimeAnalyticsService.on('error', handleError);
    realtimeAnalyticsService.on('max_reconnect_reached', handleMaxReconnect);

    // Cleanup
    return () => {
      realtimeAnalyticsService.off('connected', handleConnected);
      realtimeAnalyticsService.off('disconnected', handleDisconnected);
      realtimeAnalyticsService.off('initial', handleInitial);
      realtimeAnalyticsService.off('update', handleUpdate);
      realtimeAnalyticsService.off('error', handleError);
      realtimeAnalyticsService.off('max_reconnect_reached', handleMaxReconnect);
    };
  }, [onError]);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect && user?.token) {
      connect();
    }

    return () => {
      if (connectionRef.current) {
        disconnect();
      }
    };
  }, [autoConnect, user?.token, connect, disconnect]);

  return {
    isConnected,
    isLoading,
    metrics: realtimeMetrics,
    summary,
    error,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    trackMetric,
    refreshSummary,
    getHistoricalMetrics
  };
};