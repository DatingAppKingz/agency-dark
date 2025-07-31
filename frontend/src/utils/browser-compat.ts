// Browser compatibility checks and polyfills
import { logger } from './logger';

export const browserCompat = {
  // Check if browser supports required features
  checkSupport(): { supported: boolean; missing: string[] } {
    const missing: string[] = [];
    
    // Check for required APIs
    if (!window.fetch) missing.push('Fetch API');
    if (!window.Promise) missing.push('Promise');
    if (!window.Symbol) missing.push('Symbol');
    if (!window.Map) missing.push('Map');
    if (!window.Set) missing.push('Set');
    if (!window.IntersectionObserver) missing.push('IntersectionObserver');
    if (!window.ResizeObserver) missing.push('ResizeObserver');
    if (!window.requestAnimationFrame) missing.push('requestAnimationFrame');
    if (!window.localStorage) missing.push('localStorage');
    if (!window.sessionStorage) missing.push('sessionStorage');
    
    // Check for CSS features
    if (!CSS.supports('display', 'grid')) missing.push('CSS Grid');
    if (!CSS.supports('display', 'flex')) missing.push('Flexbox');
    if (!CSS.supports('position', 'sticky')) missing.push('Position Sticky');
    
    return {
      supported: missing.length === 0,
      missing,
    };
  },

  // Get browser info
  getBrowserInfo(): {
    name: string;
    version: string;
    engine: string;
    os: string;
  } {
    const ua = navigator.userAgent;
    let name = 'Unknown';
    let version = 'Unknown';
    let engine = 'Unknown';
    
    // Detect browser
    if (ua.includes('Firefox/')) {
      name = 'Firefox';
      version = ua.match(/Firefox\/(\d+\.?\d*)/)?.[1] || 'Unknown';
      engine = 'Gecko';
    } else if (ua.includes('Chrome/')) {
      if (ua.includes('Edg/')) {
        name = 'Edge';
        version = ua.match(/Edg\/(\d+\.?\d*)/)?.[1] || 'Unknown';
      } else {
        name = 'Chrome';
        version = ua.match(/Chrome\/(\d+\.?\d*)/)?.[1] || 'Unknown';
      }
      engine = 'Blink';
    } else if (ua.includes('Safari/') && !ua.includes('Chrome')) {
      name = 'Safari';
      version = ua.match(/Version\/(\d+\.?\d*)/)?.[1] || 'Unknown';
      engine = 'WebKit';
    }
    
    // Detect OS
    let os = 'Unknown';
    if (ua.includes('Windows')) os = 'Windows';
    else if (ua.includes('Mac')) os = 'macOS';
    else if (ua.includes('Linux')) os = 'Linux';
    else if (ua.includes('Android')) os = 'Android';
    else if (ua.includes('iOS')) os = 'iOS';
    
    return { name, version, engine, os };
  },

  // Check for specific feature support
  supports: {
    webp: (): Promise<boolean> => {
      return new Promise((resolve) => {
        const webP = new Image();
        webP.onload = webP.onerror = () => {
          resolve(webP.height === 2);
        };
        webP.src = 'data:image/webp;base64,UklGRjoAAABXRUJQVlA4IC4AAACyAgCdASoCAAIALmk0mk0iIiIiIgBoSygABc6WWgAA/veff/0PP8bA//LwYAAA';
      });
    },
    
    avif: (): Promise<boolean> => {
      return new Promise((resolve) => {
        const avif = new Image();
        avif.onload = avif.onerror = () => {
          resolve(avif.height === 2);
        };
        avif.src = 'data:image/avif;base64,AAAAIGZ0eXBhdmlmAAAAAGF2aWZtaWYxbWlhZk1BMUIAAADybWV0YQAAAAAAAAAoaGRscgAAAAAAAAAAcGljdAAAAAAAAAAAAAAAAGxpYmF2aWYAAAAADnBpdG0AAAAAAAEAAAAeaWxvYwAAAABEAAABAAEAAAABAAABGgAAABcAAAAoaWluZgAAAAAAAQAAABppbmZlAgAAAAABAABhdjAxQ29sb3IAAAAAamlwcnAAAABLaXBjbwAAABRpc3BlAAAAAAAAAAIAAAACAAAAEHBpeGkAAAAAAwgICAAAAAxhdjFDgQAMAAAAABNjb2xybmNseAACAAIABoAAAAAXaXBtYQAAAAAAAAABAAEEAQKDBAAAAB9tZGF0EgAKCBgABogQEDQgMgkQAAAAB8dSLfI=';
      });
    },
    
    serviceWorker: 'serviceWorker' in navigator,
    pushNotifications: 'PushManager' in window,
    webGL: (() => {
      try {
        const canvas = document.createElement('canvas');
        return !!(window.WebGLRenderingContext && 
          (canvas.getContext('webgl') || canvas.getContext('experimental-webgl')));
      } catch (e) {
        return false;
      }
    })(),
    
    touchEvents: 'ontouchstart' in window || navigator.maxTouchPoints > 0,
    
    mediaRecorder: 'MediaRecorder' in window,
    
    clipboard: 'clipboard' in navigator,
  },

  // Apply polyfills
  applyPolyfills(): void {
    // ResizeObserver polyfill
    if (!window.ResizeObserver) {
      logger.warn('ResizeObserver not supported, functionality may be limited');
    }
    
    // IntersectionObserver polyfill
    if (!window.IntersectionObserver) {
      logger.warn('IntersectionObserver not supported, lazy loading disabled');
    }
    
    // Smooth scroll polyfill
    if (!('scrollBehavior' in document.documentElement.style)) {
      // Simple smooth scroll polyfill
      const originalScrollTo = window.scrollTo;
      window.scrollTo = function(options: ScrollToOptions | number, y?: number) {
        if (typeof options === 'object' && options.behavior === 'smooth') {
          const start = window.pageYOffset;
          const distance = (options.top || 0) - start;
          const duration = 500;
          let start_time: number | null = null;
          
          const animation = (current_time: number) => {
            if (start_time === null) start_time = current_time;
            const elapsed = current_time - start_time;
            const progress = Math.min(elapsed / duration, 1);
            
            window.scroll(0, start + distance * progress);
            
            if (progress < 1) {
              requestAnimationFrame(animation);
            }
          };
          
          requestAnimationFrame(animation);
        } else if (typeof options === 'number') {
          originalScrollTo.call(window, options, y);
        } else {
          originalScrollTo.call(window, options);
        }
      };
    }
  },
};
