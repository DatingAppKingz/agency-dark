import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { vi } from 'vitest';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { LanguageProvider } from '@/i18n/LanguageProvider';
import { PushNotificationProvider } from '@/providers/PushNotificationProvider';
import { Toaster } from '@/components/common/Toaster';
import theme from '@/theme';
import '@/i18n';

// Create a test query client
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: false,
      },
    },
    logger: {
      log: console.log,
      warn: console.warn,
      error: () => {}, // Suppress error logs in tests
    },
  });

interface AllTheProvidersProps {
  children: React.ReactNode;
  initialEntries?: string[];
  initialIndex?: number;
}

const AllTheProviders: React.FC<AllTheProvidersProps> = ({ 
  children, 
  initialEntries = ['/'],
  initialIndex = 0,
}) => {
  const testQueryClient = createTestQueryClient();
  
  return (
    <HelmetProvider>
      <QueryClientProvider client={testQueryClient}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <MemoryRouter initialEntries={initialEntries} initialIndex={initialIndex}>
            <LanguageProvider>
              <PushNotificationProvider>
                {children}
                <Toaster />
              </PushNotificationProvider>
            </LanguageProvider>
          </MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </HelmetProvider>
  );
};

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: string[];
  initialIndex?: number;
  route?: string;
  path?: string;
}

// Custom render function
export const customRender = (
  ui: ReactElement,
  {
    initialEntries = ['/'],
    initialIndex = 0,
    route,
    path,
    ...options
  }: CustomRenderOptions = {}
) => {
  // If route and path are provided, wrap the UI in a Routes component
  const wrappedUi = route && path ? (
    <Routes>
      <Route path={path} element={ui} />
    </Routes>
  ) : ui;

  // Update initialEntries if route is provided
  const entries = route ? [route] : initialEntries;

  return render(wrappedUi, {
    wrapper: ({ children }) => (
      <AllTheProviders initialEntries={entries} initialIndex={initialIndex}>
        {children}
      </AllTheProviders>
    ),
    ...options,
  });
};

// Render with specific user role
export const renderWithAuth = (
  ui: ReactElement,
  {
    user = {
      id: '1',
      email: 'test@example.com',
      full_name: 'Test User',
      role: 'model',
      is_active: true,
      is_verified: true,
      agency_id: 'agency-1',
      created_at: new Date().toISOString(),
    },
    ...options
  }: CustomRenderOptions & { user?: any } = {}
) => {
  // Set auth token in localStorage
  localStorage.setItem('auth_token', 'mock-token');
  localStorage.setItem('user', JSON.stringify(user));
  
  return customRender(ui, options);
};

// Render within a specific route
export const renderWithRouter = (
  ui: ReactElement,
  {
    route = '/',
    path = '*',
    ...options
  }: CustomRenderOptions = {}
) => {
  return customRender(ui, {
    ...options,
    route,
    path,
  });
};

// Re-export everything from testing library
export * from '@testing-library/react';
export { customRender as render };

// Export additional utilities
export { default as userEvent } from '@testing-library/user-event';
export { createTestQueryClient };

// Helper to wait for async operations
export const waitForAsync = () => new Promise(resolve => setTimeout(resolve, 0));

// Helper to mock fetch
export const mockFetch = (response: any) => {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(response),
    } as Response)
  );
  return global.fetch as vi.Mock;
};

// Helper to create a wrapper with custom providers
export const createWrapper = (props?: Partial<AllTheProvidersProps>) => {
  return ({ children }: { children: React.ReactNode }) => (
    <AllTheProviders {...props}>{children}</AllTheProviders>
  );
};