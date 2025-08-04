import axios from 'axios';
import { AuthResponse, LoginCredentials, RegisterData, User } from '@/types/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class AuthService {
  private accessToken: string | null = null;
  private refreshPromise: Promise<void> | null = null;

  constructor() {
    // Try to restore session on init
    // Commented out to prevent unnecessary API calls on app load
    // this.checkAuth();
    
    // Restore token from localStorage on init
    const storedToken = localStorage.getItem('auth_token');
    if (storedToken) {
      this.accessToken = storedToken;
    }
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setAccessToken(token: string): void {
    this.accessToken = token;
  }

  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    // Backend expects JSON with email and password
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
    
    this.setAccessToken(response.data.access_token);
    
    // Store tokens in localStorage
    if (response.data.access_token && response.data.refresh_token) {
      this.setTokens(response.data.access_token, response.data.refresh_token);
    }
    
    // Get user info after login
    const userResponse = await axios.get<User>(
      `${API_URL}/auth/me`,
      {
        withCredentials: true,
        headers: {
          Authorization: `Bearer ${response.data.access_token}`,
        },
      }
    );
    
    return {
      ...response.data,
      user: userResponse.data,
    };
  }

  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await axios.post<AuthResponse>(
      `${API_URL}/auth/register`,
      data,
      { withCredentials: true }
    );
    
    this.setAccessToken(response.data.access_token);
    
    // Store tokens in localStorage
    if (response.data.access_token && response.data.refresh_token) {
      this.setTokens(response.data.access_token, response.data.refresh_token);
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
            Authorization: `Bearer ${this.accessToken}`
          }
        }
      );
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      this.clearTokens();
    }
  }

  async refreshToken(): Promise<void> {
    // Prevent multiple simultaneous refresh requests
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = axios
      .post<AuthResponse>(
        `${API_URL}/auth/refresh`,
        {},
        { withCredentials: true }
      )
      .then((response) => {
        // Use setTokens to handle both tokens properly
        if (response.data.refresh_token) {
          this.setTokens(response.data.access_token, response.data.refresh_token);
        } else {
          this.setAccessToken(response.data.access_token);
          localStorage.setItem('auth_token', response.data.access_token);
        }
        return response.data;
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

  async checkAuth(): Promise<User | null> {
    try {
      // Check for token in memory or localStorage
      const token = this.accessToken || localStorage.getItem('auth_token');
      if (!token) {
        return null;
      }
      
      // Try to get current user with the token
      const response = await axios.get<User>(
        `${API_URL}/auth/me`,
        { 
          withCredentials: true,
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      );
      return response.data;
    } catch (error) {
      return null;
    }
  }

  async forgotPassword(email: string): Promise<void> {
    await axios.post(
      `${API_URL}/auth/password-reset/request`,
      { email },
      { withCredentials: true }
    );
  }

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const response = await axios.post<{ message: string }>(
      `${API_URL}/auth/password-reset/confirm`,
      { token, new_password: newPassword },
      { withCredentials: true }
    );
    return response.data;
  }

  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }

  isAuthenticated(): boolean {
    return !!this.accessToken || !!localStorage.getItem('auth_token');
  }

  setTokens(accessToken: string, refreshToken: string): void {
    this.accessToken = accessToken;
    localStorage.setItem('auth_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
  }

  clearTokens(): void {
    this.accessToken = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  }

  async requestPasswordReset(email: string): Promise<{ message: string }> {
    const response = await axios.post<{ message: string }>(
      `${API_URL}/auth/forgot-password`,
      { email },
      { withCredentials: true }
    );
    return response.data;
  }

  async getCurrentUser(): Promise<User | null> {
    return this.checkAuth();
  }
}

export const authService = new AuthService();
