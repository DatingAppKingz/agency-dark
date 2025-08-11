/**
 * OAuth Callback Handler Page
 * Processes OAuth authorization callbacks and exchanges codes for tokens
 */

import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import {
  Box,
  Container,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  Button,
  Stack,
  LinearProgress,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Home as HomeIcon,
} from '@mui/icons-material';

// Callback states
enum CallbackState {
  PROCESSING = 'processing',
  SUCCESS = 'success',
  ERROR = 'error',
  INVALID = 'invalid',
}

// Error types
interface OAuthCallbackError {
  error: string;
  error_description?: string;
  error_uri?: string;
}

/**
 * OAuth Callback Page Component
 */
const OAuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { handleOAuthCallback, isAuthenticated } = useAuth();

  // Component state
  const [callbackState, setCallbackState] = useState<CallbackState>(CallbackState.PROCESSING);
  const [error, setError] = useState<OAuthCallbackError | null>(null);
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState('Processing authorization...');

  /**
   * Process OAuth callback
   */
  useEffect(() => {
    const processCallback = async () => {
      // Update progress
      setProgress(20);
      setStatusMessage('Validating authorization response...');

      // Extract parameters from URL
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');
      const errorUri = searchParams.get('error_uri');

      // Check for OAuth errors
      if (errorParam) {
        setError({
          error: errorParam,
          error_description: errorDescription || undefined,
          error_uri: errorUri || undefined,
        });
        setCallbackState(CallbackState.ERROR);
        setStatusMessage('Authorization failed');
        return;
      }

      // Validate required parameters
      if (!code || !state) {
        setError({
          error: 'invalid_request',
          error_description: 'Missing required parameters: code or state',
        });
        setCallbackState(CallbackState.INVALID);
        setStatusMessage('Invalid callback parameters');
        return;
      }

      // Update progress
      setProgress(40);
      setStatusMessage('Exchanging authorization code...');

      try {
        // Exchange code for tokens
        await handleOAuthCallback(code, state);
        
        // Update progress
        setProgress(80);
        setStatusMessage('Retrieving user information...');
        
        // Small delay for UX
        await new Promise(resolve => setTimeout(resolve, 500));
        
        // Success
        setProgress(100);
        setStatusMessage('Authorization successful!');
        setCallbackState(CallbackState.SUCCESS);
        
        // Redirect after short delay
        setTimeout(() => {
          const returnUrl = sessionStorage.getItem('auth_return_url') || '/dashboard';
          sessionStorage.removeItem('auth_return_url');
          navigate(returnUrl);
        }, 1500);
      } catch (err) {
        console.error('OAuth callback error:', err);
        
        const errorMessage = err instanceof Error ? err.message : 'Authorization failed';
        setError({
          error: 'callback_error',
          error_description: errorMessage,
        });
        setCallbackState(CallbackState.ERROR);
        setStatusMessage('Authorization failed');
      }
    };

    processCallback();
  }, [searchParams, handleOAuthCallback, navigate]);

  /**
   * Handle retry
   */
  const handleRetry = () => {
    navigate('/login');
  };

  /**
   * Handle go home
   */
  const handleGoHome = () => {
    navigate('/');
  };

  /**
   * Render error details
   */
  const renderErrorDetails = () => {
    if (!error) return null;

    let errorTitle = 'Authorization Error';
    let errorMessage = error.error_description || 'An error occurred during authorization.';

    // Customize error messages
    switch (error.error) {
      case 'access_denied':
        errorTitle = 'Access Denied';
        errorMessage = 'You denied the authorization request.';
        break;
      case 'invalid_scope':
        errorTitle = 'Invalid Permissions';
        errorMessage = 'The requested permissions are invalid.';
        break;
      case 'server_error':
        errorTitle = 'Server Error';
        errorMessage = 'The authorization server encountered an error.';
        break;
      case 'temporarily_unavailable':
        errorTitle = 'Service Unavailable';
        errorMessage = 'The authorization service is temporarily unavailable.';
        break;
      case 'invalid_request':
        errorTitle = 'Invalid Request';
        errorMessage = errorMessage || 'The authorization request was invalid.';
        break;
      case 'unauthorized_client':
        errorTitle = 'Unauthorized Client';
        errorMessage = 'This application is not authorized to use OAuth.';
        break;
      case 'unsupported_response_type':
        errorTitle = 'Unsupported Response Type';
        errorMessage = 'The authorization server does not support this response type.';
        break;
    }

    return (
      <>
        <Typography variant="h6" gutterBottom>
          {errorTitle}
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          {errorMessage}
        </Typography>
        {error.error_uri && (
          <Typography variant="body2" color="text.secondary">
            <a 
              href={error.error_uri} 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: 'inherit' }}
            >
              Learn more about this error
            </a>
          </Typography>
        )}
      </>
    );
  };

  /**
   * Render content based on state
   */
  const renderContent = () => {
    switch (callbackState) {
      case CallbackState.PROCESSING:
        return (
          <Box textAlign="center">
            <CircularProgress size={60} thickness={4} sx={{ mb: 3 }} />
            <Typography variant="h5" gutterBottom>
              {statusMessage}
            </Typography>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Please wait while we complete the authorization process...
            </Typography>
            <Box sx={{ width: '100%', mt: 3 }}>
              <LinearProgress variant="determinate" value={progress} />
            </Box>
          </Box>
        );

      case CallbackState.SUCCESS:
        return (
          <Box textAlign="center">
            <CheckCircleIcon sx={{ fontSize: 80, color: 'success.main', mb: 2 }} />
            <Typography variant="h5" gutterBottom>
              Authorization Successful!
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Redirecting you to your dashboard...
            </Typography>
            <CircularProgress size={24} sx={{ mt: 2 }} />
          </Box>
        );

      case CallbackState.ERROR:
      case CallbackState.INVALID:
        return (
          <Box>
            <Box display="flex" alignItems="center" mb={2}>
              <ErrorIcon sx={{ fontSize: 40, color: 'error.main', mr: 2 }} />
              {renderErrorDetails()}
            </Box>
            
            <Stack direction="row" spacing={2} justifyContent="center" mt={4}>
              <Button
                variant="contained"
                startIcon={<RefreshIcon />}
                onClick={handleRetry}
              >
                Try Again
              </Button>
              <Button
                variant="outlined"
                startIcon={<HomeIcon />}
                onClick={handleGoHome}
              >
                Go Home
              </Button>
            </Stack>
          </Box>
        );

      default:
        return null;
    }
  };

  return (
    <Container component="main" maxWidth="sm">
      <Box
        sx={{
          marginTop: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <Paper
          elevation={3}
          sx={{
            padding: 4,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            width: '100%',
            minHeight: 300,
            justifyContent: 'center',
          }}
        >
          {/* Logo/Title */}
          <Typography 
            component="h1" 
            variant="h4" 
            sx={{ mb: 4 }}
            align="center"
          >
            Agency Dark
          </Typography>

          {/* Main Content */}
          {renderContent()}
        </Paper>

        {/* Footer */}
        <Typography
          variant="body2"
          color="text.secondary"
          align="center"
          sx={{ mt: 4 }}
        >
          Secure OAuth 2.0 Authentication
        </Typography>
      </Box>
    </Container>
  );
};

export default OAuthCallback;