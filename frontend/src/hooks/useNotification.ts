import { useState, useCallback } from 'react';

interface Notification {
  id: string;
  title: string;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
}

interface NotificationOptions {
  title: string;
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
  duration?: number;
}

export const useNotification = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const showNotification = useCallback((options: NotificationOptions) => {
    const notification: Notification = {
      id: Date.now().toString(),
      duration: 5000,
      ...options
    };

    setNotifications((prev) => [...prev, notification]);

    if (notification.duration && notification.duration > 0) {
      setTimeout(() => {
        hideNotification(notification.id);
      }, notification.duration);
    }
  }, []);

  const hideNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return {
    notifications,
    showNotification,
    hideNotification
  };
};