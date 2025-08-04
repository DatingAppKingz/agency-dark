import React, { useEffect, useState, createContext, useContext } from 'react';
import { useAuthStore } from '@/store/authStore';
import { realtimeService, ConnectionState, useRealtimeConnection } from '@/services/realtimeService';
import { Box, Snackbar, Alert, Chip } from '@mui/material';
import { WifiOff, Wifi, Sync } from '@mui/icons-material';

interface RealtimeContextValue {
  connectionState: ConnectionState;
  isConnected: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

export const useRealtime = () => {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error('useRealtime must be used within RealtimeProvider');
  }
  return context;
};

interface RealtimeProviderProps {
  children: React.ReactNode;
  showConnectionStatus?: boolean;
  autoConnect?: boolean;
}

export const RealtimeProvider: React.FC<RealtimeProviderProps> = ({
  children,
  showConnectionStatus = true,
  autoConnect = true,
}) => {
  const { user, isAuthenticated } = useAuthStore();
  const { connectionState, isConnected, connect, disconnect } = useRealtimeConnection();
  const [showReconnecting, setShowReconnecting] = useState(false);
  const [showError, setShowError] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // Auto-connect when authenticated
  useEffect(() => {
    if (autoConnect && isAuthenticated && user) {
      const token = localStorage.getItem('access_token'); // Or get from auth store
      if (token) {
        connect({ token })
          .catch(error => {
            console.error('Failed to connect to realtime service:', error);
            setErrorMessage('Failed to establish real-time connection');
            setShowError(true);
          });
      }
    } else if (!isAuthenticated) {
      disconnect();
    }
  }, [isAuthenticated, user, autoConnect]);

  // Handle connection state changes
  useEffect(() => {
    const handleReconnecting = () => setShowReconnecting(true);
    const handleReconnected = () => {
      setShowReconnecting(false);
      setShowError(false);
    };
    const handleError = (error: Error) => {
      setErrorMessage(error.message || 'Connection error occurred');
      setShowError(true);
    };
    const handleMaxReconnectAttempts = () => {
      setErrorMessage('Unable to establish connection. Please refresh the page.');
      setShowError(true);
      setShowReconnecting(false);
    };

    realtimeService.on('reconnecting', handleReconnecting);
    realtimeService.on('reconnected', handleReconnected);
    realtimeService.on('error', handleError);
    realtimeService.on('maxReconnectAttemptsReached', handleMaxReconnectAttempts);

    return () => {
      realtimeService.off('reconnecting', handleReconnecting);
      realtimeService.off('reconnected', handleReconnected);
      realtimeService.off('error', handleError);
      realtimeService.off('maxReconnectAttemptsReached', handleMaxReconnectAttempts);
    };
  }, []);

  // Connection status indicator
  const ConnectionStatus = () => {
    if (!showConnectionStatus) return null;

    const getStatusColor = () => {
      switch (connectionState) {
        case ConnectionState.CONNECTED:
          return 'success';
        case ConnectionState.CONNECTING:
        case ConnectionState.RECONNECTING:
          return 'warning';
        case ConnectionState.DISCONNECTED:
        case ConnectionState.ERROR:
          return 'error';
        default:
          return 'default';
      }
    };

    const getStatusIcon = () => {
      switch (connectionState) {
        case ConnectionState.CONNECTED:
          return <Wifi fontSize="small" />;
        case ConnectionState.CONNECTING:
        case ConnectionState.RECONNECTING:
          return <Sync fontSize="small" className="rotate-animation" />;
        case ConnectionState.DISCONNECTED:
        case ConnectionState.ERROR:
          return <WifiOff fontSize="small" />;
        default:
          return null;
      }
    };

    const getStatusLabel = () => {
      switch (connectionState) {
        case ConnectionState.CONNECTED:
          return 'Connected';
        case ConnectionState.CONNECTING:
          return 'Connecting...';
        case ConnectionState.RECONNECTING:
          return 'Reconnecting...';
        case ConnectionState.DISCONNECTED:
          return 'Disconnected';
        case ConnectionState.ERROR:
          return 'Connection Error';
        default:
          return connectionState;
      }
    };

    return (
      <Box
        sx={{
          position: 'fixed',
          bottom: 16,
          right: 16,
          zIndex: 1000,
        }}
      >
        <Chip
          icon={getStatusIcon()}
          label={getStatusLabel()}
          color={getStatusColor()}
          size="small"
          variant="filled"
        />
      </Box>
    );
  };

  const contextValue: RealtimeContextValue = {
    connectionState,
    isConnected,
    connect: async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        await connect({ token });
      } else {
        throw new Error('No authentication token available');
      }
    },
    disconnect,
  };

  return (
    <RealtimeContext.Provider value={contextValue}>
      {children}
      <ConnectionStatus />
      
      {/* Reconnecting notification */}
      <Snackbar
        open={showReconnecting}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert severity="warning" icon={<Sync className="rotate-animation" />}>
          Reconnecting to server...
        </Alert>
      </Snackbar>

      {/* Error notification */}
      <Snackbar
        open={showError}
        autoHideDuration={6000}
        onClose={() => setShowError(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        <Alert 
          severity="error" 
          onClose={() => setShowError(false)}
          action={
            connectionState === ConnectionState.ERROR ? (
              <Box 
                component="span" 
                sx={{ cursor: 'pointer', textDecoration: 'underline' }}
                onClick={() => window.location.reload()}
              >
                Refresh Page
              </Box>
            ) : undefined
          }
        >
          {errorMessage}
        </Alert>
      </Snackbar>

      <style>
        {`
          @keyframes rotate {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          .rotate-animation {
            animation: rotate 1s linear infinite;
          }
        `}
      </style>
    </RealtimeContext.Provider>
  );
};