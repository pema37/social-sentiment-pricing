// frontend/lib/testing/setup.ts

import { afterAll, afterEach, beforeAll } from 'vitest';
import { setupServer } from 'msw/node';
import { handlers } from './msw-handlers';


// Create MSW server with default handlers
export const server = setupServer(...handlers);

// Start server before all tests
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));

// Reset handlers after each test (removes runtime overrides)
afterEach(() => server.resetHandlers());

// Clean up after all tests
afterAll(() => server.close());


