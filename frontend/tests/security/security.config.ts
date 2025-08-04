import { PlaywrightTestConfig } from '@playwright/test';

const config: PlaywrightTestConfig = {
  testDir: './',
  timeout: 60 * 1000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // Disable headless for security tests to see what's happening
    headless: process.env.CI ? true : false,
  },
  projects: [
    {
      name: 'security',
      use: {
        ...({} as any),
        // Custom context options for security testing
        contextOptions: {
          ignoreHTTPSErrors: false,
          // Strict cookie policies
          acceptDownloads: false,
          // Record HAR for analysis
          recordHar: {
            path: './test-results/security.har',
            mode: 'full',
          },
        },
      },
    },
  ],
  reporter: [
    ['html', { outputFolder: 'security-report' }],
    ['json', { outputFile: 'test-results/security-results.json' }],
  ],
};

export default config;