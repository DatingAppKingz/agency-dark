import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import {
  Snackbar,
  Alert,
  AlertTitle,
  Button,
  IconButton,
  Collapse,
  Box,
  Typography,
  LinearProgress,
} from '@mui/material';
import {
  Close,
  ExpandMore,
  ExpandLess,
  Refresh,
  BugReport,
  ContentCopy,
} from '@mui/icons-material';
import { useErrorRecovery } from '@/hooks/useErrorRecovery';
import { errorReportingService } from '@/services/errorReportingService';

interface ErrorNotification {
  id: string;
  error: Error;
  severity: 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: Date;
  actions?: ErrorAction[];
  details?: string;
  canRecover?: boolean;
  errorId?: string;
}

interface ErrorAction {
  label: string;
  action: () => void | Promise<void>;
  variant?: 'text' | 'outlined' | 'contained';
}

interface ErrorNotificationContextValue {
  showError: (error: Error | string, options?: ShowErrorOptions) => void;
  showAPIError: (error: any, endpoint: string) => void;
  showNetworkError: (error: Error) => void;
  showValidationError: (errors: any[]) => void;
  clearErrors: () => void;
  retryLastError: () => Promise<void>;
}

interface ShowErrorOptions {
  severity?: 'error' | 'warning' | 'info';
  title?: string;
  autoHide?: boolean;
  duration?: number;
  actions?: ErrorAction[];
  canRecover?: boolean;
  reportError?: boolean;
}

const ErrorNotificationContext = createContext<ErrorNotificationContextValue | null>(null);

export const useErrorNotification = () => {
  const context = useContext(ErrorNotificationContext);
  if (!context) {
    throw new Error('useErrorNotification must be used within ErrorNotificationProvider');
  }
  return context;
};

export const ErrorNotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [notifications, setNotifications] = useState<ErrorNotification[]>([]);
  const [activeNotification, setActiveNotification] = useState<ErrorNotification | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [isRecovering, setIsRecovering] = useState(false);
  const { recoverFromError } = useErrorRecovery();
  const lastErrorRef = useRef<Error | null>(null);

  const generateId = () => `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

  const showError = useCallback(async (
    error: Error | string,
    options: ShowErrorOptions = {}
  ) => {
    const {
      severity = 'error',
      title = 'Error',
      autoHide = false,
      duration = 6000,
      actions = [],
      canRecover = true,
      reportError = true,
    } = options;

    const errorObj = error instanceof Error ? error : new Error(error);
    lastErrorRef.current = errorObj;

    // Report error if enabled
    let errorId: string | null = null;
    if (reportError) {
      errorId = await errorReportingService.reportError(errorObj, {
        source: 'user_notification',
        severity,
      });
    }

    const notification: ErrorNotification = {
      id: generateId(),
      error: errorObj,
      severity,
      title,
      message: errorObj.message,
      timestamp: new Date(),
      actions,
      details: errorObj.stack,
      canRecover,
      errorId: errorId || undefined,
    };

    setNotifications(prev => [...prev, notification]);
    setActiveNotification(notification);

    if (autoHide) {
      setTimeout(() => {
        handleClose(notification.id);
      }, duration);
    }
  }, []);

  const showAPIError = useCallback((error: any, endpoint: string) => {
    const status = error.response?.status;
    const message = error.response?.data?.message || error.message;
    
    let title = 'API Error';
    let severity: 'error' | 'warning' = 'error';
    let actions: ErrorAction[] = [];

    switch (status) {
      case 401:
        title = 'Authentication Required';
        actions = [{
          label: 'Login',
          action: () => window.location.href = '/login',
        }];
        break;
      case 403:
        title = 'Access Denied';
        severity = 'warning';
        break;
      case 404:
        title = 'Not Found';
        severity = 'warning';
        break;
      case 429:
        title = 'Too Many Requests';
        severity = 'warning';
        const retryAfter = error.response?.headers?.['retry-after'];
        if (retryAfter) {
          message + ` Please try again in ${retryAfter} seconds.`;
        }
        break;
      case 500:
      case 502:
      case 503:
        title = 'Server Error';
        actions = [{
          label: 'Retry',
          action: async () => retryLastError(),
        }];
        break;
    }

    showError(new Error(message), {
      severity,
      title,
      actions,
      canRecover: status >= 500,
    });
  }, [showError]);

  const showNetworkError = useCallback((error: Error) => {
    showError(error, {
      title: 'Network Error',
      severity: 'error',
      actions: [{
        label: 'Retry',
        action: async () => retryLastError(),
      }],
      canRecover: true,
    });
  }, [showError]);

  const showValidationError = useCallback((errors: any[]) => {
    const message = errors
      .map(err => `${err.field}: ${err.message}`)
      .join('\n');
    
    showError(new Error(message), {
      title: 'Validation Error',
      severity: 'warning',
      canRecover: false,
    });
  }, [showError]);

  const handleClose = useCallback((notificationId?: string) => {
    if (notificationId) {
      setNotifications(prev => prev.filter(n => n.id !== notificationId));
      if (activeNotification?.id === notificationId) {
        setActiveNotification(null);
        setShowDetails(false);
      }
    } else if (activeNotification) {
      setNotifications(prev => prev.filter(n => n.id !== activeNotification.id));
      setActiveNotification(null);
      setShowDetails(false);
    }
  }, [activeNotification]);

  const clearErrors = useCallback(() => {
    setNotifications([]);
    setActiveNotification(null);
    setShowDetails(false);
  }, []);

  const retryLastError = useCallback(async () => {
    if (!lastErrorRef.current) return;

    setIsRecovering(true);
    try {
      const recovered = await recoverFromError(lastErrorRef.current, {
        maxAttempts: 3,
        delay: 1000,
      });

      if (recovered) {
        showError('Operation completed successfully', {
          severity: 'info',
          title: 'Success',
          autoHide: true,
          reportError: false,
        });
        handleClose();
      } else {
        showError('Recovery failed. Please try again later.', {
          severity: 'error',
          title: 'Recovery Failed',
          reportError: false,
        });
      }
    } finally {
      setIsRecovering(false);
    }
  }, [recoverFromError, showError, handleClose]);

  const handleRecover = useCallback(async () => {
    if (!activeNotification?.canRecover) return;

    setIsRecovering(true);
    try {
      const recovered = await recoverFromError(activeNotification.error);
      if (recovered) {
        handleClose();
      }
    } finally {
      setIsRecovering(false);
    }
  }, [activeNotification, recoverFromError, handleClose]);

  const copyErrorDetails = useCallback(() => {
    if (!activeNotification) return;

    const details = `
Error: ${activeNotification.title}
Message: ${activeNotification.message}
Time: ${activeNotification.timestamp.toISOString()}
Error ID: ${activeNotification.errorId || 'N/A'}
Stack: ${activeNotification.details || 'N/A'}
    `.trim();

    navigator.clipboard.writeText(details);
    
    showError('Error details copied to clipboard', {
      severity: 'info',
      autoHide: true,
      duration: 2000,
      reportError: false,
    });
  }, [activeNotification, showError]);

  const contextValue: ErrorNotificationContextValue = {
    showError,
    showAPIError,
    showNetworkError,
    showValidationError,
    clearErrors,
    retryLastError,
  };

  return (
    <ErrorNotificationContext.Provider value={contextValue}>
      {children}
      
      <Snackbar
        open={!!activeNotification}
        onClose={() => handleClose()}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        sx={{ maxWidth: 600 }}
      >
        {activeNotification && (
          <Alert
            severity={activeNotification.severity}
            onClose={() => handleClose()}
            sx={{ width: '100%' }}
            action={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {activeNotification.canRecover && (
                  <Button
                    size="small"
                    color="inherit"
                    onClick={handleRecover}
                    disabled={isRecovering}
                    startIcon={<Refresh />}
                  >
                    Recover
                  </Button>
                )}
                {activeNotification.actions?.map((action, index) => (
                  <Button
                    key={index}
                    size="small"
                    color="inherit"
                    variant={action.variant || 'text'}
                    onClick={action.action}
                  >
                    {action.label}
                  </Button>
                ))}
                <IconButton
                  size="small"
                  color="inherit"
                  onClick={() => setShowDetails(!showDetails)}
                >
                  {showDetails ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>
            }
          >
            <AlertTitle>{activeNotification.title}</AlertTitle>
            <Typography variant="body2">{activeNotification.message}</Typography>
            
            {activeNotification.errorId && (
              <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>
                Error ID: {activeNotification.errorId}
              </Typography>
            )}

            {isRecovering && (
              <LinearProgress sx={{ mt: 1 }} />
            )}

            <Collapse in={showDetails}>
              <Box sx={{ mt: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <BugReport fontSize="small" />
                  <Typography variant="subtitle2">Error Details</Typography>
                  <IconButton size="small" onClick={copyErrorDetails}>
                    <ContentCopy fontSize="small" />
                  </IconButton>
                </Box>
                <Box
                  component="pre"
                  sx={{
                    fontSize: '0.75rem',
                    backgroundColor: 'action.hover',
                    p: 1,
                    borderRadius: 1,
                    overflow: 'auto',
                    maxHeight: 200,
                    fontFamily: 'monospace',
                  }}
                >
                  {activeNotification.details || 'No additional details available'}
                </Box>
              </Box>
            </Collapse>
          </Alert>
        )}
      </Snackbar>

      {/* Queue indicator for multiple errors */}
      {notifications.length > 1 && (
        <Box
          sx={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            bgcolor: 'background.paper',
            boxShadow: 2,
            borderRadius: 1,
            p: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
          }}
        >
          <Typography variant="caption">
            {notifications.length} errors
          </Typography>
          <Button size="small" onClick={clearErrors}>
            Clear All
          </Button>
        </Box>
      )}
    </ErrorNotificationContext.Provider>
  );
};