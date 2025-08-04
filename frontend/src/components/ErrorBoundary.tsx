import React, { Component, ErrorInfo, ReactNode } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  Collapse,
  IconButton,
  Alert,
  Container,
} from '@mui/material';
import {
  Error as ErrorIcon,
  Refresh,
  ExpandMore,
  ExpandLess,
  Home,
  BugReport,
} from '@mui/icons-material';
import { errorReportingService } from '@/services/errorReportingService';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  showDetails?: boolean;
  enableReporting?: boolean;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
  reportSent: boolean;
  errorId: string | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
      reportSent: false,
      errorId: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
      showDetails: false,
      reportSent: false,
      errorId: null,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // Update state with error info
    this.setState({
      errorInfo,
    });

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Report error if enabled
    if (this.props.enableReporting !== false) {
      this.reportError(error, errorInfo);
    }
  }

  reportError = async (error: Error, errorInfo: ErrorInfo) => {
    try {
      const errorId = await errorReportingService.reportError(error, {
        componentStack: errorInfo.componentStack,
        errorBoundary: true,
        location: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString(),
      });

      this.setState({
        reportSent: true,
        errorId,
      });
    } catch (reportingError) {
      console.error('Failed to report error:', reportingError);
    }
  };

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
      reportSent: false,
      errorId: null,
    });

    // Optionally reload the page
    if (this.props.fallback === undefined) {
      window.location.reload();
    }
  };

  handleGoHome = () => {
    window.location.href = '/';
  };

  toggleDetails = () => {
    this.setState((prevState) => ({
      showDetails: !prevState.showDetails,
    }));
  };

  render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return <>{this.props.fallback}</>;
      }

      // Default error UI
      return (
        <Container maxWidth="md">
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '100vh',
              textAlign: 'center',
              py: 4,
            }}
          >
            <Paper
              elevation={3}
              sx={{
                p: 4,
                width: '100%',
                maxWidth: 600,
              }}
            >
              <ErrorIcon
                sx={{
                  fontSize: 80,
                  color: 'error.main',
                  mb: 2,
                }}
              />

              <Typography variant="h4" gutterBottom>
                Oops! Something went wrong
              </Typography>

              <Typography variant="body1" color="text.secondary" paragraph>
                We're sorry for the inconvenience. An unexpected error occurred while
                processing your request.
              </Typography>

              {this.state.reportSent && (
                <Alert severity="info" sx={{ mb: 2 }}>
                  Error report sent. Reference ID: {this.state.errorId}
                </Alert>
              )}

              <Box sx={{ mt: 3, display: 'flex', gap: 2, justifyContent: 'center' }}>
                <Button
                  variant="contained"
                  startIcon={<Refresh />}
                  onClick={this.handleReset}
                >
                  Try Again
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<Home />}
                  onClick={this.handleGoHome}
                >
                  Go Home
                </Button>
              </Box>

              {/* Error details section */}
              {this.props.showDetails !== false && this.state.error && (
                <Box sx={{ mt: 3 }}>
                  <Button
                    startIcon={this.state.showDetails ? <ExpandLess /> : <ExpandMore />}
                    endIcon={<BugReport />}
                    onClick={this.toggleDetails}
                    size="small"
                  >
                    {this.state.showDetails ? 'Hide' : 'Show'} Error Details
                  </Button>

                  <Collapse in={this.state.showDetails}>
                    <Paper
                      variant="outlined"
                      sx={{
                        mt: 2,
                        p: 2,
                        bgcolor: 'grey.100',
                        maxHeight: 300,
                        overflow: 'auto',
                      }}
                    >
                      <Typography
                        variant="subtitle2"
                        gutterBottom
                        sx={{ fontWeight: 'bold' }}
                      >
                        Error Message:
                      </Typography>
                      <Typography
                        variant="body2"
                        sx={{
                          fontFamily: 'monospace',
                          mb: 2,
                          wordBreak: 'break-word',
                        }}
                      >
                        {this.state.error.message}
                      </Typography>

                      {this.state.error.stack && (
                        <>
                          <Typography
                            variant="subtitle2"
                            gutterBottom
                            sx={{ fontWeight: 'bold' }}
                          >
                            Stack Trace:
                          </Typography>
                          <Typography
                            variant="body2"
                            component="pre"
                            sx={{
                              fontFamily: 'monospace',
                              fontSize: '0.75rem',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                            }}
                          >
                            {this.state.error.stack}
                          </Typography>
                        </>
                      )}

                      {this.state.errorInfo?.componentStack && (
                        <>
                          <Typography
                            variant="subtitle2"
                            gutterBottom
                            sx={{ fontWeight: 'bold', mt: 2 }}
                          >
                            Component Stack:
                          </Typography>
                          <Typography
                            variant="body2"
                            component="pre"
                            sx={{
                              fontFamily: 'monospace',
                              fontSize: '0.75rem',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                            }}
                          >
                            {this.state.errorInfo.componentStack}
                          </Typography>
                        </>
                      )}
                    </Paper>
                  </Collapse>
                </Box>
              )}
            </Paper>
          </Box>
        </Container>
      );
    }

    return this.props.children;
  }
}

// Async Error Boundary for handling promise rejections
export const AsyncErrorBoundary: React.FC<{ children: ReactNode }> = ({ children }) => {
  React.useEffect(() => {
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('Unhandled promise rejection:', event.reason);
      
      // Report the error
      errorReportingService.reportError(
        new Error(event.reason?.message || 'Unhandled Promise Rejection'),
        {
          type: 'unhandledRejection',
          reason: event.reason,
          promise: event.promise,
          location: window.location.href,
        }
      );
    };

    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, []);

  return <>{children}</>;
};

// Route-specific error boundary with navigation
export const RouteErrorBoundary: React.FC<{ children: ReactNode }> = ({ children }) => {
  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        // Log route-specific errors
        console.error('Route error:', {
          error,
          errorInfo,
          route: window.location.pathname,
        });
      }}
      fallback={
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '50vh',
            p: 3,
          }}
        >
          <ErrorIcon sx={{ fontSize: 60, color: 'error.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Error loading this page
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            There was a problem loading this page. Please try refreshing or navigating to a
            different page.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button variant="contained" onClick={() => window.location.reload()}>
              Refresh Page
            </Button>
            <Button variant="outlined" onClick={() => (window.location.href = '/')}>
              Go Home
            </Button>
          </Box>
        </Box>
      }
    >
      {children}
    </ErrorBoundary>
  );
};

// HOC for wrapping components with error boundary
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Partial<Props>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  );

  WrappedComponent.displayName = `withErrorBoundary(${
    Component.displayName || Component.name || 'Component'
  })`;

  return WrappedComponent;
}