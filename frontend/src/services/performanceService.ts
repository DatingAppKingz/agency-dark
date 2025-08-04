import { debounce, throttle } from 'lodash';

interface PerformanceMetrics {
  FCP: number | null; // First Contentful Paint
  LCP: number | null; // Largest Contentful Paint
  FID: number | null; // First Input Delay
  CLS: number | null; // Cumulative Layout Shift
  TTFB: number | null; // Time to First Byte
  TTI: number | null; // Time to Interactive
}

interface ResourceTiming {
  name: string;
  duration: number;
  size: number;
  type: string;
}

class PerformanceService {
  private metrics: PerformanceMetrics = {
    FCP: null,
    LCP: null,
    FID: null,
    CLS: null,
    TTFB: null,
    TTI: null,
  };

  private observers: Map<string, PerformanceObserver> = new Map();
  private reportCallback?: (metrics: PerformanceMetrics) => void;

  constructor() {
    if (typeof window !== 'undefined' && 'performance' in window) {
      this.initializeObservers();
      this.measureTTFB();
    }
  }

  private initializeObservers() {
    // First Contentful Paint (FCP)
    this.observePaintTiming();
    
    // Largest Contentful Paint (LCP)
    this.observeLCP();
    
    // First Input Delay (FID)
    this.observeFID();
    
    // Cumulative Layout Shift (CLS)
    this.observeCLS();
    
    // Time to Interactive (TTI)
    this.observeTTI();
  }

  private observePaintTiming() {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === 'first-contentful-paint') {
            this.metrics.FCP = Math.round(entry.startTime);
            this.reportMetrics();
          }
        }
      });
      
      observer.observe({ entryTypes: ['paint'] });
      this.observers.set('paint', observer);
    } catch (e) {
      console.warn('Paint timing observer not supported');
    }
  }

  private observeLCP() {
    try {
      const observer = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        this.metrics.LCP = Math.round(lastEntry.startTime);
        this.reportMetrics();
      });
      
      observer.observe({ entryTypes: ['largest-contentful-paint'] });
      this.observers.set('lcp', observer);
    } catch (e) {
      console.warn('LCP observer not supported');
    }
  }

  private observeFID() {
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === 'first-input') {
            const fidEntry = entry as PerformanceEventTiming;
            this.metrics.FID = Math.round(fidEntry.processingStart - fidEntry.startTime);
            this.reportMetrics();
            observer.disconnect();
          }
        }
      });
      
      observer.observe({ entryTypes: ['first-input'] });
      this.observers.set('fid', observer);
    } catch (e) {
      console.warn('FID observer not supported');
    }
  }

  private observeCLS() {
    let clsValue = 0;
    let clsEntries: PerformanceEntry[] = [];
    
    try {
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (!(entry as any).hadRecentInput) {
            clsEntries.push(entry);
            clsValue += (entry as any).value;
          }
        }
        this.metrics.CLS = Math.round(clsValue * 1000) / 1000;
        this.reportMetrics();
      });
      
      observer.observe({ entryTypes: ['layout-shift'] });
      this.observers.set('cls', observer);
    } catch (e) {
      console.warn('CLS observer not supported');
    }
  }

  private observeTTI() {
    // Simplified TTI calculation
    if ('PerformanceObserver' in window && 'PerformanceLongTaskTiming' in window) {
      let lastLongTaskTime = 0;
      
      const observer = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          lastLongTaskTime = Math.max(lastLongTaskTime, entry.startTime + entry.duration);
        }
        
        // TTI is approximately when the last long task finishes
        this.metrics.TTI = Math.round(lastLongTaskTime);
        this.reportMetrics();
      });
      
      try {
        observer.observe({ entryTypes: ['longtask'] });
        this.observers.set('tti', observer);
      } catch (e) {
        console.warn('Long task observer not supported');
      }
    }
  }

  private measureTTFB() {
    const navigationTiming = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
    if (navigationTiming) {
      this.metrics.TTFB = Math.round(navigationTiming.responseStart - navigationTiming.requestStart);
      this.reportMetrics();
    }
  }

  private reportMetrics = debounce(() => {
    if (this.reportCallback) {
      this.reportCallback(this.metrics);
    }
    
    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.log('Performance Metrics:', this.metrics);
    }
    
    // Send to analytics
    this.sendToAnalytics(this.metrics);
  }, 1000);

  private sendToAnalytics(metrics: PerformanceMetrics) {
    // Send to your analytics service
    if (window.gtag) {
      Object.entries(metrics).forEach(([key, value]) => {
        if (value !== null) {
          window.gtag('event', 'web_vitals', {
            event_category: 'Performance',
            event_label: key,
            value: Math.round(value),
            non_interaction: true,
          });
        }
      });
    }
  }

  // Public methods
  
  onReport(callback: (metrics: PerformanceMetrics) => void) {
    this.reportCallback = callback;
  }

  getMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  measureResourceTiming(): ResourceTiming[] {
    const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
    
    return resources
      .filter(r => r.duration > 0)
      .map(r => ({
        name: r.name,
        duration: Math.round(r.duration),
        size: Math.round(r.transferSize || 0),
        type: this.getResourceType(r.name),
      }))
      .sort((a, b) => b.duration - a.duration)
      .slice(0, 20); // Top 20 slowest resources
  }

  private getResourceType(url: string): string {
    const extension = url.split('.').pop()?.toLowerCase() || '';
    const typeMap: Record<string, string> = {
      js: 'script',
      css: 'stylesheet',
      jpg: 'image',
      jpeg: 'image',
      png: 'image',
      gif: 'image',
      webp: 'image',
      svg: 'image',
      woff: 'font',
      woff2: 'font',
      ttf: 'font',
      eot: 'font',
    };
    
    return typeMap[extension] || 'other';
  }

  markCustomTiming(name: string) {
    if (performance.mark) {
      performance.mark(name);
    }
  }

  measureCustomTiming(name: string, startMark: string, endMark: string) {
    if (performance.measure) {
      try {
        performance.measure(name, startMark, endMark);
        const measures = performance.getEntriesByName(name, 'measure');
        if (measures.length > 0) {
          return Math.round(measures[0].duration);
        }
      } catch (e) {
        console.warn('Failed to measure timing:', e);
      }
    }
    return null;
  }

  cleanup() {
    this.observers.forEach(observer => observer.disconnect());
    this.observers.clear();
  }
}

// Create singleton instance
export const performanceService = new PerformanceService();

// React hook for performance monitoring
export const usePerformanceMonitoring = () => {
  const [metrics, setMetrics] = React.useState<PerformanceMetrics>(
    performanceService.getMetrics()
  );

  React.useEffect(() => {
    performanceService.onReport(setMetrics);
    
    return () => {
      // Cleanup if needed
    };
  }, []);

  return metrics;
};

// Performance optimization utilities

export const optimizeBundle = {
  // Lazy load heavy libraries
  loadMoment: () => import('moment'),
  loadChartJs: () => import('chart.js'),
  loadPdfLib: () => import('pdf-lib'),
  
  // Preload critical resources
  preloadFont: (url: string) => {
    const link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'font';
    link.href = url;
    link.crossOrigin = 'anonymous';
    document.head.appendChild(link);
  },
  
  preloadImage: (url: string) => {
    const link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'image';
    link.href = url;
    document.head.appendChild(link);
  },
  
  // Prefetch next page resources
  prefetchRoute: (path: string) => {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = path;
    document.head.appendChild(link);
  },
};

// Image loading optimization
export const imageOptimization = {
  // Generate blur placeholder
  generateBlurDataURL: async (imageSrc: string): Promise<string> => {
    return new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        // Create small version for blur
        const width = 20;
        const height = Math.round((img.height / img.width) * width);
        
        canvas.width = width;
        canvas.height = height;
        
        ctx?.drawImage(img, 0, 0, width, height);
        
        // Convert to data URL
        resolve(canvas.toDataURL('image/jpeg', 0.6));
      };
      
      img.onerror = () => {
        resolve(''); // Return empty string on error
      };
      
      img.src = imageSrc;
    });
  },
  
  // Progressive image loading
  loadProgressiveImage: (lowQualitySrc: string, highQualitySrc: string) => {
    return new Promise<string>((resolve) => {
      const img = new Image();
      
      // Load low quality first
      img.src = lowQualitySrc;
      img.onload = () => {
        resolve(lowQualitySrc);
        
        // Then load high quality
        const highQualityImg = new Image();
        highQualityImg.src = highQualitySrc;
        highQualityImg.onload = () => {
          resolve(highQualitySrc);
        };
      };
    });
  },
};

// Request optimization
export const requestOptimization = {
  // Batch API requests
  batchRequests: <T>(
    requests: (() => Promise<T>)[],
    batchSize: number = 5
  ): Promise<T[]> => {
    const results: T[] = [];
    
    const executeBatch = async (batch: (() => Promise<T>)[]): Promise<void> => {
      const batchResults = await Promise.all(batch.map(req => req()));
      results.push(...batchResults);
    };
    
    const processBatches = async () => {
      for (let i = 0; i < requests.length; i += batchSize) {
        const batch = requests.slice(i, i + batchSize);
        await executeBatch(batch);
      }
      return results;
    };
    
    return processBatches();
  },
  
  // Debounce API calls
  createDebouncedApi: <T extends (...args: any[]) => any>(
    fn: T,
    delay: number = 300
  ) => {
    return debounce(fn, delay);
  },
  
  // Throttle API calls
  createThrottledApi: <T extends (...args: any[]) => any>(
    fn: T,
    delay: number = 1000
  ) => {
    return throttle(fn, delay);
  },
};

// Memory optimization
export const memoryOptimization = {
  // Clean up large objects
  cleanup: (obj: any) => {
    if (obj && typeof obj === 'object') {
      Object.keys(obj).forEach(key => {
        delete obj[key];
      });
    }
  },
  
  // Monitor memory usage
  getMemoryUsage: () => {
    if ('memory' in performance) {
      const memory = (performance as any).memory;
      return {
        usedJSHeapSize: Math.round(memory.usedJSHeapSize / 1048576), // Convert to MB
        totalJSHeapSize: Math.round(memory.totalJSHeapSize / 1048576),
        jsHeapSizeLimit: Math.round(memory.jsHeapSizeLimit / 1048576),
      };
    }
    return null;
  },
};