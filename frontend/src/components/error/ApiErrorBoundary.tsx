import { Component, ReactNode } from 'react';
import { Box, Typography, Button, Alert, Collapse } from '@mui/material';
import { ExpandMore, ExpandLess } from '@mui/icons-material';

interface ApiError {
  status?: number;
  message: string;
  details?: any;
  timestamp: Date;
}

interface ApiErrorBoundaryState {
  hasError: boolean;
  error: ApiError | null;
  showDetails: boolean;
}

interface ApiErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: ApiError, retry: () => void) => ReactNode;
  onError?: (error: ApiError) => void;
}

export class ApiErrorBoundary extends Component<ApiErrorBoundaryProps, ApiErrorBoundaryState> {
  constructor(props: ApiErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      showDetails: false,
    };
  }

  static getDerivedStateFromError(error: Error): ApiErrorBoundaryState {
    // Parse API errors
    const apiError: ApiError = {
      message: error.message || 'An unexpected error occurred',
      timestamp: new Date(),
    };

    // Check if it's an API response error
    if ('response' in error && error.response) {
      const response = error.response as any;
      apiError.status = response.status;
      apiError.details = response.data;
      
      // Extract user-friendly message
      if (response.data?.detail) {
        apiError.message = response.data.detail;
      } else if (response.data?.message) {
        apiError.message = response.data.message;
      }
    }

    return {
      hasError: true,
      error: apiError,
      showDetails: false,
    };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('API Error Boundary caught:', error, errorInfo);
    
    if (this.props.onError && this.state.error) {
      this.props.onError(this.state.error);
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, showDetails: false });
  };

  toggleDetails = () => {
    this.setState(prev => ({ showDetails: !prev.showDetails }));
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry);
      }

      const { error, showDetails } = this.state;
      const isServerError = error.status && error.status >= 500;
      const isClientError = error.status && error.status >= 400 && error.status < 500;
      const isNetworkError = !error.status && error.message.toLowerCase().includes('network');

      return (
        <Box sx={{ p: 3 }}>
          <Alert
            severity={isServerError ? 'error' : isClientError ? 'warning' : 'info'}
            sx={{ mb: 2 }}
          >
            <Typography variant="h6" gutterBottom>
              {isServerError && 'Server Error'}
              {isClientError && 'Request Error'}
              {isNetworkError && 'Network Error'}
              {!isServerError && !isClientError && !isNetworkError && 'Error'}
            </Typography>
            
            <Typography variant="body2">
              {error.message}
            </Typography>
            
            {error.status && (
              <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                Error Code: {error.status}
              </Typography>
            )}
          </Alert>

          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <Button variant="contained" size="small" onClick={this.handleRetry}>
              Try Again
            </Button>
            
            {error.details && (
              <Button
                variant="text"
                size="small"
                onClick={this.toggleDetails}
                endIcon={showDetails ? <ExpandLess /> : <ExpandMore />}
              >
                {showDetails ? 'Hide' : 'Show'} Details
              </Button>
            )}
          </Box>

          <Collapse in={showDetails}>
            <Box
              sx={{
                p: 2,
                backgroundColor: 'grey.100',
                borderRadius: 1,
                overflow: 'auto',
              }}
            >
              <Typography variant="caption" component="pre">
                {JSON.stringify(error.details, null, 2)}
              </Typography>
            </Box>
          </Collapse>
        </Box>
      );
    }

    return this.props.children;
  }
}