import axios from 'axios';
import { AuthResponse, LoginCredentials, RegisterData, User } from '@/types/auth';
import { clearCSRFToken } from '@/utils/csrf';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class AuthServiceV2 {
  private refreshPromise: Promise<void> | null = null;

  constructor() {
    // Security V2 uses httpOnly cookies for tokens
    // No need to restore from localStorage
  }

  getAccessToken(): string | null {
    // In security_v2, access token is stored in httpOnly cookie
    // Not accessible via JavaScript for security
    return localStorage.getItem('access_token');
  }

  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const response = await axios.post<AuthResponse>(
      `${API_URL}/auth/login`,
      {
        email: credentials.email,
        password: credentials.password,
      },
      { 
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    
    // Store the access token for API requests
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    
    // Get user info after successful login
    try {
      const userResponse = await axios.get<User>(
        `${API_URL}/auth/me`,
        {
          withCredentials: true,
          headers: {
            'Authorization': `Bearer ${response.data.access_token}`
          }
        }
      );
      
      return {
        ...response.data,
        user: userResponse.data
      };
    } catch (error) {
      console.error('Failed to fetch user data after login:', error);
      return response.data;
    }
  }

  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await axios.post<AuthResponse>(
      `${API_URL}/auth/register`,
      data,
      { 
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );
    
    // Store the access token
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await axios.post(
        `${API_URL}/auth/logout`,
        {},
        { 
          withCredentials: true,
          headers: {
            'Authorization': `Bearer ${this.getAccessToken()}`
          }
        }
      );
    } finally {
      localStorage.removeItem('access_token');
      clearCSRFToken();
    }
  }

  async getCurrentUser(): Promise<User | null> {
    const token = this.getAccessToken();
    if (!token) {
      return null;
    }

    try {
      const response = await axios.get<User>(
        `${API_URL}/auth/me`,
        {
          withCredentials: true,
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        // Token expired, try to refresh
        await this.refreshToken();
        // Retry the request
        const retryResponse = await axios.get<User>(
          `${API_URL}/auth/me`,
          {
            withCredentials: true,
            headers: {
              'Authorization': `Bearer ${this.getAccessToken()}`
            }
          }
        );
        return retryResponse.data;
      }
      throw error;
    }
  }

  async refreshToken(): Promise<void> {
    // Avoid multiple simultaneous refresh requests
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
      try {
        const response = await axios.post<AuthResponse>(
          `${API_URL}/auth/refresh`,
          {},
          { 
            withCredentials: true,
            headers: {
              'Authorization': `Bearer ${this.getAccessToken()}`
            }
          }
        );
        
        if (response.data.access_token) {
          localStorage.setItem('access_token', response.data.access_token);
        }
      } catch (error) {
        localStorage.removeItem('access_token');
        throw error;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  async verifyEmail(token: string): Promise<void> {
    await axios.post(
      `${API_URL}/auth/verify-email`,
      { token },
      { withCredentials: true }
    );
  }

  async forgotPassword(email: string): Promise<void> {
    await axios.post(
      `${API_URL}/auth/forgot-password`,
      { email },
      { withCredentials: true }
    );
  }

  async resetPassword(token: string, newPassword: string): Promise<void> {
    await axios.post(
      `${API_URL}/auth/reset-password`,
      { token, new_password: newPassword },
      { withCredentials: true }
    );
  }

  async verifyToken(): Promise<boolean> {
    const token = this.getAccessToken();
    if (!token) {
      return false;
    }

    try {
      await axios.post(
        `${API_URL}/auth/verify-token`,
        {},
        {
          withCredentials: true,
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      return true;
    } catch {
      return false;
    }
  }

  isAuthenticated(): boolean {
    return !!this.getAccessToken();
  }

  // Setup axios interceptors for automatic token handling
  setupInterceptors(): void {
    // Request interceptor to add auth header
    axios.interceptors.request.use(
      (config) => {
        const token = this.getAccessToken();
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle token refresh
    axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;
          
          try {
            await this.refreshToken();
            const token = this.getAccessToken();
            if (token) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return axios(originalRequest);
          } catch (refreshError) {
            // Refresh failed, redirect to login
            localStorage.removeItem('access_token');
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }
        
        return Promise.reject(error);
      }
    );
  }
}

const authServiceV2 = new AuthServiceV2();
authServiceV2.setupInterceptors();

export default authServiceV2;