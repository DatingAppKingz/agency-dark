import { createContext, useContext, useEffect, ReactNode } from 'react';
import { socketManager } from '@/services/socket/socketManager';
import { useAuthStore } from '@/store/authStore';
import { useToast } from '@/components/common/Toaster';
import { logger } from '@/utils/logger';

const SocketContext = createContext(socketManager);

export const useSocket = () => {
  return useContext(SocketContext);
};

interface SocketProviderProps {
  children: ReactNode;
}

export const SocketProvider = ({ children }: SocketProviderProps) => {
  const { isAuthenticated } = useAuthStore();
  const { info, error } = useToast();

  useEffect(() => {
    if (isAuthenticated) {
      socketManager.connect();

      socketManager.on('connect', () => {
        logger.info('Connected to chat server');
      });

      socketManager.on('disconnect', (reason) => {
        if (reason === 'io server disconnect') {
          error('Disconnected from chat server');
        }
      });

      socketManager.on('error', (err) => {
        logger.error('Socket error:', err);
        error('Connection error. Please refresh the page.');
      });

      socketManager.on('notification', (notification) => {
        info(notification.message);
      });

      return () => {
        socketManager.disconnect();
      };
    }
  }, [isAuthenticated, info, error]);

  return (
    <SocketContext.Provider value={socketManager}>
      {children}
    </SocketContext.Provider>
  );
};
