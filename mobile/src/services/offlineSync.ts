/**
 * Offline Data Synchronization Service
 * 
 * Manages offline data storage and synchronization with the backend
 */
import NetInfo from '@react-native-community/netinfo';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { MMKV } from 'react-native-mmkv';
import BackgroundFetch from 'react-native-background-fetch';
import { differenceInMinutes } from 'date-fns';

import { api } from './api';
import { showMessage } from '@/utils/toast';

// Initialize MMKV for faster offline storage
const storage = new MMKV({
  id: 'offline-sync-storage',
  encryptionKey: 'agencydark-offline-encryption-key',
});

interface SyncQueueItem {
  id: string;
  type: 'create' | 'update' | 'delete';
  endpoint: string;
  data: any;
  timestamp: number;
  retries: number;
  priority: 'high' | 'normal' | 'low';
}

interface SyncStatus {
  lastSyncTime: number;
  pendingCount: number;
  failedCount: number;
  isRunning: boolean;
}

interface OfflineConfig {
  maxRetries: number;
  syncInterval: number; // minutes
  batchSize: number;
  enableBackgroundSync: boolean;
}

class OfflineSyncService {
  private syncQueue: Map<string, SyncQueueItem> = new Map();
  private syncStatus: SyncStatus = {
    lastSyncTime: 0,
    pendingCount: 0,
    failedCount: 0,
    isRunning: false,
  };
  private config: OfflineConfig = {
    maxRetries: 3,
    syncInterval: 15, // 15 minutes
    batchSize: 10,
    enableBackgroundSync: true,
  };
  private isOnline: boolean = true;
  private syncListeners: Set<(status: SyncStatus) => void> = new Set();

  constructor() {
    this.initialize();
  }

  // Initialize offline sync
  private async initialize(): Promise<void> {
    try {
      // Load sync queue from storage
      await this.loadSyncQueue();
      
      // Load sync status
      await this.loadSyncStatus();
      
      // Monitor network connectivity
      this.setupNetworkMonitoring();
      
      // Setup background sync
      if (this.config.enableBackgroundSync) {
        await this.setupBackgroundSync();
      }
      
      // Start sync if online and have pending items
      if (this.isOnline && this.syncStatus.pendingCount > 0) {
        this.startSync();
      }
    } catch (error) {
      console.error('Failed to initialize offline sync:', error);
    }
  }

  // Setup network monitoring
  private setupNetworkMonitoring(): void {
    NetInfo.addEventListener(state => {
      const wasOffline = !this.isOnline;
      this.isOnline = state.isConnected && state.isInternetReachable !== false;
      
      if (wasOffline && this.isOnline) {
        console.log('Network connected, starting sync');
        this.startSync();
      }
    });
  }

  // Setup background sync
  private async setupBackgroundSync(): Promise<void> {
    try {
      await BackgroundFetch.configure(
        {
          minimumFetchInterval: this.config.syncInterval,
          stopOnTerminate: false,
          startOnBoot: true,
          enableHeadless: true,
        },
        async (taskId) => {
          console.log('[BackgroundFetch] Sync task started:', taskId);
          
          // Perform sync
          await this.performBackgroundSync();
          
          // Signal completion
          BackgroundFetch.finish(taskId);
        },
        (error) => {
          console.error('[BackgroundFetch] Failed to configure:', error);
        }
      );

      // Check background fetch status
      const status = await BackgroundFetch.status();
      console.log('[BackgroundFetch] Status:', status);
    } catch (error) {
      console.error('Failed to setup background sync:', error);
    }
  }

  // Add item to sync queue
  async addToSyncQueue(
    type: 'create' | 'update' | 'delete',
    endpoint: string,
    data: any,
    priority: 'high' | 'normal' | 'low' = 'normal'
  ): Promise<string> {
    const id = `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const item: SyncQueueItem = {
      id,
      type,
      endpoint,
      data,
      timestamp: Date.now(),
      retries: 0,
      priority,
    };
    
    // Add to queue
    this.syncQueue.set(id, item);
    
    // Save to storage
    await this.saveSyncQueue();
    
    // Update status
    this.syncStatus.pendingCount = this.syncQueue.size;
    await this.saveSyncStatus();
    
    // Try to sync immediately if online and high priority
    if (this.isOnline && priority === 'high' && !this.syncStatus.isRunning) {
      this.startSync();
    }
    
    return id;
  }

  // Remove item from sync queue
  async removeFromSyncQueue(id: string): Promise<void> {
    this.syncQueue.delete(id);
    await this.saveSyncQueue();
    
    this.syncStatus.pendingCount = this.syncQueue.size;
    await this.saveSyncStatus();
  }

  // Start synchronization
  async startSync(): Promise<void> {
    if (!this.isOnline || this.syncStatus.isRunning || this.syncQueue.size === 0) {
      return;
    }
    
    this.syncStatus.isRunning = true;
    this.notifyListeners();
    
    try {
      await this.performSync();
    } finally {
      this.syncStatus.isRunning = false;
      this.syncStatus.lastSyncTime = Date.now();
      await this.saveSyncStatus();
      this.notifyListeners();
    }
  }

  // Perform synchronization
  private async performSync(): Promise<void> {
    const items = Array.from(this.syncQueue.values())
      .sort((a, b) => {
        // Sort by priority then timestamp
        const priorityOrder = { high: 0, normal: 1, low: 2 };
        if (priorityOrder[a.priority] !== priorityOrder[b.priority]) {
          return priorityOrder[a.priority] - priorityOrder[b.priority];
        }
        return a.timestamp - b.timestamp;
      })
      .slice(0, this.config.batchSize);
    
    let successCount = 0;
    let failCount = 0;
    
    for (const item of items) {
      try {
        await this.syncItem(item);
        await this.removeFromSyncQueue(item.id);
        successCount++;
      } catch (error) {
        console.error(`Failed to sync item ${item.id}:`, error);
        failCount++;
        
        // Update retry count
        item.retries++;
        
        if (item.retries >= this.config.maxRetries) {
          // Move to failed items
          await this.moveToFailedItems(item);
          await this.removeFromSyncQueue(item.id);
        } else {
          // Update in queue
          this.syncQueue.set(item.id, item);
        }
      }
    }
    
    // Update status
    this.syncStatus.failedCount += failCount;
    
    // Continue syncing if more items
    if (this.syncQueue.size > 0 && this.isOnline) {
      setTimeout(() => this.startSync(), 1000);
    }
    
    // Show sync result
    if (successCount > 0) {
      showMessage(`Synced ${successCount} items`, 'success');
    }
  }

  // Sync individual item
  private async syncItem(item: SyncQueueItem): Promise<void> {
    switch (item.type) {
      case 'create':
        await api.post(item.endpoint, item.data);
        break;
      case 'update':
        await api.put(item.endpoint, item.data);
        break;
      case 'delete':
        await api.delete(item.endpoint);
        break;
    }
  }

  // Perform background sync
  private async performBackgroundSync(): Promise<void> {
    if (!this.isOnline || this.syncQueue.size === 0) {
      return;
    }
    
    // Check if enough time has passed since last sync
    const minutesSinceLastSync = differenceInMinutes(
      new Date(),
      new Date(this.syncStatus.lastSyncTime)
    );
    
    if (minutesSinceLastSync < this.config.syncInterval) {
      return;
    }
    
    await this.startSync();
  }

  // Cache data for offline access
  async cacheData(key: string, data: any, ttl?: number): Promise<void> {
    const cacheItem = {
      data,
      timestamp: Date.now(),
      ttl: ttl || 0, // 0 means no expiration
    };
    
    storage.set(key, JSON.stringify(cacheItem));
  }

  // Get cached data
  async getCachedData<T>(key: string): Promise<T | null> {
    try {
      const cached = storage.getString(key);
      if (!cached) return null;
      
      const cacheItem = JSON.parse(cached);
      
      // Check if expired
      if (cacheItem.ttl > 0) {
        const age = Date.now() - cacheItem.timestamp;
        if (age > cacheItem.ttl) {
          storage.delete(key);
          return null;
        }
      }
      
      return cacheItem.data as T;
    } catch (error) {
      console.error('Failed to get cached data:', error);
      return null;
    }
  }

  // Clear cache
  async clearCache(pattern?: string): Promise<void> {
    if (pattern) {
      const keys = storage.getAllKeys();
      keys.forEach(key => {
        if (key.includes(pattern)) {
          storage.delete(key);
        }
      });
    } else {
      storage.clearAll();
    }
  }

  // Save sync queue to storage
  private async saveSyncQueue(): Promise<void> {
    const queueArray = Array.from(this.syncQueue.entries());
    await AsyncStorage.setItem('@sync_queue', JSON.stringify(queueArray));
  }

  // Load sync queue from storage
  private async loadSyncQueue(): Promise<void> {
    try {
      const queueString = await AsyncStorage.getItem('@sync_queue');
      if (queueString) {
        const queueArray = JSON.parse(queueString);
        this.syncQueue = new Map(queueArray);
      }
    } catch (error) {
      console.error('Failed to load sync queue:', error);
    }
  }

  // Save sync status
  private async saveSyncStatus(): Promise<void> {
    await AsyncStorage.setItem('@sync_status', JSON.stringify(this.syncStatus));
  }

  // Load sync status
  private async loadSyncStatus(): Promise<void> {
    try {
      const statusString = await AsyncStorage.getItem('@sync_status');
      if (statusString) {
        this.syncStatus = JSON.parse(statusString);
      }
    } catch (error) {
      console.error('Failed to load sync status:', error);
    }
  }

  // Move item to failed items
  private async moveToFailedItems(item: SyncQueueItem): Promise<void> {
    const failedItems = await this.getFailedItems();
    failedItems.push(item);
    await AsyncStorage.setItem('@failed_sync_items', JSON.stringify(failedItems));
  }

  // Get failed items
  async getFailedItems(): Promise<SyncQueueItem[]> {
    try {
      const itemsString = await AsyncStorage.getItem('@failed_sync_items');
      return itemsString ? JSON.parse(itemsString) : [];
    } catch (error) {
      console.error('Failed to get failed items:', error);
      return [];
    }
  }

  // Retry failed items
  async retryFailedItems(): Promise<void> {
    const failedItems = await this.getFailedItems();
    
    for (const item of failedItems) {
      item.retries = 0; // Reset retry count
      await this.addToSyncQueue(item.type, item.endpoint, item.data, item.priority);
    }
    
    // Clear failed items
    await AsyncStorage.removeItem('@failed_sync_items');
    
    // Start sync
    this.startSync();
  }

  // Add sync status listener
  addSyncListener(listener: (status: SyncStatus) => void): () => void {
    this.syncListeners.add(listener);
    return () => this.syncListeners.delete(listener);
  }

  // Notify listeners
  private notifyListeners(): void {
    this.syncListeners.forEach(listener => listener(this.syncStatus));
  }

  // Get sync status
  getSyncStatus(): SyncStatus {
    return { ...this.syncStatus };
  }

  // Configure offline sync
  async configure(config: Partial<OfflineConfig>): Promise<void> {
    this.config = { ...this.config, ...config };
    
    if (config.enableBackgroundSync !== undefined) {
      if (config.enableBackgroundSync) {
        await this.setupBackgroundSync();
      } else {
        await BackgroundFetch.stop();
      }
    }
  }

  // Clear all offline data
  async clearAll(): Promise<void> {
    this.syncQueue.clear();
    await AsyncStorage.multiRemove([
      '@sync_queue',
      '@sync_status',
      '@failed_sync_items',
    ]);
    storage.clearAll();
    
    this.syncStatus = {
      lastSyncTime: 0,
      pendingCount: 0,
      failedCount: 0,
      isRunning: false,
    };
    
    this.notifyListeners();
  }
}

export const offlineSyncService = new OfflineSyncService();

// Export convenience functions
export const cacheData = (key: string, data: any, ttl?: number) => 
  offlineSyncService.cacheData(key, data, ttl);

export const getCachedData = <T>(key: string) => 
  offlineSyncService.getCachedData<T>(key);

export const addToSyncQueue = (
  type: 'create' | 'update' | 'delete',
  endpoint: string,
  data: any,
  priority?: 'high' | 'normal' | 'low'
) => offlineSyncService.addToSyncQueue(type, endpoint, data, priority);