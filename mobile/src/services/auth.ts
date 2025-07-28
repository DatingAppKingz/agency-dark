/**
 * Authentication Service
 * 
 * Handles all authentication-related API calls and token management
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Keychain from 'react-native-keychain';
import DeviceInfo from 'react-native-device-info';

import { api } from './api';
import { 
  User, 
  AuthTokens, 
  LoginCredentials, 
  RegisterData, 
  AuthResponse 
} from '@/types/auth';

const TOKEN_KEY = '@auth_tokens';
const USER_KEY = '@user_data';

class AuthService {
  // Store tokens securely
  async storeTokens(tokens: AuthTokens): Promise<void> {
    try {
      // Store in encrypted keychain for better security
      await Keychain.setInternetCredentials(
        'agencydark.tokens',
        'tokens',
        JSON.stringify(tokens)
      );
      
      // Also store in AsyncStorage for quick access
      await AsyncStorage.setItem(TOKEN_KEY, JSON.stringify(tokens));
    } catch (error) {
      console.error('Failed to store tokens:', error);
      throw error;
    }
  }

  // Retrieve stored tokens
  async getStoredTokens(): Promise<AuthTokens | null> {
    try {
      // Try keychain first
      const credentials = await Keychain.getInternetCredentials('agencydark.tokens');
      if (credentials) {
        return JSON.parse(credentials.password);
      }

      // Fallback to AsyncStorage
      const tokensString = await AsyncStorage.getItem(TOKEN_KEY);
      if (tokensString) {
        return JSON.parse(tokensString);
      }

      return null;
    } catch (error) {
      console.error('Failed to retrieve tokens:', error);
      return null;
    }
  }

  // Clear stored tokens
  async clearTokens(): Promise<void> {
    try {
      await Keychain.resetInternetCredentials('agencydark.tokens');
      await AsyncStorage.removeItem(TOKEN_KEY);
      await AsyncStorage.removeItem(USER_KEY);
    } catch (error) {
      console.error('Failed to clear tokens:', error);
    }
  }

  // Login with email and password
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      const deviceId = await DeviceInfo.getUniqueId();
      const deviceName = await DeviceInfo.getDeviceName();
      
      const response = await api.post<AuthResponse>('/auth/mobile/login', {
        ...credentials,
        device_info: {
          device_id: deviceId,
          device_name: deviceName,
          platform: DeviceInfo.getSystemName(),
          platform_version: DeviceInfo.getSystemVersion(),
          app_version: DeviceInfo.getVersion(),
        }
      });

      if (response.data.tokens) {
        await this.storeTokens(response.data.tokens);
        api.setAuthToken(response.data.tokens.accessToken);
      }

      if (response.data.user) {
        await AsyncStorage.setItem(USER_KEY, JSON.stringify(response.data.user));
      }

      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Login failed');
    }
  }

  // Register new user
  async register(data: RegisterData): Promise<AuthResponse> {
    try {
      const deviceId = await DeviceInfo.getUniqueId();
      
      const response = await api.post<AuthResponse>('/auth/mobile/register', {
        ...data,
        device_id: deviceId,
      });

      if (response.data.tokens) {
        await this.storeTokens(response.data.tokens);
        api.setAuthToken(response.data.tokens.accessToken);
      }

      if (response.data.user) {
        await AsyncStorage.setItem(USER_KEY, JSON.stringify(response.data.user));
      }

      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Registration failed');
    }
  }

  // Logout
  async logout(): Promise<void> {
    try {
      const tokens = await this.getStoredTokens();
      
      if (tokens) {
        // Notify backend about logout
        await api.post('/auth/mobile/logout', {
          refresh_token: tokens.refreshToken,
          device_id: await DeviceInfo.getUniqueId(),
        });
      }
    } catch (error) {
      console.error('Logout API call failed:', error);
    } finally {
      // Always clear local data
      await this.clearTokens();
      api.clearAuthToken();
    }
  }

  // Refresh authentication tokens
  async refreshTokens(refreshToken: string): Promise<AuthTokens | null> {
    try {
      const response = await api.post<{ tokens: AuthTokens }>('/auth/mobile/refresh', {
        refresh_token: refreshToken,
        device_id: await DeviceInfo.getUniqueId(),
      });

      if (response.data.tokens) {
        await this.storeTokens(response.data.tokens);
        api.setAuthToken(response.data.tokens.accessToken);
        return response.data.tokens;
      }

      return null;
    } catch (error) {
      console.error('Token refresh failed:', error);
      return null;
    }
  }

  // Validate token with backend
  async validateToken(accessToken: string): Promise<User | null> {
    try {
      api.setAuthToken(accessToken);
      const response = await api.get<{ user: User }>('/auth/mobile/me');
      
      if (response.data.user) {
        await AsyncStorage.setItem(USER_KEY, JSON.stringify(response.data.user));
        return response.data.user;
      }

      return null;
    } catch (error) {
      console.error('Token validation failed:', error);
      return null;
    }
  }

  // Get stored user data
  async getStoredUser(): Promise<User | null> {
    try {
      const userString = await AsyncStorage.getItem(USER_KEY);
      if (userString) {
        return JSON.parse(userString);
      }
      return null;
    } catch (error) {
      console.error('Failed to retrieve user data:', error);
      return null;
    }
  }

  // Request password reset
  async requestPasswordReset(email: string): Promise<void> {
    try {
      await api.post('/auth/mobile/reset-password', { email });
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Failed to send reset email');
    }
  }

  // Reset password with token
  async resetPassword(token: string, newPassword: string): Promise<void> {
    try {
      await api.post('/auth/mobile/reset-password/confirm', {
        token,
        new_password: newPassword,
      });
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Failed to reset password');
    }
  }

  // Update user profile
  async updateProfile(updates: Partial<User>): Promise<User> {
    try {
      const response = await api.patch<{ user: User }>('/auth/mobile/profile', updates);
      
      if (response.data.user) {
        await AsyncStorage.setItem(USER_KEY, JSON.stringify(response.data.user));
        return response.data.user;
      }

      throw new Error('Failed to update profile');
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Profile update failed');
    }
  }

  // Enable 2FA
  async enable2FA(): Promise<{ qrCode: string; secret: string }> {
    try {
      const response = await api.post<{ qr_code: string; secret: string }>('/auth/mobile/2fa/enable');
      return {
        qrCode: response.data.qr_code,
        secret: response.data.secret,
      };
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Failed to enable 2FA');
    }
  }

  // Verify 2FA code
  async verify2FA(code: string): Promise<void> {
    try {
      await api.post('/auth/mobile/2fa/verify', { code });
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Invalid 2FA code');
    }
  }

  // Disable 2FA
  async disable2FA(password: string): Promise<void> {
    try {
      await api.post('/auth/mobile/2fa/disable', { password });
    } catch (error: any) {
      throw new Error(error.response?.data?.message || 'Failed to disable 2FA');
    }
  }
}

export const authService = new AuthService();