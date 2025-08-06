/**
 * Auth Service V2 - Compatible with security_v2 backend
 * This service works with the new security implementation
 */
import axios from 'axios';
import { AuthResponse, LoginCredentials, RegisterData, User } from '@/types/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
}

interface CurrentUser {
  user_id: number;
  email: string;
  role: string;
  agency_id?: number | null;
}

class AuthServiceV2 {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<void> | null = null;

  constructor() {
    // Restore tokens from localStorage if available
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  private setTokens(access: string, refresh?: string) {
    this.accessToken = access;
    localStorage.setItem('access_token', access);
    
    if (refresh) {
      this.refreshToken = refresh;
      localStorage.setItem('refresh_token', refresh);
    }
  }

  private clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      // Call the new backend login endpoint
      const response = await axios.post<TokenResponse>(
        `${API_URL}/auth/login`,
        {
          email: credentials.email,
          password: credentials.password,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
      
      // Store tokens
      this.setTokens(response.data.access_token, response.data.refresh_token);
      
      // Get user info using the token
      const userInfo = await this.getCurrentUser();
      
      // Return in the expected format
      return {
        access_token: response.data.access_token,
        token_type: response.data.token_type,
        user: userInfo || this.createMockUser(credentials.email),
      };
    } catch (error: any) {
      // If new endpoint fails, try the fallback endpoint
      if (error.response?.status === 404 || error.response?.status === 500) {
        console.log('Trying fallback login endpoint...');
        return this.loginFallback(credentials);
      }
      throw error;
    }
  }

  private async loginFallback(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await axios.post<TokenResponse>(
      `${API_URL}/auth/login-fix`,
      {
        email: credentials.email,
        password: credentials.password,
      },
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    
    // Store tokens
    this.setTokens(response.data.access_token, response.data.refresh_token);
    
    // Return with mock user for now
    return {
      access_token: response.data.access_token,
      token_type: response.data.token_type,
      user: this.createMockUser(credentials.email),
    };
  }

  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await axios.post<TokenResponse>(
      `${API_URL}/auth/register`,
      data,
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    
    // Store tokens if provided
    if (response.data.access_token) {
      this.setTokens(response.data.access_token, response.data.refresh_token);
    }
    
    // Return with mock user for now
    return {
      ...response.data,
      user: this.createMockUser(data.email),
    };
  }

  async logout(): Promise<void> {
    try {
      // Call logout endpoint if token exists
      if (this.accessToken) {
        await axios.post(
          `${API_URL}/auth/logout`,
          {},
          {
            headers: {
              'Authorization': `Bearer ${this.accessToken}`,
            },
          }
        );
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Always clear tokens
      this.clearTokens();
    }
  }

  async refreshAccessToken(): Promise<void> {
    // Prevent multiple simultaneous refresh requests
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    this.refreshPromise = axios
      .post<TokenResponse>(
        `${API_URL}/auth/refresh`,
        {
          refresh_token: this.refreshToken,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      .then((response) => {
        this.setTokens(response.data.access_token, response.data.refresh_token);
      })
      .catch((error) => {
        this.clearTokens();
        throw error;
      })
      .finally(() => {
        this.refreshPromise = null;
      });

    return this.refreshPromise;
  }

  async getCurrentUser(): Promise<User | null> {
    if (!this.accessToken) {
      return null;
    }

    try {
      const response = await axios.get<CurrentUser>(
        `${API_URL}/auth/me`,
        {
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
          },
        }
      );
      
      // Map the response to User type
      return {
        id: String(response.data.user_id),
        email: response.data.email,
        role: response.data.role,
        agency_id: response.data.agency_id || null,
        // Mock additional fields for now
        full_name: response.data.email.split('@')[0],
        first_name: response.data.email.split('@')[0],
        last_name: '',
        is_active: true,
        is_verified: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
    } catch (error: any) {
      if (error.response?.status === 401) {
        // Token expired or invalid
        this.clearTokens();
        return null;
      }
      // For other errors, return null
      console.error('Error getting current user:', error);
      return null;
    }
  }

  async checkAuth(): Promise<User | null> {
    // First check if we have a token
    if (!this.accessToken) {
      return null;
    }

    // Try to get current user
    return this.getCurrentUser();
  }

  private createMockUser(email: string): User {
    return {
      id: 'mock-' + Date.now(),
      email: email,
      full_name: email.split('@')[0],
      first_name: email.split('@')[0],
      last_name: '',
      role: email === 'admin@agency.com' ? 'super_admin' : 'viewer',
      is_active: true,
      is_verified: true,
      agency_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }

  // Setup axios interceptor for automatic token injection
  setupInterceptors() {
    // Request interceptor to add token
    axios.interceptors.request.use(
      (config) => {
        if (this.accessToken && !config.headers['Authorization']) {
          config.headers['Authorization'] = `Bearer ${this.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle 401 and refresh token
    axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await this.refreshAccessToken();
            // Retry original request with new token
            originalRequest.headers['Authorization'] = `Bearer ${this.accessToken}`;
            return axios(originalRequest);
          } catch (refreshError) {
            // Refresh failed, redirect to login
            this.clearTokens();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }
}

// Create and export singleton instance
const authServiceV2 = new AuthServiceV2();

// Setup interceptors immediately
authServiceV2.setupInterceptors();

export default authServiceV2;