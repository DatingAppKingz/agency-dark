import { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Switch,
  Button,
  Divider,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Chip } from '@mui/material';
import {
  Notifications,
  NotificationsActive,
  NotificationsOff,
  Check,
  Close } from '@mui/icons-material';
import { pushNotifications } from '@/services/pushNotifications';
import { useToast } from '@/components/common/Toaster';
import { useQuery, useMutation } from '@tanstack/react-query';
import apiClient from '@/services/api/client';

interface NotificationPreferences {
  push_enabled: boolean;
  email_enabled: boolean;
  new_messages: boolean;
  new_subscribers: boolean;
  new_tips: boolean;
  goal_achievements: boolean;
  system_updates: boolean;
  marketing: boolean;
}

export const NotificationSettings = () => {
  const { success, error } = useToast();
  const [pushPermission, setPushPermission] = useState<NotificationPermission>('default');
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isInitializing, setIsInitializing] = useState(true);

  // Fetch notification preferences
  const { data: preferences, refetch } = useQuery<NotificationPreferences>({
    queryKey: ['notification-preferences'],
    queryFn: async () => {
      const response = await apiClient.get('/users/notification-preferences');
      return response.data;
    } });

  // Update preferences mutation
  const updatePreferences = useMutation({
    mutationFn: async (updates: Partial<NotificationPreferences>) => {
      const response = await apiClient.patch('/users/notification-preferences', updates);
      return response.data;
    },
    onSuccess: () => {
      success('Notification preferences updated');
      refetch();
    },
    onError: () => {
      error('Failed to update preferences');
    } });

  useEffect(() => {
    const initPushNotifications = async () => {
      setIsInitializing(true);
      await pushNotifications.init();
      setPushPermission(pushNotifications.getPermissionStatus());
      setIsSubscribed(pushNotifications.isSubscribed());
      setIsInitializing(false);
    };

    initPushNotifications();
  }, []);

  const handleEnablePush = async () => {
    const permission = await pushNotifications.requestPermission();
    setPushPermission(permission);
    
    if (permission === 'granted') {
      setIsSubscribed(true);
      updatePreferences.mutate({ push_enabled: true });
    }
  };

  const handleDisablePush = async () => {
    const result = await pushNotifications.unsubscribe();
    if (result) {
      setIsSubscribed(false);
      updatePreferences.mutate({ push_enabled: false });
    }
  };

  const handleTestNotification = () => {
    pushNotifications.sendTestNotification();
    success('Test notification sent');
  };

  const handleTogglePreference = (key: keyof NotificationPreferences) => {
    if (preferences) {
      updatePreferences.mutate({ [key]: !preferences[key] });
    }
  };

  const getPermissionStatus = () => {
    switch (pushPermission) {
      case 'granted':
        return { text: 'Enabled', color: 'success', icon: <Check /> };
      case 'denied':
        return { text: 'Blocked', color: 'error', icon: <Close /> };
      default:
        return { text: 'Not Set', color: 'warning', icon: <Notifications /> };
    }
  };

  const status = getPermissionStatus();

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Notification Settings
      </Typography>

      {/* Push Notifications Status */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <NotificationsActive color="primary" />
            <Typography variant="h6">Push Notifications</Typography>
            <Chip
              label={status.text}
              color={status.color as 'success' | 'error' | 'warning'}
              size="small"
              icon={status.icon}
            />
          </Box>
        </Box>

        {pushPermission === 'denied' && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            Push notifications are blocked. Please enable them in your browser settings.
          </Alert>
        )}

        {pushPermission === 'default' && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Enable push notifications to receive instant updates about new messages and activities.
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 2 }}>
          {!isSubscribed && pushPermission !== 'denied' && (
            <Button
              variant="contained"
              onClick={handleEnablePush}
              disabled={isInitializing}
              startIcon={<NotificationsActive />}
            >
              Enable Push Notifications
            </Button>
          )}

          {isSubscribed && (
            <>
              <Button
                variant="outlined"
                onClick={handleTestNotification}
                startIcon={<Notifications />}
              >
                Send Test Notification
              </Button>
              <Button
                variant="outlined"
                color="error"
                onClick={handleDisablePush}
                startIcon={<NotificationsOff />}
              >
                Disable Push Notifications
              </Button>
            </>
          )}
        </Box>
      </Paper>

      {/* Notification Preferences */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Notification Preferences
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Choose what notifications you want to receive
        </Typography>

        <List>
          <ListItem>
            <ListItemText
              primary="Email Notifications"
              secondary="Receive notifications via email"
            />
            <ListItemSecondaryAction>
              <Switch
                checked={preferences?.email_enabled || false}
                onChange={() => handleTogglePreference('email_enabled')}
              />
            </ListItemSecondaryAction>
          </ListItem>

          <Divider />

          <ListItem>
            <ListItemText
              primary="New Messages"
              secondary="Get notified when you receive new messages"
            />
            <ListItemSecondaryAction>
              <Switch
                checked={preferences?.new_messages || false}
                onChange={() => handleTogglePreference('new_messages')}
              />
            </ListItemSecondaryAction>
          </ListItem>

          <ListItem>
            <ListItemText
              primary="New Subscribers"
              secondary="Get notified when someone subscribes"
            />
            <ListItemSecondaryAction>
              <Switch
                checked={preferences?.new_subscribers || false}
                onChange={() => handleTogglePreference('new_subscribers')}
              />
            </ListItemSecondaryAction>
          </ListItem>

          <ListItem>
            <ListItemText
              primary="Tips & Payments"
              secondary="Get notified about tips and payments"
            />
            <ListItemSecondaryAction>
              <Switch
                checked={preferences?.new_tips || false}
                onChange={() => handleTogglePreference('new_tips')}
              />
            </ListItemSecondaryAction>
          </ListItem>

          <ListItem>
            <ListItemText
              primary="Goal Achievements"
              secondary="Get notified when you reach your goals"
            />
            <ListItemSecondaryAction>
              <Switch
                checked={preferences?.goal_achievements || false}
                onChange={() => handleTogglePreference('goal_achievements')}
              />
            </ListItemSecondaryAction>
          </ListItem>

          <Divider />

          <ListItem>
            <ListItemText
              primary="System Updates"
              secondary="Important system updates and maintenance"
            />
            <ListItemSecondaryAction>
              <Switch
                checked={preferences?.system_updates || false}
                onChange={() => handleTogglePreference('system_updates')}
              />
            </ListItemSecondaryAction>
          </ListItem>

          <ListItem>
            <ListItemText
              primary="Marketing & Promotions"
              secondary="Tips, promotions, and platform news"
            />
            <ListItemSecondaryAction>
              <Switch
                checked={preferences?.marketing || false}
                onChange={() => handleTogglePreference('marketing')}
              />
            </ListItemSecondaryAction>
          </ListItem>
        </List>
      </Paper>
    </Box>
  );
};
