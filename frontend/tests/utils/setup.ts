import { vi } from 'vitest';

// Mock axios before any imports
vi.mock('axios', () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    post: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    put: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    patch: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    delete: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    request: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() }
    }
  };
  return {
    default: mockAxios,
    ...mockAxios
  };
});

// Mock API client
vi.mock('@/services/api/client', () => ({
  default: {
    get: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    post: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    put: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    patch: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    delete: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    request: vi.fn().mockRejectedValue(new Error('API calls should be mocked in tests')),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() }
    }
  }
}));

// Mock pushNotifications service
vi.mock('@/services/pushNotifications', () => ({
  pushNotifications: {
    isSupported: vi.fn().mockReturnValue(true),
    requestPermission: vi.fn().mockResolvedValue(true),
    subscribeUser: vi.fn().mockResolvedValue({
      endpoint: 'https://push.example.com/123',
      keys: { p256dh: 'test-key', auth: 'test-auth' }
    }),
    unsubscribeUser: vi.fn().mockResolvedValue(undefined),
    sendNotification: vi.fn().mockResolvedValue(undefined),
    isSubscribed: vi.fn().mockResolvedValue(false),
    getSubscription: vi.fn().mockResolvedValue(null),
  }
}));

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';

// Set environment variables
process.env.VITE_API_URL = 'http://localhost:8000';
process.env.VITE_WS_URL = 'http://localhost:8000';
process.env.VITE_PUBLIC_VAPID_KEY = 'test-vapid-key';
process.env.NODE_ENV = 'test';

// Add TextEncoder/TextDecoder polyfills for Node.js environment
if (typeof globalThis.TextEncoder === 'undefined') {
  const util = require('util');
  globalThis.TextEncoder = util.TextEncoder;
  globalThis.TextDecoder = util.TextDecoder as any;
}

// Mock import.meta for Vite environment variables
(globalThis as any).import = {
  meta: {
    env: {
      VITE_API_URL: 'http://localhost:8000',
      VITE_WS_URL: 'http://localhost:8000',
      VITE_PUBLIC_VAPID_KEY: 'test-vapid-key',
      MODE: 'test',
      DEV: false,
      PROD: false,
      SSR: false,
    },
  },
};

// Mock Response if not available
if (typeof globalThis.Response === 'undefined') {
  (globalThis as any).Response = class Response {
    constructor(public body: any, public init: any = {}) {}
  };
}

// Cleanup after each test
afterEach(() => {
  cleanup();
});

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock BroadcastChannel for MSW
globalThis.BroadcastChannel = class BroadcastChannel {
  constructor(public name: string) {}
  postMessage(message: any) {}
  close() {}
  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
} as any;

// Mock IntersectionObserver
globalThis.IntersectionObserver = class IntersectionObserver {
  root = null;
  rootMargin = '';
  thresholds = [];
  
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
  takeRecords() {
    return [];
  }
} as any;

// Mock ResizeObserver
globalThis.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {};
};

// Mock scrollTo
window.scrollTo = vi.fn();

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
  length: 0,
  key: vi.fn(),
};
globalThis.localStorage = localStorageMock as any;

// Mock sessionStorage
globalThis.sessionStorage = localStorageMock as any;