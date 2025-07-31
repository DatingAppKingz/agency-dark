import React, { ReactElement } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n/config';
import { theme } from '@/theme/optimizedTheme';

// Create a new QueryClient for each test
const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

interface AllTheProvidersProps {
  children: React.ReactNode;
}

const AllTheProviders: React.FC<AllTheProvidersProps> = ({ children }) => {
  const queryClient = createTestQueryClient();
  
  return (
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <BrowserRouter>
            {children}
          </BrowserRouter>
        </ThemeProvider>
      </I18nextProvider>
    </QueryClientProvider>
  );
};

const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>,
) => render(ui, { wrapper: AllTheProviders, ...options });

// Re-export everything
export * from '@testing-library/react';
export { customRender as render };

// Test data generators
export const createMockUser = (overrides = {}) => ({
  id: '1',
  email: 'test@example.com',
  name: 'Test User',
  role: 'AGENCY_ADMIN',
  agency_id: 'agency-1',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

export const createMockAgency = (overrides = {}) => ({
  id: 'agency-1',
  name: 'Test Agency',
  domain: 'test.agency.com',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

export const createMockModel = (overrides = {}) => ({
  id: 'model-1',
  name: 'Test Model',
  email: 'model@example.com',
  agency_id: 'agency-1',
  status: 'active',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

export const createMockChat = (overrides = {}) => ({
  id: 'chat-1',
  model_id: 'model-1',
  fan_id: 'fan-1',
  messages: [],
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
});

// Mock API responses
export const mockApiResponses = {
  login: {
    access_token: 'mock-access-token',
    refresh_token: 'mock-refresh-token',
    user: createMockUser(),
  },
  users: {
    data: [createMockUser()],
    total: 1,
    page: 1,
    limit: 10,
  },
  models: {
    data: [createMockModel()],
    total: 1,
    page: 1,
    limit: 10,
  },
};
