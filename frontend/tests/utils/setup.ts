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

// Mock authService - needs to be before other mocks
vi.mock('@/services/auth/authService', () => ({
  authService: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    checkAuth: vi.fn(),
    refreshToken: vi.fn(),
    getAccessToken: vi.fn(),
    getRefreshToken: vi.fn(),
    isAuthenticated: vi.fn(),
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
    requestPasswordReset: vi.fn(),
    resetPassword: vi.fn(),
    getCurrentUser: vi.fn(),
  }
}));

// Mock pushNotifications service
vi.mock('@/services/pushNotifications', () => ({
  pushNotifications: {
    init: vi.fn().mockResolvedValue(true),
    isSupported: vi.fn().mockReturnValue(true),
    getPermissionStatus: vi.fn().mockReturnValue('default'),
    requestPermission: vi.fn().mockResolvedValue(true),
    subscribeUser: vi.fn().mockResolvedValue({
      endpoint: 'https://push.example.com/123',
      keys: { p256dh: 'test-key', auth: 'test-auth' }
    }),
    unsubscribeUser: vi.fn().mockResolvedValue(undefined),
    sendNotification: vi.fn().mockResolvedValue(undefined),
    isSubscribed: vi.fn().mockReturnValue(false),
    getSubscription: vi.fn().mockResolvedValue(null),
  }
}));

// Import MUI icon mocks
import mockIcons from './mui-icon-mocks';

// Mock all @mui/icons-material imports
vi.mock('@mui/icons-material', () => mockIcons);

// Mock LanguageProvider to avoid loading translations in tests
vi.mock('@/i18n/LanguageProvider', () => ({
  LanguageProvider: ({ children }: { children: React.ReactNode }) => {
    const React = require('react');
    return React.createElement(React.Fragment, null, children);
  },
}));

import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';

// Set environment variables
process.env.VITE_API_URL = 'http://localhost:8000/api/v1';
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
      VITE_API_URL: 'http://localhost:8000/api/v1',
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

// Mock pointer capture methods
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = vi.fn(() => false);
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = vi.fn();
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = vi.fn();
}

// Mock scrollIntoView
Element.prototype.scrollIntoView = vi.fn();

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value.toString();
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index: number) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    }),
  };
})();
globalThis.localStorage = localStorageMock as any;

// Mock sessionStorage (separate instance)
const sessionStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value.toString();
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    get length() {
      return Object.keys(store).length;
    },
    key: vi.fn((index: number) => {
      const keys = Object.keys(store);
      return keys[index] || null;
    }),
  };
})();
globalThis.sessionStorage = sessionStorageMock as any;