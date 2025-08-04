import React, { useEffect } from 'react';
import { performanceService } from '../services/performanceService';
import { cacheService, createQueryCacheAdapter } from '../services/cacheService';
import { optimisticUpdateService } from '../services/optimisticUpdateService';
import { useQueryClient } from '@tanstack/react-query';

interface PerformanceProviderProps {
  children: React.ReactNode;
  reportToAnalytics?: boolean;
  enableCaching?: boolean;
  enableOptimisticUpdates?: boolean;
}

export const PerformanceProvider: React.FC<PerformanceProviderProps> = ({
  children,
  reportToAnalytics = true,
  enableCaching = true,
  enableOptimisticUpdates = true,
}) => {
  const queryClient = useQueryClient();

  useEffect(() => {
    // Initialize performance monitoring
    performanceService.onReport((metrics) => {
      // Log performance metrics in development
      if (process.env.NODE_ENV === 'development') {
        console.log('Web Vitals:', metrics);
      }

      // Report to analytics if enabled
      if (reportToAnalytics && window.gtag) {
        Object.entries(metrics).forEach(([metric, value]) => {
          if (value !== null) {
            window.gtag('event', metric, {
              value: Math.round(value),
              metric_name: metric,
              event_category: 'Web Vitals',
            });
          }
        });
      }
    });

    // Set up cache service
    if (enableCaching) {
      cacheService.setQueryClient(queryClient);
      
      // Preload critical data
      const criticalEndpoints = [
        { key: '/api/v1/auth/me', fetcher: () => fetch('/api/v1/auth/me').then(r => r.json()), priority: 10 },
        { key: '/api/v1/models', fetcher: () => fetch('/api/v1/models').then(r => r.json()), priority: 8 },
        { key: '/api/v1/users/current', fetcher: () => fetch('/api/v1/users/current').then(r => r.json()), priority: 9 },
      ];
      
      // Warm cache on app start
      cacheService.preload(criticalEndpoints).catch(console.error);
    }

    // Set up optimistic updates
    if (enableOptimisticUpdates) {
      optimisticUpdateService.setQueryClient(queryClient);
    }

    // Monitor memory usage in development
    if (process.env.NODE_ENV === 'development') {
      const memoryInterval = setInterval(() => {
        if ('memory' in performance) {
          const memory = (performance as any).memory;
          const usedMB = Math.round(memory.usedJSHeapSize / 1048576);
          const totalMB = Math.round(memory.totalJSHeapSize / 1048576);
          
          if (usedMB > totalMB * 0.9) {
            console.warn(`High memory usage: ${usedMB}MB / ${totalMB}MB`);
          }
        }
      }, 30000); // Check every 30 seconds

      return () => {
        clearInterval(memoryInterval);
        performanceService.cleanup();
      };
    }

    return () => {
      performanceService.cleanup();
    };
  }, [queryClient, reportToAnalytics, enableCaching, enableOptimisticUpdates]);

  // Provide performance context if needed in future
  return <>{children}</>;
};

// Hook to use performance metrics
export const usePerformanceMetrics = () => {
  const [metrics, setMetrics] = React.useState(performanceService.getMetrics());

  useEffect(() => {
    performanceService.onReport(setMetrics);
  }, []);

  return metrics;
};

// Hook to measure custom timings
export const usePerformanceTiming = (name: string) => {
  const startMarkRef = React.useRef<string>(`${name}-start-${Date.now()}`);
  const endMarkRef = React.useRef<string>(`${name}-end-${Date.now()}`);

  useEffect(() => {
    performanceService.markCustomTiming(startMarkRef.current);
    
    return () => {
      performanceService.markCustomTiming(endMarkRef.current);
      const duration = performanceService.measureCustomTiming(
        name,
        startMarkRef.current,
        endMarkRef.current
      );
      
      if (duration !== null && process.env.NODE_ENV === 'development') {
        console.log(`${name} took ${duration}ms`);
      }
    };
  }, [name]);
};