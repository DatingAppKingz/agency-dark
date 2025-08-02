export const pushNotifications = {
  isSupported: jest.fn().mockReturnValue(true),
  
  requestPermission: jest.fn().mockResolvedValue(true),
  
  subscribeUser: jest.fn().mockResolvedValue({
    endpoint: 'https://push.example.com/123',
    keys: {
      p256dh: 'test-key',
      auth: 'test-auth'
    }
  }),
  
  unsubscribeUser: jest.fn().mockResolvedValue(undefined),
  
  sendNotification: jest.fn().mockResolvedValue(undefined),
  
  isSubscribed: jest.fn().mockResolvedValue(false),
  
  getSubscription: jest.fn().mockResolvedValue(null),
};