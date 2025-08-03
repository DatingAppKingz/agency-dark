import axios from 'axios';
import { AuthResponse, LoginCredentials, User } from '@/types/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class AuthServiceMinimal {
  private accessToken: string | null = null;

  constructor() {
    // Try to restore session from localStorage
    const token = localStorage.getItem('access_token');
    if (token) {
      this.accessToken = token;
    }
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  setAccessToken(token: string): void {
    this.accessToken = token;
    localStorage.setItem('access_token', token);
  }

  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      // Use the minimal login endpoint
      const response = await axios.post(
        `${API_URL}/auth/login-minimal`,
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
      
      // The minimal endpoint returns user data directly
      const { access_token, user } = response.data;
      
      this.setAccessToken(access_token);
      
      // Return in the expected format
      return {
        access_token,
        token_type: 'bearer',
        user,
      };
    } catch (error: any) {
      console.error('Login error:', error);
      throw error;
    }
  }

  async getCurrentUser(): Promise<User> {
    if (!this.accessToken) {
      throw new Error('No access token');
    }

    try {
      const response = await axios.get(
        `${API_URL}/auth/me-minimal`,
        {
          headers: {
            Authorization: `Bearer ${this.accessToken}`,
          },
        }
      );
      
      return response.data;
    } catch (error) {
      console.error('Get current user error:', error);
      throw error;
    }
  }

  async logout(): Promise<void> {
    this.accessToken = null;
    localStorage.removeItem('access_token');
    // Clear any other stored data
    localStorage.removeItem('user');
  }

  async checkAuth(): Promise<User | null> {
    if (!this.accessToken) {
      return null;
    }

    try {
      const user = await this.getCurrentUser();
      return user;
    } catch (error) {
      // Token might be expired
      this.logout();
      return null;
    }
  }
}

export const authServiceMinimal = new AuthServiceMinimal();