/**
 * CSRF (Cross-Site Request Forgery) protection utilities.
 * 
 * This module handles CSRF token management for secure API requests.
 */

import axios from 'axios';

const CSRF_COOKIE_NAME = '__Secure-CSRF-Token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';

class CSRFManager {
  private csrfToken: string | null = null;

  /**
   * Get CSRF token from cookie.
   * Note: This only works if the cookie is not httpOnly.
   */
  private getCSRFTokenFromCookie(): string | null {
    const cookies = document.cookie.split(';');
    for (const cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === CSRF_COOKIE_NAME) {
        return decodeURIComponent(value);
      }
    }
    return null;
  }

  /**
   * Get current CSRF token, fetching a new one if needed.
   */
  async getCSRFToken(): Promise<string | null> {
    // First try to get from memory
    if (this.csrfToken) {
      return this.csrfToken;
    }

    // Then try to get from cookie
    const cookieToken = this.getCSRFTokenFromCookie();
    if (cookieToken) {
      this.csrfToken = cookieToken;
      return cookieToken;
    }

    // If no token, fetch a new one
    try {
      const response = await axios.get('/api/v1/auth/csrf-token', {
        withCredentials: true
      });
      
      if (response.data.csrf_token) {
        this.csrfToken = response.data.csrf_token;
        return this.csrfToken;
      }
    } catch (error) {
      console.error('Failed to fetch CSRF token:', error);
    }

    return null;
  }

  /**
   * Clear stored CSRF token (call on logout).
   */
  clearCSRFToken(): void {
    this.csrfToken = null;
  }

  /**
   * Add CSRF token to request headers.
   */
  async addCSRFHeader(headers: Record<string, string>): Promise<Record<string, string>> {
    const token = await this.getCSRFToken();
    if (token) {
      headers[CSRF_HEADER_NAME] = token;
    }
    return headers;
  }

  /**
   * Configure axios to automatically include CSRF token.
   */
  setupAxiosInterceptor(): void {
    axios.interceptors.request.use(
      async (config) => {
        // Only add CSRF token for state-changing methods
        const needsCSRF = ['post', 'put', 'patch', 'delete'].includes(
          config.method?.toLowerCase() || ''
        );

        if (needsCSRF && config.headers) {
          const token = await this.getCSRFToken();
          if (token) {
            config.headers[CSRF_HEADER_NAME] = token;
          }
        }

        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );
  }
}

// Export singleton instance
export const csrfManager = new CSRFManager();

// Export convenience functions
export const getCSRFToken = () => csrfManager.getCSRFToken();
export const clearCSRFToken = () => csrfManager.clearCSRFToken();
export const addCSRFHeader = (headers: Record<string, string>) => 
  csrfManager.addCSRFHeader(headers);