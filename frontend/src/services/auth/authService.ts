import axios from 'axios';
import { AuthResponse, LoginCredentials, RegisterData, User } from '@/types/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class AuthService {
  private accessToken: string | null = null;
  private refreshPromise: Promise<void> | null = null;

  constructor() {
    // Try to restore session on init
    this.checkAuth();
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
      this.accessToken = null;
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
        this.setAccessToken(response.data.access_token);
      })
      .catch((error) => {
        this.accessToken = null;
        throw error;
      })
      .finally(() => {
        this.refreshPromise = null;
      });

    return this.refreshPromise;
  }

  async checkAuth(): Promise<User | null> {
    try {
      // Try to get current user, which will trigger token refresh if needed
      const response = await axios.get<User>(
        `${API_URL}/auth/me`,
        { withCredentials: true }
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

  async resetPassword(token: string, newPassword: string): Promise<void> {
    await axios.post(
      `${API_URL}/auth/password-reset/confirm`,
      { token, new_password: newPassword },
      { withCredentials: true }
    );
  }
}

export const authService = new AuthService();
