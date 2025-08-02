import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';

// Set environment variables
process.env.VITE_API_URL = 'http://localhost:8000';
process.env.VITE_WS_URL = 'http://localhost:8000';
process.env.VITE_PUBLIC_VAPID_KEY = 'test-vapid-key';
process.env.NODE_ENV = 'test';

// Mock pushNotifications service before any imports
jest.mock('@/services/pushNotifications', () => ({
  pushNotifications: {
    isSupported: jest.fn().mockReturnValue(true),
    requestPermission: jest.fn().mockResolvedValue(true),
    subscribeUser: jest.fn().mockResolvedValue({
      endpoint: 'https://push.example.com/123',
      keys: { p256dh: 'test-key', auth: 'test-auth' }
    }),
    unsubscribeUser: jest.fn().mockResolvedValue(undefined),
    sendNotification: jest.fn().mockResolvedValue(undefined),
    isSubscribed: jest.fn().mockResolvedValue(false),
    getSubscription: jest.fn().mockResolvedValue(null),
  }
}));

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
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

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
  unobserve() {}
};

// Mock scrollTo
window.scrollTo = jest.fn();

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
  length: 0,
  key: jest.fn(),
};
globalThis.localStorage = localStorageMock as any;

// Mock sessionStorage
globalThis.sessionStorage = localStorageMock as any;
