import { useState, useCallback, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { errorReportingService } from '@/services/errorReportingService';

interface RetryConfig {
  maxAttempts?: number;
  delay?: number;
  backoff?: 'linear' | 'exponential';
  onRetry?: (attempt: number, error: Error) => void;
}

interface ErrorRecoveryOptions {
  enableAutoRecovery?: boolean;
  recoveryStrategies?: RecoveryStrategy[];
  onRecoverySuccess?: () => void;
  onRecoveryFailed?: (error: Error) => void;
}

type RecoveryStrategy = 
  | 'retry'
  | 'refresh'
  | 'redirect'
  | 'reload'
  | 'cache-clear'
  | 'auth-refresh'
  | 'offline-queue';

interface RecoveryContext {
  error: Error;
  strategy: RecoveryStrategy;
  attempt: number;
  metadata?: Record<string, any>;
}

export const useErrorRecovery = (options: ErrorRecoveryOptions = {}) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [isRecovering, setIsRecovering] = useState(false);
  const [recoveryAttempts, setRecoveryAttempts] = useState(0);
  const recoveryInProgress = useRef(false);

  const {
    enableAutoRecovery = true,
    recoveryStrategies = ['retry', 'refresh', 'cache-clear'],
    onRecoverySuccess,
    onRecoveryFailed,
  } = options;

  // Recovery strategy implementations
  const recoveryHandlers: Record<RecoveryStrategy, (context: RecoveryContext) => Promise<void>> = {
    retry: async (context) => {
      // Simple retry - re-execute the failed operation
      await new Promise(resolve => setTimeout(resolve, 1000 * context.attempt));
    },

    refresh: async () => {
      // Refresh current data
      await queryClient.invalidateQueries();
    },

    redirect: async (context) => {
      // Redirect to error page or home
      const redirectPath = context.metadata?.redirectPath || '/';
      navigate(redirectPath);
    },

    reload: async () => {
      // Reload the page
      window.location.reload();
    },

    'cache-clear': async () => {
      // Clear all caches
      queryClient.clear();
      localStorage.removeItem('app-cache');
      sessionStorage.clear();
    },

    'auth-refresh': async () => {
      // Try to refresh authentication
      try {
        const response = await fetch('/api/v1/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        });
        
        if (!response.ok) {
          throw new Error('Auth refresh failed');
        }
        
        // Invalidate auth queries
        await queryClient.invalidateQueries({ queryKey: ['auth'] });
      } catch (error) {
        // Redirect to login
        navigate('/login');
        throw error;
      }
    },

    'offline-queue': async (context) => {
      // Queue operation for when online
      const queuedOperation = {
        id: Date.now(),
        operation: context.metadata?.operation,
        data: context.metadata?.data,
        timestamp: new Date(),
      };
      
      const queue = JSON.parse(localStorage.getItem('offline-queue') || '[]');
      queue.push(queuedOperation);
      localStorage.setItem('offline-queue', JSON.stringify(queue));
    },
  };

  // Determine recovery strategy based on error
  const determineStrategy = (error: Error): RecoveryStrategy[] => {
    const errorMessage = error.message.toLowerCase();
    const strategies: RecoveryStrategy[] = [];

    // Network errors
    if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
      strategies.push('retry', 'offline-queue');
    }

    // Authentication errors
    if (errorMessage.includes('401') || errorMessage.includes('unauthorized')) {
      strategies.push('auth-refresh', 'redirect');
    }

    // Server errors
    if (errorMessage.includes('500') || errorMessage.includes('server')) {
      strategies.push('retry', 'refresh');
    }

    // Timeout errors
    if (errorMessage.includes('timeout')) {
      strategies.push('retry');
    }

    // Default strategies
    if (strategies.length === 0) {
      strategies.push(...recoveryStrategies);
    }

    return strategies;
  };

  // Main recovery function
  const recoverFromError = useCallback(async (
    error: Error,
    config?: RetryConfig,
    customStrategies?: RecoveryStrategy[]
  ): Promise<boolean> => {
    if (recoveryInProgress.current) {
      console.warn('Recovery already in progress');
      return false;
    }

    recoveryInProgress.current = true;
    setIsRecovering(true);
    setRecoveryAttempts(0);

    const {
      maxAttempts = 3,
      delay = 1000,
      backoff = 'exponential',
      onRetry,
    } = config || {};

    const strategies = customStrategies || determineStrategy(error);
    let recovered = false;

    try {
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        setRecoveryAttempts(attempt);

        for (const strategy of strategies) {
          try {
            console.log(`Attempting recovery: ${strategy} (attempt ${attempt})`);
            
            const context: RecoveryContext = {
              error,
              strategy,
              attempt,
              metadata: {},
            };

            await recoveryHandlers[strategy](context);
            
            // If we get here, recovery succeeded
            recovered = true;
            onRecoverySuccess?.();
            
            // Report successful recovery
            await errorReportingService.reportError(error, {
              type: 'error_recovered',
              strategy,
              attempt,
            });
            
            break;
          } catch (strategyError) {
            console.error(`Recovery strategy ${strategy} failed:`, strategyError);
            continue;
          }
        }

        if (recovered) break;

        // Calculate delay for next attempt
        const nextDelay = backoff === 'exponential' 
          ? delay * Math.pow(2, attempt - 1)
          : delay * attempt;

        onRetry?.(attempt, error);

        if (attempt < maxAttempts) {
          await new Promise(resolve => setTimeout(resolve, nextDelay));
        }
      }

      if (!recovered) {
        throw new Error('All recovery attempts failed');
      }

      return true;
    } catch (recoveryError) {
      console.error('Recovery failed:', recoveryError);
      onRecoveryFailed?.(error);
      
      // Report failed recovery
      await errorReportingService.reportError(error, {
        type: 'error_recovery_failed',
        attempts: recoveryAttempts,
        strategies,
      });
      
      return false;
    } finally {
      recoveryInProgress.current = false;
      setIsRecovering(false);
    }
  }, [recoveryStrategies, onRecoverySuccess, onRecoveryFailed, navigate, queryClient]);

  // Auto-recovery for global errors
  useEffect(() => {
    if (!enableAutoRecovery) return;

    const handleError = async (event: ErrorEvent) => {
      console.log('Global error detected, attempting auto-recovery');
      await recoverFromError(new Error(event.message));
    };

    const handleUnhandledRejection = async (event: PromiseRejectionEvent) => {
      console.log('Unhandled rejection detected, attempting auto-recovery');
      await recoverFromError(new Error(event.reason?.message || 'Promise rejection'));
    };

    window.addEventListener('error', handleError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [enableAutoRecovery, recoverFromError]);

  // Process offline queue when back online
  useEffect(() => {
    const processOfflineQueue = async () => {
      const queue = JSON.parse(localStorage.getItem('offline-queue') || '[]');
      if (queue.length === 0) return;

      console.log(`Processing ${queue.length} offline operations`);
      
      for (const operation of queue) {
        try {
          // Process queued operation
          // This would need to be implemented based on your app's needs
          console.log('Processing offline operation:', operation);
        } catch (error) {
          console.error('Failed to process offline operation:', error);
        }
      }

      localStorage.removeItem('offline-queue');
    };

    const handleOnline = () => {
      processOfflineQueue();
    };

    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, []);

  return {
    recoverFromError,
    isRecovering,
    recoveryAttempts,
  };
};

// Hook for retryable operations
export const useRetryableOperation = <T = any>(
  operation: () => Promise<T>,
  options?: RetryConfig & ErrorRecoveryOptions
) => {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const { recoverFromError } = useErrorRecovery(options);

  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const result = await operation();
      setData(result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);

      // Attempt recovery
      const recovered = await recoverFromError(error, options);
      
      if (recovered) {
        // Retry operation after recovery
        try {
          const result = await operation();
          setData(result);
          setError(null);
          return result;
        } catch (retryErr) {
          const retryError = retryErr instanceof Error ? retryErr : new Error(String(retryErr));
          setError(retryError);
          throw retryError;
        }
      }

      throw error;
    } finally {
      setLoading(false);
    }
  }, [operation, recoverFromError, options]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return {
    execute,
    data,
    error,
    loading,
    reset,
  };
};