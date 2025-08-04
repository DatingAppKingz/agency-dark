import { test, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';

test.describe('Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Clear cookies and local storage before each test
    await page.context().clearCookies();
    await page.evaluate(() => localStorage.clear());
  });

  test('should login successfully with valid credentials', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const dashboardPage = new DashboardPage(page);

    await loginPage.goto();
    await loginPage.login('admin@agency.com', 'admin123');

    // Should redirect to dashboard
    await expect(page).toHaveURL(/.*dashboard/);
    await dashboardPage.waitForDashboardLoad();
    
    // Should show welcome message
    await expect(dashboardPage.welcomeMessage).toBeVisible();
  });

  test('should show error with invalid credentials', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.login('invalid@email.com', 'wrongpassword');

    // Should show error message
    const errorMessage = await loginPage.waitForErrorMessage();
    expect(errorMessage).toContain('Invalid email or password');
    
    // Should stay on login page
    await expect(page).toHaveURL(/.*login/);
  });

  test('should show validation errors for empty fields', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    
    // Try to submit empty form
    await loginPage.loginButton.click();

    // Should show validation errors
    await expect(page.getByText('Email is required')).toBeVisible();
    await expect(page.getByText('Password is required')).toBeVisible();
  });

  test('should logout successfully', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const dashboardPage = new DashboardPage(page);

    // First login
    await loginPage.goto();
    await loginPage.login('admin@agency.com', 'admin123');
    await dashboardPage.waitForDashboardLoad();

    // Then logout
    await dashboardPage.logout();

    // Should redirect to login page
    await expect(page).toHaveURL(/.*login/);
    
    // Should not be able to access dashboard
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/.*login/);
  });

  test('should persist login across page refresh', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const dashboardPage = new DashboardPage(page);

    await loginPage.goto();
    await loginPage.login('admin@agency.com', 'admin123');
    await dashboardPage.waitForDashboardLoad();

    // Refresh the page
    await page.reload();

    // Should still be on dashboard
    await expect(page).toHaveURL(/.*dashboard/);
    await expect(dashboardPage.welcomeMessage).toBeVisible();
  });

  test('should redirect to login when accessing protected routes', async ({ page }) => {
    // Try to access protected routes without authentication
    const protectedRoutes = ['/dashboard', '/models', '/financials', '/chat'];

    for (const route of protectedRoutes) {
      await page.goto(route);
      await expect(page).toHaveURL(/.*login/);
    }
  });

  test('should handle forgot password flow', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.forgotPasswordLink.click();

    // Should navigate to forgot password page
    await expect(page).toHaveURL(/.*forgot-password/);
    
    // Fill in email
    const emailInput = page.getByPlaceholder('Enter your email');
    await emailInput.fill('admin@agency.com');
    
    const submitButton = page.getByRole('button', { name: /reset password/i });
    await submitButton.click();

    // Should show success message
    await expect(page.getByText(/reset link sent/i)).toBeVisible();
  });

  test('should handle registration flow', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    await loginPage.registerLink.click();

    // Should navigate to registration page
    await expect(page).toHaveURL(/.*register/);

    // Fill registration form
    await page.getByLabel('Email').fill('newuser@agency.com');
    await page.getByLabel('Password', { exact: true }).fill('SecurePass123!');
    await page.getByLabel('Confirm Password').fill('SecurePass123!');
    await page.getByLabel('Agency Name').fill('Test Agency');
    
    // Accept terms
    const termsCheckbox = page.getByRole('checkbox', { name: /terms/i });
    await termsCheckbox.check();

    // Submit form
    const registerButton = page.getByRole('button', { name: /create account/i });
    await registerButton.click();

    // Should redirect to dashboard or show success
    await expect(page).toHaveURL(/(dashboard|verify-email)/);
  });

  test('should handle session timeout', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const dashboardPage = new DashboardPage(page);

    await loginPage.goto();
    await loginPage.login('admin@agency.com', 'admin123');
    await dashboardPage.waitForDashboardLoad();

    // Simulate session expiry by clearing auth cookie
    await page.context().clearCookies();

    // Try to navigate to another protected page
    await page.goto('/models');

    // Should redirect to login
    await expect(page).toHaveURL(/.*login/);
    
    // Should show session expired message
    await expect(page.getByText(/session expired/i)).toBeVisible();
  });

  test('should handle CSRF protection', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.goto();
    
    // Remove CSRF token to simulate CSRF attack
    await page.evaluate(() => {
      // Remove CSRF token from meta tag or cookie
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      if (csrfMeta) csrfMeta.remove();
    });

    await loginPage.login('admin@agency.com', 'admin123');

    // Should show CSRF error
    await expect(page.getByText(/csrf|security/i)).toBeVisible();
  });
});