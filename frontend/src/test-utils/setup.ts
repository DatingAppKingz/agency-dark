import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';

// Add TextEncoder/TextDecoder polyfills for Node.js environment
if (typeof globalThis.TextEncoder === 'undefined') {
  const { TextEncoder, TextDecoder } = require('util');
  globalThis.TextEncoder = TextEncoder;
  globalThis.TextDecoder = TextDecoder as any;
}

// Mock import.meta for Vite environment variables
(globalThis as any).import = {
  meta: {
    env: {
      VITE_API_URL: 'http://localhost:8000',
      VITE_WS_URL: 'http://localhost:8000',
      MODE: 'test',
      DEV: false,
      PROD: false,
      SSR: false,
    },
  },
};

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
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
  takeRecords() {
    return [];
  }
};

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
