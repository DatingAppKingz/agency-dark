import { setupServer } from 'msw/node';
import { handlers } from './handlers';

// Setup MSW server with default handlers
export const server = setupServer(...handlers);

// Start server before all tests
beforeAll(() => {
  server.listen({
    onUnhandledRequest: 'warn',
  });
});

// Reset handlers after each test
afterEach(() => {
  server.resetHandlers();
});

// Clean up after all tests
afterAll(() => {
  server.close();
});

// Utility to add runtime handlers
export const addHandler = (handler: any) => {
  server.use(handler);
};