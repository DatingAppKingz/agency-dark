import { screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';

/**
 * Wait for loading states to finish
 */
export const waitForLoadingToFinish = async () => {
  await waitFor(() => {
    const loadingElements = screen.queryAllByText(/loading/i);
    const spinners = screen.queryAllByRole('progressbar');
    expect(loadingElements.length + spinners.length).toBe(0);
  });
};

/**
 * Login a user for testing
 */
export const loginUser = async (user = { email: 'test@example.com', password: 'password123' }) => {
  const userInstance = userEvent.setup();
  
  // Fill in login form
  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/password/i);
  
  await userInstance.type(emailInput, user.email);
  await userInstance.type(passwordInput, user.password);
  
  // Submit form
  const submitButton = screen.getByRole('button', { name: /login|sign in/i });
  await userInstance.click(submitButton);
  
  // Wait for login to complete
  await waitForLoadingToFinish();
  
  return user;
};

/**
 * Mock successful API response
 */
export const mockApiSuccess = (data: any, delay = 0) => {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ data, status: 200 }), delay);
  });
};

/**
 * Mock API error response
 */
export const mockApiError = (message: string, status = 400, delay = 0) => {
  return new Promise((_, reject) => {
    setTimeout(() => reject({ 
      response: { 
        data: { message }, 
        status 
      } 
    }), delay);
  });
};

/**
 * Get all elements by test ID pattern
 */
export const getAllByTestIdPattern = (pattern: RegExp) => {
  const elements = screen.queryAllByTestId(pattern);
  return elements;
};

/**
 * Wait for element to be removed
 */
export const waitForElementToBeRemoved = async (query: () => HTMLElement | null) => {
  await waitFor(() => {
    expect(query()).not.toBeInTheDocument();
  });
};

/**
 * Mock intersection observer
 */
export const mockIntersectionObserver = () => {
  const mockIntersectionObserver = vi.fn();
  mockIntersectionObserver.mockReturnValue({
    observe: () => null,
    unobserve: () => null,
    disconnect: () => null
  });
  window.IntersectionObserver = mockIntersectionObserver as any;
};

/**
 * Create mock file for upload testing
 */
export const createMockFile = (name: string, size: number, type: string): File => {
  const file = new File(['x'.repeat(size)], name, { type });
  Object.defineProperty(file, 'size', { value: size });
  return file;
};

/**
 * Simulate file drop
 */
export const dropFile = async (element: HTMLElement, file: File) => {
  const dataTransfer = {
    files: [file],
    items: [{
      kind: 'file',
      type: file.type,
      getAsFile: () => file
    }],
    types: ['Files']
  };

  const dropEvent = new Event('drop', { bubbles: true });
  Object.defineProperty(dropEvent, 'dataTransfer', {
    value: dataTransfer
  });

  element.dispatchEvent(dropEvent);
  await waitFor(() => {});
};

/**
 * Get computed styles of an element
 */
export const getComputedStyles = (element: HTMLElement) => {
  return window.getComputedStyle(element);
};

/**
 * Simulate network conditions
 */
export const simulateSlowNetwork = (delay = 2000) => {
  const originalFetch = global.fetch;
  global.fetch = vi.fn((...args) => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(originalFetch(...args));
      }, delay);
    });
  }) as any;
  
  return () => {
    global.fetch = originalFetch;
  };
};

/**
 * Create mock WebSocket
 */
export const createMockWebSocket = () => {
  const mockSocket = {
    send: vi.fn(),
    close: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    readyState: WebSocket.OPEN,
    CONNECTING: 0,
    OPEN: 1,
    CLOSING: 2,
    CLOSED: 3,
  };
  
  return mockSocket;
};

/**
 * Wait for debounced input
 */
export const waitForDebouncedInput = async (ms = 500) => {
  await act(async () => {
    vi.advanceTimersByTime(ms);
  });
  await waitFor(() => {});
};

/**
 * Assert element has focus
 */
export const assertHasFocus = (element: HTMLElement) => {
  expect(document.activeElement).toBe(element);
};

/**
 * Get all console method calls during test
 */
export const captureConsole = () => {
  const originalConsole = { ...console };
  const calls: { method: string; args: any[] }[] = [];
  
  ['log', 'warn', 'error', 'info'].forEach(method => {
    console[method as keyof Console] = vi.fn((...args) => {
      calls.push({ method, args });
    }) as any;
  });
  
  return {
    calls,
    restore: () => {
      Object.assign(console, originalConsole);
    }
  };
};