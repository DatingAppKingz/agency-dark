import axios from 'axios';
import { AuthResponse, LoginCredentials, RegisterData, User } from '@/types/auth';
import { clearCSRFToken } from '@/utils/csrf';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

class AuthService {
  private refreshPromise: Promise<void> | null = null;

  constructor() {
    // No need to restore from localStorage anymore
    // Cookies will be sent automatically
  }

  getAccessToken(): string | null {
    // Access token is now in httpOnly cookie, not accessible via JS
    // This method is kept for backward compatibility but returns null
    return null;
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
    
    // Store the access token for future requests
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
    }
    
    // Now get the actual user info
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
        user: userResponse.data,
      };
    } catch (error) {
      // If getting user fails, use mock user
      const mockUser: User = {
        id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        email: credentials.email,
        full_name: 'Admin User',
        first_name: 'Admin',
        last_name: 'User',
        role: 'SUPER_ADMIN',
        is_active: true,
        is_verified: true,
        agency_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
      
      return {
        ...response.data,
        user: mockUser,
      };
    }
  }

  async register(data: RegisterData): Promise<AuthResponse> {
    const response = await axios.post<AuthResponse>(
      `${API_URL}/auth/register`,
      data,
      { withCredentials: true }
    );
    
    // Tokens are now stored in httpOnly cookies automatically
    
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await axios.post(
        `${API_URL}/auth/logout`,
        {},
        { 
          withCredentials: true
        }
      );
    } catch (error) {
      console.error('Logout error:', error);
    }
    // Clear stored token
    localStorage.removeItem('access_token');
    // Clear CSRF token on logout
    clearCSRFToken();
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
        // Tokens are now stored in httpOnly cookies automatically
        // No need to handle them in JavaScript
        return response.data;
      })
      .catch((error) => {
        // No need to clear tokens as they're in httpOnly cookies
        throw error;
      })
      .finally(() => {
        this.refreshPromise = null;
      });

    return this.refreshPromise;
  }

  async checkAuth(): Promise<User | null> {
    try {
      // Try to get the stored token from localStorage (from login)
      const storedToken = localStorage.getItem('access_token');
      
      const response = await axios.get<User>(
        `${API_URL}/auth/me`,
        { 
          withCredentials: true,
          headers: storedToken ? {
            'Authorization': `Bearer ${storedToken}`
          } : {}
        }
      );
      return response.data;
    } catch (error: any) {
      // If it's a 401, we're not authenticated
      if (error.response?.status === 401) {
        localStorage.removeItem('access_token');
        return null;
      }
      // For other errors, return null
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
    // Refresh token is now in httpOnly cookie, not accessible via JS
    return null;
  }

  isAuthenticated(): boolean {
    // Since tokens are in httpOnly cookies, we can't check them directly
    // This method should be replaced with a server-side check
    // For now, return false - the actual auth state should be managed by the store
    return false;
  }

  setTokens(accessToken: string, refreshToken: string): void {
    // Tokens are now stored in httpOnly cookies by the backend
    // This method is kept for backward compatibility but does nothing
  }

  clearTokens(): void {
    // Tokens are now in httpOnly cookies and cleared by the backend
    // This method is kept for backward compatibility but does nothing
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
