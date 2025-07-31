// Performance monitoring utilities
import { logger } from './logger';

interface PerformanceMetrics {
  FCP?: number; // First Contentful Paint
  LCP?: number; // Largest Contentful Paint
  FID?: number; // First Input Delay
  CLS?: number; // Cumulative Layout Shift
  TTFB?: number; // Time to First Byte
  INP?: number; // Interaction to Next Paint
}

class PerformanceMonitor {
  private metrics: PerformanceMetrics = {};
  private reportCallback?: (metrics: PerformanceMetrics) => void;

  constructor() {
    if (typeof window !== 'undefined' && 'PerformanceObserver' in window) {
      this.initializeObservers();
    }
  }

  private initializeObservers(): void {
    // First Contentful Paint (FCP)
    try {
      const fcpObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.name === 'first-contentful-paint') {
            this.metrics.FCP = Math.round(entry.startTime);
            this.report();
          }
        }
      });
      fcpObserver.observe({ entryTypes: ['paint'] });
    } catch (e) {
      logger.warn('FCP observer not supported');
    }

    // Largest Contentful Paint (LCP)
    try {
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        this.metrics.LCP = Math.round(lastEntry.startTime);
        this.report();
      });
      lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });
    } catch (e) {
      logger.warn('LCP observer not supported');
    }

    // First Input Delay (FID)
    try {
      const fidObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const firstInput = entry as PerformanceEventTiming;
          this.metrics.FID = Math.round(firstInput.processingStart - firstInput.startTime);
          this.report();
        }
      });
      fidObserver.observe({ entryTypes: ['first-input'] });
    } catch (e) {
      logger.warn('FID observer not supported');
    }

    // Cumulative Layout Shift (CLS)
    let clsValue = 0;
    const clsEntries: PerformanceEntry[] = [];
    
    try {
      const clsObserver = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          const layoutShift = entry as PerformanceEntry & { hadRecentInput?: boolean; value?: number };
          if (!layoutShift.hadRecentInput) {
            clsValue += layoutShift.value;
            clsEntries.push(entry);
          }
        }
        this.metrics.CLS = Math.round(clsValue * 1000) / 1000;
        this.report();
      });
      clsObserver.observe({ entryTypes: ['layout-shift'] });
    } catch (e) {
      logger.warn('CLS observer not supported');
    }

    // Time to First Byte (TTFB)
    if ('performance' in window && 'timing' in window.performance) {
      const navigationTiming = performance.timing;
      const ttfb = navigationTiming.responseStart - navigationTiming.requestStart;
      this.metrics.TTFB = Math.round(ttfb);
      this.report();
    }
  }

  public onReport(callback: (metrics: PerformanceMetrics) => void): void {
    this.reportCallback = callback;
  }

  private report(): void {
    if (this.reportCallback) {
      this.reportCallback(this.metrics);
    }
  }

  public getMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  public logMetrics(): void {
    logger.group('Performance Metrics');
    logger.info('FCP:', this.metrics.FCP ? `${this.metrics.FCP}ms` : 'Not measured');
    logger.info('LCP:', this.metrics.LCP ? `${this.metrics.LCP}ms` : 'Not measured');
    logger.info('FID:', this.metrics.FID ? `${this.metrics.FID}ms` : 'Not measured');
    logger.info('CLS:', this.metrics.CLS || 'Not measured');
    logger.info('TTFB:', this.metrics.TTFB ? `${this.metrics.TTFB}ms` : 'Not measured');
    logger.groupEnd();
  }
}

// Singleton instance
export const performanceMonitor = new PerformanceMonitor();

// React hook for performance monitoring
import { useEffect, useState } from 'react';

export const usePerformanceMetrics = () => {
  const [metrics, setMetrics] = useState<PerformanceMetrics>({});

  useEffect(() => {
    performanceMonitor.onReport((newMetrics) => {
      setMetrics(newMetrics);
    });

    // Get initial metrics
    setMetrics(performanceMonitor.getMetrics());
  }, []);

  return metrics;
};

// Utility to measure component render time
export const measureComponentPerformance = (componentName: string) => {
  const startMark = `${componentName}-start`;
  const endMark = `${componentName}-end`;
  const measureName = `${componentName}-render`;

  return {
    startMeasure: () => {
      performance.mark(startMark);
    },
    endMeasure: () => {
      performance.mark(endMark);
      performance.measure(measureName, startMark, endMark);
      
      const measures = performance.getEntriesByName(measureName);
      const duration = measures[measures.length - 1]?.duration;
      
      if (duration > 16) { // Longer than one frame (60fps)
        logger.warn(`${componentName} render took ${duration.toFixed(2)}ms`);
      }
      
      // Clean up
      performance.clearMarks(startMark);
      performance.clearMarks(endMark);
      performance.clearMeasures(measureName);
      
      return duration;
    },
  };
};

// Resource timing helper
export const getResourceTimings = () => {
  const resources = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
  
  return resources.map(resource => ({
    name: resource.name,
    type: resource.initiatorType,
    duration: Math.round(resource.duration),
    size: resource.transferSize,
    cached: resource.transferSize === 0 && resource.decodedBodySize > 0,
  }));
};

// Bundle size analyzer
export const analyzeBundleSize = () => {
  const scripts = getResourceTimings().filter(r => r.type === 'script');
  const totalSize = scripts.reduce((sum, script) => sum + (script.size || 0), 0);
  
  return {
    scripts,
    totalSize,
    totalSizeKB: Math.round(totalSize / 1024),
    totalSizeMB: (totalSize / 1024 / 1024).toFixed(2),
  };
};

// Memory usage monitor (Chrome only)
export const getMemoryUsage = () => {
  if ('memory' in performance) {
    const memory = (performance as any).memory;
    return {
      usedJSHeapSize: Math.round(memory.usedJSHeapSize / 1024 / 1024),
      totalJSHeapSize: Math.round(memory.totalJSHeapSize / 1024 / 1024),
      jsHeapSizeLimit: Math.round(memory.jsHeapSizeLimit / 1024 / 1024),
    };
  }
  return null;
};
