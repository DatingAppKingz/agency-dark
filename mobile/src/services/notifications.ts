/**
 * Push Notification Service
 * 
 * Handles push notification setup, permissions, and handling
 */
import messaging, { FirebaseMessagingTypes } from '@react-native-firebase/messaging';
import notifee, { AndroidImportance, AndroidStyle, EventType } from '@notifee/react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform, PermissionsAndroid } from 'react-native';
import DeviceInfo from 'react-native-device-info';

import { api } from './api';
import { navigationRef } from '@/navigation/RootNavigator';

const FCM_TOKEN_KEY = '@fcm_token';

interface NotificationData {
  id: string;
  title: string;
  body: string;
  type: 'message' | 'transaction' | 'alert' | 'update';
  data?: Record<string, any>;
  imageUrl?: string;
  deepLink?: string;
}

class NotificationService {
  private notificationListeners: Array<() => void> = [];

  // Initialize push notifications
  async setupNotifications(): Promise<void> {
    try {
      // Request permissions
      const hasPermission = await this.requestPermissions();
      if (!hasPermission) {
        console.log('Notification permissions denied');
        return;
      }

      // Create notification channels for Android
      if (Platform.OS === 'android') {
        await this.createNotificationChannels();
      }

      // Get FCM token
      await this.registerForPushNotifications();

      // Set up notification handlers
      this.setupNotificationHandlers();

      // Handle initial notification (app opened from notification)
      const initialNotification = await messaging().getInitialNotification();
      if (initialNotification) {
        this.handleNotificationOpen(initialNotification);
      }

    } catch (error) {
      console.error('Failed to setup notifications:', error);
    }
  }

  // Request notification permissions
  private async requestPermissions(): Promise<boolean> {
    if (Platform.OS === 'ios') {
      const authStatus = await messaging().requestPermission();
      const enabled =
        authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
        authStatus === messaging.AuthorizationStatus.PROVISIONAL;

      if (enabled) {
        console.log('iOS notification permissions granted');
      }

      return enabled;
    } else {
      // Android 13+ requires runtime permission
      if (Platform.Version >= 33) {
        const granted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS
        );
        return granted === PermissionsAndroid.RESULTS.GRANTED;
      }
      return true;
    }
  }

  // Create notification channels for Android
  private async createNotificationChannels(): Promise<void> {
    await notifee.createChannel({
      id: 'messages',
      name: 'Messages',
      description: 'New messages and conversations',
      importance: AndroidImportance.HIGH,
      sound: 'default',
    });

    await notifee.createChannel({
      id: 'transactions',
      name: 'Transactions',
      description: 'Transaction updates and confirmations',
      importance: AndroidImportance.HIGH,
      sound: 'default',
    });

    await notifee.createChannel({
      id: 'alerts',
      name: 'Alerts',
      description: 'Important alerts and warnings',
      importance: AndroidImportance.HIGH,
      sound: 'alert',
    });

    await notifee.createChannel({
      id: 'updates',
      name: 'Updates',
      description: 'General updates and information',
      importance: AndroidImportance.DEFAULT,
    });
  }

  // Register device for push notifications
  private async registerForPushNotifications(): Promise<void> {
    try {
      // Get FCM token
      const fcmToken = await messaging().getToken();
      
      // Check if token changed
      const storedToken = await AsyncStorage.getItem(FCM_TOKEN_KEY);
      if (fcmToken !== storedToken) {
        // Store new token
        await AsyncStorage.setItem(FCM_TOKEN_KEY, fcmToken);
        
        // Send to backend
        await this.sendTokenToBackend(fcmToken);
      }

      // Listen for token refreshes
      this.notificationListeners.push(
        messaging().onTokenRefresh(async (token) => {
          await AsyncStorage.setItem(FCM_TOKEN_KEY, token);
          await this.sendTokenToBackend(token);
        })
      );

    } catch (error) {
      console.error('Failed to register for push notifications:', error);
    }
  }

  // Send FCM token to backend
  private async sendTokenToBackend(token: string): Promise<void> {
    try {
      await api.post('/notifications/mobile/register', {
        fcm_token: token,
        device_id: await DeviceInfo.getUniqueId(),
        device_name: await DeviceInfo.getDeviceName(),
        platform: Platform.OS,
        platform_version: Platform.Version.toString(),
        app_version: DeviceInfo.getVersion(),
      });
    } catch (error) {
      console.error('Failed to send FCM token to backend:', error);
    }
  }

  // Set up notification handlers
  private setupNotificationHandlers(): void {
    // Handle foreground notifications
    this.notificationListeners.push(
      messaging().onMessage(async (remoteMessage) => {
        console.log('Foreground notification received:', remoteMessage);
        await this.displayLocalNotification(remoteMessage);
      })
    );

    // Handle notification opens
    this.notificationListeners.push(
      messaging().onNotificationOpenedApp((remoteMessage) => {
        console.log('Notification opened app:', remoteMessage);
        this.handleNotificationOpen(remoteMessage);
      })
    );

    // Handle local notification interactions
    notifee.onForegroundEvent(({ type, detail }) => {
      if (type === EventType.PRESS) {
        this.handleLocalNotificationPress(detail.notification);
      }
    });

    // Handle background events
    notifee.onBackgroundEvent(async ({ type, detail }) => {
      if (type === EventType.PRESS) {
        this.handleLocalNotificationPress(detail.notification);
      }
    });
  }

  // Display local notification for foreground messages
  private async displayLocalNotification(
    remoteMessage: FirebaseMessagingTypes.RemoteMessage
  ): Promise<void> {
    const { notification, data } = remoteMessage;
    
    if (!notification) return;

    const channelId = this.getChannelId(data?.type);
    
    const notificationOptions: any = {
      title: notification.title,
      body: notification.body,
      android: {
        channelId,
        importance: AndroidImportance.HIGH,
        pressAction: {
          id: 'default',
        },
      },
      ios: {
        sound: 'default',
      },
      data,
    };

    // Add image if available
    if (notification.android?.imageUrl || notification.apple?.imageUrl) {
      notificationOptions.android.largeIcon = notification.android?.imageUrl;
      notificationOptions.android.style = {
        type: AndroidStyle.BIGPICTURE,
        picture: notification.android?.imageUrl,
      };
      notificationOptions.ios.attachments = [{
        url: notification.apple?.imageUrl || notification.android?.imageUrl,
      }];
    }

    await notifee.displayNotification(notificationOptions);
  }

  // Get channel ID based on notification type
  private getChannelId(type?: string): string {
    switch (type) {
      case 'message':
        return 'messages';
      case 'transaction':
        return 'transactions';
      case 'alert':
        return 'alerts';
      default:
        return 'updates';
    }
  }

  // Handle notification open
  private handleNotificationOpen(
    remoteMessage: FirebaseMessagingTypes.RemoteMessage
  ): void {
    const { data } = remoteMessage;
    
    if (data?.deepLink) {
      // Navigate to deep link
      this.navigateToDeepLink(data.deepLink);
    } else if (data?.type) {
      // Navigate based on type
      this.navigateByType(data.type, data);
    }
  }

  // Handle local notification press
  private handleLocalNotificationPress(notification: any): void {
    const { data } = notification;
    
    if (data?.deepLink) {
      this.navigateToDeepLink(data.deepLink);
    } else if (data?.type) {
      this.navigateByType(data.type, data);
    }
  }

  // Navigate to deep link
  private navigateToDeepLink(deepLink: string): void {
    // Parse deep link and navigate
    // Example: agencydark://messages/123
    const [scheme, path] = deepLink.split('://');
    if (scheme === 'agencydark') {
      const [screen, id] = path.split('/');
      
      if (navigationRef.isReady()) {
        switch (screen) {
          case 'messages':
            navigationRef.navigate('Messages', { messageId: id });
            break;
          case 'transactions':
            navigationRef.navigate('TransactionDetails', { transactionId: id });
            break;
          case 'profile':
            navigationRef.navigate('Profile');
            break;
          default:
            navigationRef.navigate('Home');
        }
      }
    }
  }

  // Navigate based on notification type
  private navigateByType(type: string, data: any): void {
    if (!navigationRef.isReady()) return;

    switch (type) {
      case 'message':
        navigationRef.navigate('Messages', { 
          conversationId: data.conversation_id 
        });
        break;
      case 'transaction':
        navigationRef.navigate('Transactions', { 
          transactionId: data.transaction_id 
        });
        break;
      case 'alert':
        navigationRef.navigate('Notifications');
        break;
      default:
        navigationRef.navigate('Home');
    }
  }

  // Schedule local notification
  async scheduleNotification(
    notification: NotificationData,
    triggerDate: Date
  ): Promise<string> {
    const channelId = this.getChannelId(notification.type);
    
    const notificationId = await notifee.createTriggerNotification(
      {
        title: notification.title,
        body: notification.body,
        android: {
          channelId,
          importance: AndroidImportance.HIGH,
        },
        data: notification.data,
      },
      {
        type: notifee.TriggerType.TIMESTAMP,
        timestamp: triggerDate.getTime(),
      }
    );

    return notificationId;
  }

  // Cancel scheduled notification
  async cancelNotification(notificationId: string): Promise<void> {
    await notifee.cancelNotification(notificationId);
  }

  // Cancel all notifications
  async cancelAllNotifications(): Promise<void> {
    await notifee.cancelAllNotifications();
  }

  // Update notification preferences
  async updateNotificationPreferences(preferences: {
    messages: boolean;
    transactions: boolean;
    alerts: boolean;
    updates: boolean;
  }): Promise<void> {
    try {
      await api.put('/notifications/mobile/preferences', preferences);
      await AsyncStorage.setItem(
        '@notification_preferences',
        JSON.stringify(preferences)
      );
    } catch (error) {
      console.error('Failed to update notification preferences:', error);
      throw error;
    }
  }

  // Clean up listeners
  cleanup(): void {
    this.notificationListeners.forEach(unsubscribe => unsubscribe());
    this.notificationListeners = [];
  }
}

export const notificationService = new NotificationService();

// Export setup function for easy initialization
export const setupNotifications = () => notificationService.setupNotifications();