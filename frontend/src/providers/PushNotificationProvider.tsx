import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { pushNotifications } from '@/services/pushNotifications';
import { useAuthStore } from '@/store/authStore';

interface PushNotificationContextType {
  isSupported: boolean;
  permission: NotificationPermission;
  isSubscribed: boolean;
  requestPermission: () => Promise<void>;
  unsubscribe: () => Promise<void>;
}

const PushNotificationContext = createContext<PushNotificationContextType>({
  isSupported: false,
  permission: 'default',
  isSubscribed: false,
  requestPermission: async () => {},
  unsubscribe: async () => {},
});

export const usePushNotifications = () => useContext(PushNotificationContext);

interface PushNotificationProviderProps {
  children: ReactNode;
}

export const PushNotificationProvider = ({ children }: PushNotificationProviderProps) => {
  const { isAuthenticated } = useAuthStore();
  const [isSupported, setIsSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>('default');
  const [isSubscribed, setIsSubscribed] = useState(false);

  useEffect(() => {
    const init = async () => {
      if (!isAuthenticated) return;

      const supported = await pushNotifications.init();
      setIsSupported(supported);

      if (supported) {
        setPermission(pushNotifications.getPermissionStatus());
        setIsSubscribed(pushNotifications.isSubscribed());
      }
    };

    init();
  }, [isAuthenticated]);

  const requestPermission = async () => {
    const newPermission = await pushNotifications.requestPermission();
    setPermission(newPermission);
    
    if (newPermission === 'granted') {
      setIsSubscribed(true);
    }
  };

  const unsubscribe = async () => {
    const result = await pushNotifications.unsubscribe();
    if (result) {
      setIsSubscribed(false);
    }
  };

  return (
    <PushNotificationContext.Provider
      value={{
        isSupported,
        permission,
        isSubscribed,
        requestPermission,
        unsubscribe,
      }}
    >
      {children}
    </PushNotificationContext.Provider>
  );
};