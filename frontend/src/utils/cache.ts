// Cache utilities for API responses and assets

interface CacheItem<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

class CacheManager {
  private cache: Map<string, CacheItem<any>> = new Map();
  private localStorage: Storage | null = null;
  private maxSize: number = 100; // Maximum number of items in memory cache

  constructor() {
    if (typeof window !== 'undefined' && 'localStorage' in window) {
      this.localStorage = window.localStorage;
      this.loadFromLocalStorage();
    }
  }

  // Set item in cache
  set<T>(key: string, data: T, ttl: number = 300000): void { // Default 5 minutes
    const item: CacheItem<T> = {
      data,
      timestamp: Date.now(),
      ttl,
    };

    this.cache.set(key, item);
    
    // Implement LRU eviction if cache is too large
    if (this.cache.size > this.maxSize) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }

    // Save to localStorage for persistence
    this.saveToLocalStorage(key, item);
  }

  // Get item from cache
  get<T>(key: string): T | null {
    const item = this.cache.get(key);
    
    if (!item) {
      // Try to load from localStorage
      return this.getFromLocalStorage<T>(key);
    }

    // Check if expired
    if (Date.now() - item.timestamp > item.ttl) {
      this.delete(key);
      return null;
    }

    return item.data;
  }

  // Delete item from cache
  delete(key: string): void {
    this.cache.delete(key);
    this.deleteFromLocalStorage(key);
  }

  // Clear entire cache
  clear(): void {
    this.cache.clear();
    this.clearLocalStorage();
  }

  // Check if key exists and is valid
  has(key: string): boolean {
    const item = this.cache.get(key);
    if (!item) return false;
    
    if (Date.now() - item.timestamp > item.ttl) {
      this.delete(key);
      return false;
    }
    
    return true;
  }

  // Get cache statistics
  getStats() {
    let totalSize = 0;
    let expiredCount = 0;
    const now = Date.now();

    this.cache.forEach((item) => {
      totalSize += JSON.stringify(item.data).length;
      if (now - item.timestamp > item.ttl) {
        expiredCount++;
      }
    });

    return {
      itemCount: this.cache.size,
      totalSizeBytes: totalSize,
      totalSizeKB: (totalSize / 1024).toFixed(2),
      expiredCount,
    };
  }

  // LocalStorage methods
  private saveToLocalStorage(key: string, item: CacheItem<any>): void {
    if (!this.localStorage) return;
    
    try {
      this.localStorage.setItem(`cache_${key}`, JSON.stringify(item));
    } catch (e) {
      console.warn('Failed to save to localStorage:', e);
    }
  }

  private getFromLocalStorage<T>(key: string): T | null {
    if (!this.localStorage) return null;
    
    try {
      const stored = this.localStorage.getItem(`cache_${key}`);
      if (!stored) return null;
      
      const item: CacheItem<T> = JSON.parse(stored);
      
      // Check if expired
      if (Date.now() - item.timestamp > item.ttl) {
        this.deleteFromLocalStorage(key);
        return null;
      }
      
      // Re-add to memory cache
      this.cache.set(key, item);
      return item.data;
    } catch (e) {
      console.warn('Failed to load from localStorage:', e);
      return null;
    }
  }

  private deleteFromLocalStorage(key: string): void {
    if (!this.localStorage) return;
    
    try {
      this.localStorage.removeItem(`cache_${key}`);
    } catch (e) {
      console.warn('Failed to delete from localStorage:', e);
    }
  }

  private clearLocalStorage(): void {
    if (!this.localStorage) return;
    
    try {
      // Only clear cache items, not other localStorage data
      const keys = Object.keys(this.localStorage);
      keys.forEach(key => {
        if (key.startsWith('cache_')) {
          this.localStorage!.removeItem(key);
        }
      });
    } catch (e) {
      console.warn('Failed to clear localStorage:', e);
    }
  }

  private loadFromLocalStorage(): void {
    if (!this.localStorage) return;
    
    try {
      const keys = Object.keys(this.localStorage);
      keys.forEach(key => {
        if (key.startsWith('cache_')) {
          const stored = this.localStorage!.getItem(key);
          if (stored) {
            const item = JSON.parse(stored);
            const cacheKey = key.replace('cache_', '');
            
            // Only load if not expired
            if (Date.now() - item.timestamp <= item.ttl) {
              this.cache.set(cacheKey, item);
            } else {
              this.localStorage!.removeItem(key);
            }
          }
        }
      });
    } catch (e) {
      console.warn('Failed to load cache from localStorage:', e);
    }
  }
}

// Singleton instance
export const cache = new CacheManager();

// API Cache decorator
export function cacheAPI(ttl: number = 300000) {
  return function (target: any, propertyKey: string, descriptor: PropertyDescriptor) {
    const originalMethod = descriptor.value;

    descriptor.value = async function (...args: any[]) {
      // Generate cache key from method name and arguments
      const cacheKey = `api_${propertyKey}_${JSON.stringify(args)}`;
      
      // Check cache first
      const cached = cache.get(cacheKey);
      if (cached) {
        return cached;
      }

      // Call original method
      const result = await originalMethod.apply(this, args);
      
      // Cache the result
      cache.set(cacheKey, result, ttl);
      
      return result;
    };

    return descriptor;
  };
}

// React hook for cached data
import { useState, useEffect } from 'react';

export function useCachedData<T>(
  key: string,
  fetcher: () => Promise<T>,
  ttl: number = 300000
): {
  data: T | null;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
} {
  const [data, setData] = useState<T | null>(cache.get<T>(key));
  const [loading, setLoading] = useState(!data);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await fetcher();
      cache.set(key, result, ttl);
      setData(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!data) {
      fetchData();
    }
  }, [key]);

  const refresh = async () => {
    cache.delete(key);
    await fetchData();
  };

  return { data, loading, error, refresh };
}

// Service Worker cache strategy
export const setupServiceWorkerCache = () => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').then(registration => {
      console.log('Service Worker registered:', registration);
    }).catch(error => {
      console.log('Service Worker registration failed:', error);
    });
  }
};

// Prefetch critical resources
export const prefetchResources = (urls: string[]) => {
  urls.forEach(url => {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = url;
    document.head.appendChild(link);
  });
};

// Preconnect to external domains
export const preconnectDomains = (domains: string[]) => {
  domains.forEach(domain => {
    const link = document.createElement('link');
    link.rel = 'preconnect';
    link.href = domain;
    document.head.appendChild(link);
  });
};