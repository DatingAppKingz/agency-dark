import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Wait for element to be removed
export const waitForElementToBeRemoved = async (element: HTMLElement | (() => HTMLElement)) => {
  await waitFor(() => {
    if (typeof element === 'function') {
      expect(element).toThrow();
    } else {
      expect(element).not.toBeInTheDocument();
    }
  });
};

// Wait for loading to complete
export const waitForLoadingToFinish = async () => {
  const loadingElements = screen.queryAllByTestId(/loading|spinner|skeleton/i);
  if (loadingElements.length > 0) {
    await waitFor(() => {
      loadingElements.forEach(element => {
        expect(element).not.toBeInTheDocument();
      });
    });
  }
};

// Fill form helper
export const fillForm = async (formData: Record<string, string | boolean>) => {
  const user = userEvent.setup();
  
  for (const [field, value] of Object.entries(formData)) {
    const element = screen.getByLabelText(new RegExp(field, 'i'));
    
    if (element.getAttribute('type') === 'checkbox') {
      if (value === true) {
        await user.click(element);
      }
    } else {
      await user.clear(element);
      await user.type(element, value.toString());
    }
  }
};

// Submit form helper
export const submitForm = async (buttonText = /submit|save|create/i) => {
  const user = userEvent.setup();
  const submitButton = screen.getByRole('button', { name: buttonText });
  await user.click(submitButton);
};

// Login helper
export const loginUser = async (email = 'test@example.com', password = 'password123') => {
  await fillForm({ email, password });
  await submitForm(/log in|sign in/i);
  await waitForLoadingToFinish();
};

// Assert toast message
export const expectToastMessage = async (message: string | RegExp, type?: 'success' | 'error' | 'info') => {
  const toast = await screen.findByText(message);
  expect(toast).toBeInTheDocument();
  
  if (type) {
    const toastContainer = toast.closest('[role="alert"]');
    expect(toastContainer).toHaveAttribute('data-type', type);
  }
};

// Assert redirect
export const expectRedirect = (expectedPath: string) => {
  expect(window.location.pathname).toBe(expectedPath);
};

// Mock console methods
export const mockConsole = () => {
  const originalConsole = { ...console };
  
  beforeAll(() => {
    console.error = jest.fn();
    console.warn = jest.fn();
    console.log = jest.fn();
  });
  
  afterAll(() => {
    console.error = originalConsole.error;
    console.warn = originalConsole.warn;
    console.log = originalConsole.log;
  });
  
  return {
    expectNoConsoleErrors: () => {
      expect(console.error).not.toHaveBeenCalled();
    },
    expectConsoleError: (message?: string | RegExp) => {
      if (message) {
        expect(console.error).toHaveBeenCalledWith(
          expect.stringMatching(message)
        );
      } else {
        expect(console.error).toHaveBeenCalled();
      }
    },
  };
};

// Mock window methods
export const mockWindow = () => {
  const originalWindow = { ...window };
  
  return {
    mockMatchMedia: () => {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: jest.fn().mockImplementation(query => ({
          matches: false,
          media: query,
          onchange: null,
          addListener: jest.fn(),
          removeListener: jest.fn(),
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
          dispatchEvent: jest.fn(),
        })),
      });
    },
    
    mockLocalStorage: () => {
      const store: Record<string, string> = {};
      
      const mockLocalStorage = {
        getItem: jest.fn((key: string) => store[key] || null),
        setItem: jest.fn((key: string, value: string) => {
          store[key] = value;
        }),
        removeItem: jest.fn((key: string) => {
          delete store[key];
        }),
        clear: jest.fn(() => {
          Object.keys(store).forEach(key => delete store[key]);
        }),
      };
      
      Object.defineProperty(window, 'localStorage', {
        value: mockLocalStorage,
      });
      
      return mockLocalStorage;
    },
    
    restore: () => {
      Object.assign(window, originalWindow);
    },
  };
};

// Accessibility helpers
export const checkAccessibility = async (container: HTMLElement) => {
  const results = await import('jest-axe').then(({ axe }) => axe(container));
  expect(results).toHaveNoViolations();
};

// Debug helper
export const debugScreen = () => {
  screen.debug(undefined, Infinity);
};

// Custom queries
export const getByTestId = (testId: string) => {
  return screen.getByTestId(testId);
};

export const queryByTestId = (testId: string) => {
  return screen.queryByTestId(testId);
};

// Performance helpers
export const measureRenderTime = async (callback: () => void | Promise<void>) => {
  const start = performance.now();
  await callback();
  const end = performance.now();
  return end - start;
};

// Network helpers
export const waitForRequest = async (url: string | RegExp, timeout = 5000) => {
  const start = Date.now();
  
  while (Date.now() - start < timeout) {
    const requests = performance.getEntriesByType('resource') as PerformanceResourceTiming[];
    const found = requests.find(req => 
      typeof url === 'string' ? req.name.includes(url) : url.test(req.name)
    );
    
    if (found) return found;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  
  throw new Error(`Request to ${url} not found within ${timeout}ms`);
};