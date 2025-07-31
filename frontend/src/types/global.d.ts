/// <reference types="vite/client" />

// Node.js globals for test environment
declare global {
  var TextEncoder: typeof TextEncoder;
  var TextDecoder: typeof TextDecoder;
  var ResizeObserver: typeof ResizeObserver;
  var MutationObserver: typeof MutationObserver;
  var IntersectionObserver: typeof IntersectionObserver;
  
  namespace NodeJS {
    interface Timeout {
      ref(): this;
      unref(): this;
      refresh(): this;
      [Symbol.toPrimitive](): number;
    }
  }
}

// Notification API extension
interface NotificationOptions {
  vibrate?: number | number[];
}

// Module declarations
declare module 'util' {
  export const TextEncoder: typeof global.TextEncoder;
  export const TextDecoder: typeof global.TextDecoder;
}

declare module 'react-beautiful-dnd' {
  export * from '@types/react-beautiful-dnd';
}

// Environment variables
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_WS_URL: string;
  readonly VITE_APP_NAME: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Process global for environment checks
declare global {
  interface Window {
    process?: {
      env: {
        NODE_ENV?: string;
      };
    };
  }
}

// For compatibility
declare const process: {
  env: {
    NODE_ENV?: string;
  };
};

export {};
