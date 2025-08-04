import { QueryClient } from '@tanstack/react-query';

interface CacheConfig {
  maxAge: number; // Maximum age in milliseconds
  maxSize: number; // Maximum number of entries
  persistToStorage: boolean;
  storageKey: string;
}

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  size: number;
  accessCount: number;
  lastAccessed: number;
}

class CacheService {
  private memoryCache: Map<string, CacheEntry<any>> = new Map();
  private config: CacheConfig;
  private totalSize: number = 0;
  private queryClient?: QueryClient;

  constructor(config: Partial<CacheConfig> = {}) {
    this.config = {
      maxAge: 5 * 60 * 1000, // 5 minutes default
      maxSize: 100, // 100 entries default
      persistToStorage: true,
      storageKey: 'app-cache',
      ...config,
    };

    if (this.config.persistToStorage) {
      this.loadFromStorage();
    }
  }

  // Set query client for React Query integration
  setQueryClient(queryClient: QueryClient) {
    this.queryClient = queryClient;
  }

  // Generate cache key
  generateKey(endpoint: string, params?: Record<string, any>): string {
    const sortedParams = params ? JSON.stringify(this.sortObject(params)) : '';
    return `${endpoint}:${sortedParams}`;
  }

  // Sort object keys for consistent cache keys
  private sortObject(obj: Record<string, any>): Record<string, any> {
    return Object.keys(obj)
      .sort()
      .reduce((sorted, key) => {
        sorted[key] = obj[key];
        return sorted;
      }, {} as Record<string, any>);
  }

  // Get from cache
  get<T>(key: string): T | null {
    const entry = this.memoryCache.get(key);
    
    if (!entry) {
      return null;
    }

    // Check if expired
    if (this.isExpired(entry)) {
      this.delete(key);
      return null;
    }

    // Update access info
    entry.accessCount++;
    entry.lastAccessed = Date.now();

    return entry.data;
  }

  // Set in cache
  set<T>(key: string, data: T, options?: { maxAge?: number }): void {
    const size = this.estimateSize(data);
    const maxAge = options?.maxAge || this.config.maxAge;

    // Check if we need to evict entries
    if (this.memoryCache.size >= this.config.maxSize) {
      this.evictLRU();
    }

    const entry: CacheEntry<T> = {
      data,
      timestamp: Date.now(),
      size,
      accessCount: 1,
      lastAccessed: Date.now(),
    };

    this.memoryCache.set(key, entry);
    this.totalSize += size;

    // Update React Query cache if available
    if (this.queryClient) {
      const [endpoint, params] = key.split(':');
      this.queryClient.setQueryData([endpoint, params ? JSON.parse(params) : undefined], data);
    }

    // Persist to storage
    if (this.config.persistToStorage) {
      this.saveToStorage();
    }
  }

  // Delete from cache
  delete(key: string): boolean {
    const entry = this.memoryCache.get(key);
    if (entry) {
      this.totalSize -= entry.size;
      this.memoryCache.delete(key);
      
      if (this.config.persistToStorage) {
        this.saveToStorage();
      }
      
      return true;
    }
    return false;
  }

  // Clear entire cache
  clear(): void {
    this.memoryCache.clear();
    this.totalSize = 0;
    
    if (this.config.persistToStorage) {
      localStorage.removeItem(this.config.storageKey);
    }

    if (this.queryClient) {
      this.queryClient.clear();
    }
  }

  // Check if entry is expired
  private isExpired(entry: CacheEntry<any>): boolean {
    return Date.now() - entry.timestamp > this.config.maxAge;
  }

  // Evict least recently used entry
  private evictLRU(): void {
    let lruKey: string | null = null;
    let lruTime = Infinity;

    this.memoryCache.forEach((entry, key) => {
      if (entry.lastAccessed < lruTime) {
        lruTime = entry.lastAccessed;
        lruKey = key;
      }
    });

    if (lruKey) {
      this.delete(lruKey);
    }
  }

  // Estimate size of data
  private estimateSize(data: any): number {
    if (data === null || data === undefined) return 0;
    
    const str = JSON.stringify(data);
    return str.length * 2; // Rough estimate (2 bytes per character)
  }

  // Save to localStorage
  private saveToStorage(): void {
    if (!this.config.persistToStorage) return;

    try {
      const cacheData: Record<string, CacheEntry<any>> = {};
      
      // Only persist non-expired entries
      this.memoryCache.forEach((entry, key) => {
        if (!this.isExpired(entry)) {
          cacheData[key] = entry;
        }
      });

      localStorage.setItem(this.config.storageKey, JSON.stringify(cacheData));
    } catch (e) {
      console.warn('Failed to save cache to localStorage:', e);
    }
  }

  // Load from localStorage
  private loadFromStorage(): void {
    if (!this.config.persistToStorage) return;

    try {
      const stored = localStorage.getItem(this.config.storageKey);
      if (!stored) return;

      const cacheData = JSON.parse(stored) as Record<string, CacheEntry<any>>;
      
      Object.entries(cacheData).forEach(([key, entry]) => {
        if (!this.isExpired(entry)) {
          this.memoryCache.set(key, entry);
          this.totalSize += entry.size;
        }
      });
    } catch (e) {
      console.warn('Failed to load cache from localStorage:', e);
    }
  }

  // Get cache statistics
  getStats() {
    const entries = Array.from(this.memoryCache.entries());
    const now = Date.now();

    return {
      totalEntries: this.memoryCache.size,
      totalSize: this.totalSize,
      averageSize: this.totalSize / (this.memoryCache.size || 1),
      hitRate: this.calculateHitRate(),
      expirationStats: {
        expired: entries.filter(([_, entry]) => this.isExpired(entry)).length,
        active: entries.filter(([_, entry]) => !this.isExpired(entry)).length,
      },
      ageStats: {
        oldest: Math.min(...entries.map(([_, entry]) => entry.timestamp)),
        newest: Math.max(...entries.map(([_, entry]) => entry.timestamp)),
        average: entries.reduce((sum, [_, entry]) => sum + (now - entry.timestamp), 0) / entries.length,
      },
    };
  }

  // Calculate cache hit rate
  private calculateHitRate(): number {
    let hits = 0;
    let total = 0;

    this.memoryCache.forEach(entry => {
      total += entry.accessCount;
      if (entry.accessCount > 1) {
        hits += entry.accessCount - 1;
      }
    });

    return total > 0 ? (hits / total) * 100 : 0;
  }

  // Preload cache with critical data
  async preload(requests: Array<{ key: string; fetcher: () => Promise<any> }>): Promise<void> {
    const promises = requests.map(async ({ key, fetcher }) => {
      try {
        const existing = this.get(key);
        if (!existing) {
          const data = await fetcher();
          this.set(key, data);
        }
      } catch (error) {
        console.error(`Failed to preload cache for key ${key}:`, error);
      }
    });

    await Promise.all(promises);
  }

  // Invalidate cache entries matching pattern
  invalidate(pattern: string | RegExp): number {
    let count = 0;
    const regex = typeof pattern === 'string' ? new RegExp(pattern) : pattern;

    Array.from(this.memoryCache.keys()).forEach(key => {
      if (regex.test(key)) {
        this.delete(key);
        count++;
      }
    });

    return count;
  }

  // Refresh stale entries
  async refreshStale(
    staleness: number = this.config.maxAge * 0.8,
    fetcher: (key: string) => Promise<any>
  ): Promise<void> {
    const now = Date.now();
    const staleEntries: string[] = [];

    this.memoryCache.forEach((entry, key) => {
      if (now - entry.timestamp > staleness) {
        staleEntries.push(key);
      }
    });

    // Refresh stale entries in background
    staleEntries.forEach(async key => {
      try {
        const data = await fetcher(key);
        this.set(key, data);
      } catch (error) {
        console.error(`Failed to refresh cache for key ${key}:`, error);
      }
    });
  }
}

// Create singleton instance
export const cacheService = new CacheService();

// React Query cache adapter
export const createQueryCacheAdapter = (queryClient: QueryClient) => {
  cacheService.setQueryClient(queryClient);

  return {
    // Prefetch and cache
    prefetchQuery: async <T>(
      key: string | string[],
      fetcher: () => Promise<T>,
      options?: { maxAge?: number }
    ) => {
      const cacheKey = Array.isArray(key) ? key.join(':') : key;
      
      const cached = cacheService.get<T>(cacheKey);
      if (cached) {
        return cached;
      }

      const data = await fetcher();
      cacheService.set(cacheKey, data, options);
      
      return data;
    },

    // Invalidate queries
    invalidateQueries: (pattern: string | RegExp) => {
      const count = cacheService.invalidate(pattern);
      queryClient.invalidateQueries();
      return count;
    },

    // Get from cache
    getQueryData: <T>(key: string | string[]): T | null => {
      const cacheKey = Array.isArray(key) ? key.join(':') : key;
      return cacheService.get<T>(cacheKey);
    },

    // Set query data
    setQueryData: <T>(key: string | string[], data: T) => {
      const cacheKey = Array.isArray(key) ? key.join(':') : key;
      cacheService.set(cacheKey, data);
    },
  };
};

// Optimistic updates helper
export const optimisticUpdate = <T>(
  key: string,
  updater: (old: T) => T
): T | null => {
  const current = cacheService.get<T>(key);
  if (current) {
    const updated = updater(current);
    cacheService.set(key, updated);
    return updated;
  }
  return null;
};

// Cache warming utility
export const warmCache = async (endpoints: Array<{
  key: string;
  fetcher: () => Promise<any>;
  priority?: number;
}>) => {
  // Sort by priority (higher priority first)
  const sorted = endpoints.sort((a, b) => (b.priority || 0) - (a.priority || 0));
  
  // Warm cache in batches
  const batchSize = 5;
  for (let i = 0; i < sorted.length; i += batchSize) {
    const batch = sorted.slice(i, i + batchSize);
    await cacheService.preload(batch);
  }
};