interface CacheItem<T> {
  data: T;
  timestamp: number;
  expiresAt: number;
}

interface CacheOptions {
  ttl?: number; // Time to live in milliseconds
  storage?: 'memory' | 'localStorage' | 'sessionStorage';
}

class CacheService {
  private memoryCache = new Map<string, CacheItem<any>>();
  private defaultTTL = 5 * 60 * 1000; // 5 minutes

  constructor() {
    // Clean up expired items periodically
    if (typeof window !== 'undefined') {
      setInterval(() => this.cleanup(), 60 * 1000); // Every minute
    }
  }

  set<T>(key: string, data: T, options: CacheOptions = {}): void {
    const { ttl = this.defaultTTL, storage = 'memory' } = options;
    const timestamp = Date.now();
    const expiresAt = timestamp + ttl;

    const cacheItem: CacheItem<T> = {
      data,
      timestamp,
      expiresAt,
    };

    switch (storage) {
      case 'memory':
        this.memoryCache.set(key, cacheItem);
        break;
      case 'localStorage':
        if (typeof window !== 'undefined' && window.localStorage) {
          try {
            localStorage.setItem(key, JSON.stringify(cacheItem));
          } catch (e) {
            console.error('Failed to save to localStorage:', e);
            // Fallback to memory
            this.memoryCache.set(key, cacheItem);
          }
        }
        break;
      case 'sessionStorage':
        if (typeof window !== 'undefined' && window.sessionStorage) {
          try {
            sessionStorage.setItem(key, JSON.stringify(cacheItem));
          } catch (e) {
            console.error('Failed to save to sessionStorage:', e);
            // Fallback to memory
            this.memoryCache.set(key, cacheItem);
          }
        }
        break;
    }
  }

  get<T>(key: string, storage: 'memory' | 'localStorage' | 'sessionStorage' = 'memory'): T | null {
    let cacheItem: CacheItem<T> | null = null;

    switch (storage) {
      case 'memory':
        cacheItem = this.memoryCache.get(key) || null;
        break;
      case 'localStorage':
        if (typeof window !== 'undefined' && window.localStorage) {
          const item = localStorage.getItem(key);
          if (item) {
            try {
              cacheItem = JSON.parse(item);
            } catch (e) {
              console.error('Failed to parse localStorage item:', e);
              localStorage.removeItem(key);
            }
          }
        }
        break;
      case 'sessionStorage':
        if (typeof window !== 'undefined' && window.sessionStorage) {
          const item = sessionStorage.getItem(key);
          if (item) {
            try {
              cacheItem = JSON.parse(item);
            } catch (e) {
              console.error('Failed to parse sessionStorage item:', e);
              sessionStorage.removeItem(key);
            }
          }
        }
        break;
    }

    if (!cacheItem) return null;

    // Check if expired
    if (Date.now() > cacheItem.expiresAt) {
      this.delete(key, storage);
      return null;
    }

    return cacheItem.data;
  }

  delete(key: string, storage: 'memory' | 'localStorage' | 'sessionStorage' = 'memory'): void {
    switch (storage) {
      case 'memory':
        this.memoryCache.delete(key);
        break;
      case 'localStorage':
        if (typeof window !== 'undefined' && window.localStorage) {
          localStorage.removeItem(key);
        }
        break;
      case 'sessionStorage':
        if (typeof window !== 'undefined' && window.sessionStorage) {
          sessionStorage.removeItem(key);
        }
        break;
    }
  }

  clear(storage?: 'memory' | 'localStorage' | 'sessionStorage'): void {
    if (!storage || storage === 'memory') {
      this.memoryCache.clear();
    }
    if ((!storage || storage === 'localStorage') && typeof window !== 'undefined' && window.localStorage) {
      // Clear only cache-related items
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key.startsWith('cache_')) {
          localStorage.removeItem(key);
        }
      });
    }
    if ((!storage || storage === 'sessionStorage') && typeof window !== 'undefined' && window.sessionStorage) {
      // Clear only cache-related items
      const keys = Object.keys(sessionStorage);
      keys.forEach(key => {
        if (key.startsWith('cache_')) {
          sessionStorage.removeItem(key);
        }
      });
    }
  }

  private cleanup(): void {
    // Clean memory cache
    const now = Date.now();
    this.memoryCache.forEach((item, key) => {
      if (now > item.expiresAt) {
        this.memoryCache.delete(key);
      }
    });

    // Clean localStorage
    if (typeof window !== 'undefined' && window.localStorage) {
      const keys = Object.keys(localStorage);
      keys.forEach(key => {
        if (key.startsWith('cache_')) {
          const item = localStorage.getItem(key);
          if (item) {
            try {
              const cacheItem = JSON.parse(item);
              if (now > cacheItem.expiresAt) {
                localStorage.removeItem(key);
              }
            } catch (e) {
              localStorage.removeItem(key);
            }
          }
        }
      });
    }
  }

  // Generate cache key from request parameters
  generateKey(prefix: string, params: Record<string, any>): string {
    const sortedParams = Object.keys(params)
      .sort()
      .reduce((acc, key) => {
        acc[key] = params[key];
        return acc;
      }, {} as Record<string, any>);
    
    return `cache_${prefix}_${JSON.stringify(sortedParams)}`;
  }
}

export const cache = new CacheService();

// React Query cache configuration
export const queryClientConfig = {
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      refetchOnWindowFocus: false,
      refetchOnReconnect: 'always',
      retry: (failureCount: number, error: unknown) => {
        // Don't retry on 4xx errors
        const axiosError = error as { response?: { status?: number } };
        if (axiosError?.response?.status && axiosError.response.status >= 400 && axiosError.response.status < 500) {
          return false;
        }
        return failureCount < 3;
      },
    },
  },
};

// Cache strategies for different data types
export const cacheStrategies = {
  user: {
    ttl: 30 * 60 * 1000, // 30 minutes
    storage: 'sessionStorage' as const,
  },
  analytics: {
    ttl: 5 * 60 * 1000, // 5 minutes
    storage: 'memory' as const,
  },
  financial: {
    ttl: 1 * 60 * 1000, // 1 minute
    storage: 'memory' as const,
  },
  chat: {
    ttl: 30 * 1000, // 30 seconds
    storage: 'memory' as const,
  },
  static: {
    ttl: 24 * 60 * 60 * 1000, // 24 hours
    storage: 'localStorage' as const,
  },
};
