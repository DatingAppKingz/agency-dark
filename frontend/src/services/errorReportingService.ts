import axios from 'axios';

interface ErrorContext {
  userId?: string;
  sessionId?: string;
  component?: string;
  action?: string;
  metadata?: Record<string, any>;
  [key: string]: any;
}

interface ErrorReport {
  id: string;
  timestamp: string;
  message: string;
  stack?: string;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  context: ErrorContext;
  userAgent: string;
  url: string;
  source: 'client' | 'server';
}

interface ErrorReportingConfig {
  endpoint?: string;
  apiKey?: string;
  environment?: string;
  release?: string;
  userId?: string;
  enableConsoleLog?: boolean;
  enableLocalStorage?: boolean;
  maxStoredErrors?: number;
  beforeSend?: (report: ErrorReport) => ErrorReport | null;
  sampleRate?: number; // 0-1, percentage of errors to report
}

class ErrorReportingService {
  private config: ErrorReportingConfig;
  private queue: ErrorReport[] = [];
  private isOnline: boolean = navigator.onLine;
  private sessionId: string;
  private errorCounts: Map<string, number> = new Map();
  private rateLimitWindow = 60000; // 1 minute
  private maxErrorsPerType = 10; // Max errors of same type per window

  constructor(config: ErrorReportingConfig = {}) {
    this.config = {
      endpoint: process.env.REACT_APP_ERROR_REPORTING_URL || '/api/v1/errors',
      environment: process.env.NODE_ENV,
      enableConsoleLog: process.env.NODE_ENV === 'development',
      enableLocalStorage: true,
      maxStoredErrors: 50,
      sampleRate: process.env.NODE_ENV === 'production' ? 0.1 : 1,
      ...config,
    };

    this.sessionId = this.generateSessionId();
    this.setupEventListeners();
    this.loadQueuedErrors();
  }

  private generateSessionId(): string {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private setupEventListeners(): void {
    // Monitor online/offline status
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.flushQueue();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
    });

    // Global error handler
    window.addEventListener('error', (event) => {
      this.reportError(
        new Error(event.message),
        {
          type: 'global',
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
        }
      );
    });

    // Cleanup error counts periodically
    setInterval(() => {
      this.errorCounts.clear();
    }, this.rateLimitWindow);
  }

  async reportError(
    error: Error,
    context: ErrorContext = {}
  ): Promise<string | null> {
    try {
      // Check sample rate
      if (Math.random() > this.config.sampleRate!) {
        return null;
      }

      // Rate limiting
      const errorKey = `${error.name}_${error.message}`;
      const count = this.errorCounts.get(errorKey) || 0;
      if (count >= this.maxErrorsPerType) {
        console.warn('Error rate limit exceeded for:', errorKey);
        return null;
      }
      this.errorCounts.set(errorKey, count + 1);

      // Create error report
      const report: ErrorReport = {
        id: `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        timestamp: new Date().toISOString(),
        message: error.message,
        stack: error.stack,
        type: error.name,
        severity: this.determineSeverity(error, context),
        context: {
          ...context,
          userId: this.config.userId,
          sessionId: this.sessionId,
          environment: this.config.environment,
          release: this.config.release,
        },
        userAgent: navigator.userAgent,
        url: window.location.href,
        source: 'client',
      };

      // Apply beforeSend hook
      if (this.config.beforeSend) {
        const modifiedReport = this.config.beforeSend(report);
        if (!modifiedReport) {
          return null; // Skip reporting
        }
        Object.assign(report, modifiedReport);
      }

      // Log to console if enabled
      if (this.config.enableConsoleLog) {
        console.error('Error Report:', report);
      }

      // Send or queue
      if (this.isOnline) {
        await this.sendReport(report);
      } else {
        this.queueReport(report);
      }

      return report.id;
    } catch (err) {
      console.error('Failed to report error:', err);
      return null;
    }
  }

  private determineSeverity(
    error: Error,
    context: ErrorContext
  ): ErrorReport['severity'] {
    // Critical: Security errors, data loss, auth failures
    if (
      error.message.includes('401') ||
      error.message.includes('403') ||
      context.type === 'security' ||
      context.type === 'data_loss'
    ) {
      return 'critical';
    }

    // High: Network errors, API failures, payment errors
    if (
      error.name === 'NetworkError' ||
      error.message.includes('500') ||
      context.type === 'payment' ||
      context.type === 'api_error'
    ) {
      return 'high';
    }

    // Medium: Validation errors, state errors
    if (
      error.name === 'ValidationError' ||
      context.type === 'validation' ||
      context.type === 'state_error'
    ) {
      return 'medium';
    }

    // Low: UI errors, warnings
    return 'low';
  }

  private async sendReport(report: ErrorReport): Promise<void> {
    try {
      await axios.post(this.config.endpoint!, report, {
        headers: {
          'Content-Type': 'application/json',
          ...(this.config.apiKey && { 'X-API-Key': this.config.apiKey }),
        },
        timeout: 5000,
      });

      // Store in local storage for debugging
      if (this.config.enableLocalStorage) {
        this.storeErrorLocally(report);
      }
    } catch (err) {
      console.error('Failed to send error report:', err);
      this.queueReport(report);
    }
  }

  private queueReport(report: ErrorReport): void {
    this.queue.push(report);
    
    // Limit queue size
    if (this.queue.length > 100) {
      this.queue.shift(); // Remove oldest
    }

    // Save queue to localStorage
    if (this.config.enableLocalStorage) {
      try {
        localStorage.setItem('error_queue', JSON.stringify(this.queue));
      } catch (e) {
        console.warn('Failed to save error queue:', e);
      }
    }
  }

  private async flushQueue(): Promise<void> {
    if (this.queue.length === 0) return;

    const reports = [...this.queue];
    this.queue = [];

    // Send reports in batches
    const batchSize = 10;
    for (let i = 0; i < reports.length; i += batchSize) {
      const batch = reports.slice(i, i + batchSize);
      try {
        await axios.post(
          `${this.config.endpoint}/batch`,
          { errors: batch },
          {
            headers: {
              'Content-Type': 'application/json',
              ...(this.config.apiKey && { 'X-API-Key': this.config.apiKey }),
            },
          }
        );
      } catch (err) {
        // Re-queue failed batch
        this.queue.unshift(...batch);
        break;
      }
    }

    // Clear localStorage queue
    if (this.config.enableLocalStorage) {
      localStorage.removeItem('error_queue');
    }
  }

  private loadQueuedErrors(): void {
    if (!this.config.enableLocalStorage) return;

    try {
      const stored = localStorage.getItem('error_queue');
      if (stored) {
        this.queue = JSON.parse(stored);
        if (this.isOnline) {
          this.flushQueue();
        }
      }
    } catch (e) {
      console.warn('Failed to load error queue:', e);
    }
  }

  private storeErrorLocally(report: ErrorReport): void {
    try {
      const stored = localStorage.getItem('error_reports') || '[]';
      const reports = JSON.parse(stored);
      reports.push(report);

      // Keep only recent errors
      const recentReports = reports
        .slice(-this.config.maxStoredErrors!)
        .filter((r: ErrorReport) => {
          const age = Date.now() - new Date(r.timestamp).getTime();
          return age < 7 * 24 * 60 * 60 * 1000; // 7 days
        });

      localStorage.setItem('error_reports', JSON.stringify(recentReports));
    } catch (e) {
      console.warn('Failed to store error locally:', e);
    }
  }

  // Public methods

  reportAPIError(
    error: any,
    endpoint: string,
    method: string,
    context: ErrorContext = {}
  ): Promise<string | null> {
    const apiError = new Error(
      error.response?.data?.message || error.message || 'API Error'
    );
    
    return this.reportError(apiError, {
      ...context,
      type: 'api_error',
      endpoint,
      method,
      status: error.response?.status,
      statusText: error.response?.statusText,
      responseData: error.response?.data,
    });
  }

  reportUserAction(
    action: string,
    error: Error,
    context: ErrorContext = {}
  ): Promise<string | null> {
    return this.reportError(error, {
      ...context,
      type: 'user_action',
      action,
    });
  }

  reportPerformanceIssue(
    metric: string,
    value: number,
    threshold: number,
    context: ErrorContext = {}
  ): Promise<string | null> {
    const error = new Error(
      `Performance issue: ${metric} (${value}ms) exceeded threshold (${threshold}ms)`
    );
    
    return this.reportError(error, {
      ...context,
      type: 'performance',
      metric,
      value,
      threshold,
      severity: value > threshold * 2 ? 'high' : 'medium',
    });
  }

  getStoredErrors(): ErrorReport[] {
    if (!this.config.enableLocalStorage) return [];

    try {
      const stored = localStorage.getItem('error_reports');
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      return [];
    }
  }

  clearStoredErrors(): void {
    if (this.config.enableLocalStorage) {
      localStorage.removeItem('error_reports');
      localStorage.removeItem('error_queue');
    }
  }

  setUserId(userId: string): void {
    this.config.userId = userId;
  }

  configure(config: Partial<ErrorReportingConfig>): void {
    Object.assign(this.config, config);
  }
}

// Create singleton instance
export const errorReportingService = new ErrorReportingService();

// React hook for error reporting
import { useCallback } from 'react';

export const useErrorReporting = () => {
  const reportError = useCallback(
    (error: Error, context?: ErrorContext) => {
      return errorReportingService.reportError(error, context);
    },
    []
  );

  const reportAPIError = useCallback(
    (error: any, endpoint: string, method: string, context?: ErrorContext) => {
      return errorReportingService.reportAPIError(error, endpoint, method, context);
    },
    []
  );

  const reportUserAction = useCallback(
    (action: string, error: Error, context?: ErrorContext) => {
      return errorReportingService.reportUserAction(action, error, context);
    },
    []
  );

  return {
    reportError,
    reportAPIError,
    reportUserAction,
  };
};