/**
 * Authentication Context
 * 
 * Manages authentication state and provides auth methods
 */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import * as Keychain from 'react-native-keychain';
import ReactNativeBiometrics, { BiometryTypes } from 'react-native-biometrics';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { authService } from '@/services/auth';
import { User, AuthTokens, LoginCredentials, RegisterData } from '@/types/auth';
import { showMessage } from '@/utils/toast';

const rnBiometrics = new ReactNativeBiometrics();

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  biometricType: string | null;
  login: (credentials: LoginCredentials) => Promise<void>;
  loginWithBiometrics: () => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  updateUser: (user: Partial<User>) => void;
  checkBiometricAvailability: () => Promise<void>;
  enableBiometrics: () => Promise<void>;
  disableBiometrics: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [biometricType, setBiometricType] = useState<string | null>(null);

  // Check biometric availability
  const checkBiometricAvailability = useCallback(async () => {
    try {
      const { biometryType, available } = await rnBiometrics.isSensorAvailable();
      
      if (available && biometryType) {
        setBiometricType(biometryType);
      } else {
        setBiometricType(null);
      }
    } catch (error) {
      console.error('Biometric check failed:', error);
      setBiometricType(null);
    }
  }, []);

  // Initialize auth state
  useEffect(() => {
    const initializeAuth = async () => {
      try {
        setIsLoading(true);

        // Check for stored tokens
        const tokens = await authService.getStoredTokens();
        if (tokens) {
          // Validate tokens with backend
          const userData = await authService.validateToken(tokens.accessToken);
          if (userData) {
            setUser(userData);
          } else {
            // Try to refresh token
            const newTokens = await authService.refreshTokens(tokens.refreshToken);
            if (newTokens) {
              const userData = await authService.validateToken(newTokens.accessToken);
              setUser(userData);
            }
          }
        }

        // Check biometric availability
        await checkBiometricAvailability();

      } catch (error) {
        console.error('Auth initialization failed:', error);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, [checkBiometricAvailability]);

  // Login with credentials
  const login = useCallback(async (credentials: LoginCredentials) => {
    try {
      setIsLoading(true);
      const response = await authService.login(credentials);
      
      if (response.user && response.tokens) {
        setUser(response.user);
        await authService.storeTokens(response.tokens);
        
        // Store credentials for biometric login if enabled
        const biometricsEnabled = await AsyncStorage.getItem('biometrics_enabled');
        if (biometricsEnabled === 'true') {
          await Keychain.setInternetCredentials(
            'agencydark.com',
            credentials.email,
            credentials.password
          );
        }
        
        showMessage('Login successful', 'success');
      }
    } catch (error: any) {
      showMessage(error.message || 'Login failed', 'error');
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Login with biometrics
  const loginWithBiometrics = useCallback(async () => {
    try {
      if (!biometricType) {
        throw new Error('Biometrics not available');
      }

      // Prompt for biometric authentication
      const { success } = await rnBiometrics.simplePrompt({
        promptMessage: 'Authenticate to login',
        cancelButtonText: 'Cancel',
      });

      if (!success) {
        throw new Error('Biometric authentication failed');
      }

      // Retrieve stored credentials
      const credentials = await Keychain.getInternetCredentials('agencydark.com');
      if (!credentials) {
        throw new Error('No stored credentials found');
      }

      // Login with stored credentials
      await login({
        email: credentials.username,
        password: credentials.password,
      });

    } catch (error: any) {
      showMessage(error.message || 'Biometric login failed', 'error');
      throw error;
    }
  }, [biometricType, login]);

  // Register new user
  const register = useCallback(async (data: RegisterData) => {
    try {
      setIsLoading(true);
      const response = await authService.register(data);
      
      if (response.user && response.tokens) {
        setUser(response.user);
        await authService.storeTokens(response.tokens);
        showMessage('Registration successful', 'success');
      }
    } catch (error: any) {
      showMessage(error.message || 'Registration failed', 'error');
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      setIsLoading(true);
      await authService.logout();
      setUser(null);
      
      // Clear stored credentials
      await Keychain.resetInternetCredentials('agencydark.com');
      
      showMessage('Logged out successfully', 'success');
    } catch (error: any) {
      showMessage(error.message || 'Logout failed', 'error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Refresh token
  const refreshToken = useCallback(async () => {
    try {
      const tokens = await authService.getStoredTokens();
      if (!tokens) {
        throw new Error('No tokens found');
      }

      const newTokens = await authService.refreshTokens(tokens.refreshToken);
      if (newTokens) {
        await authService.storeTokens(newTokens);
        const userData = await authService.validateToken(newTokens.accessToken);
        setUser(userData);
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
      // If refresh fails, logout user
      await logout();
    }
  }, [logout]);

  // Update user data
  const updateUser = useCallback((updates: Partial<User>) => {
    setUser(prev => prev ? { ...prev, ...updates } : null);
  }, []);

  // Enable biometrics
  const enableBiometrics = useCallback(async () => {
    try {
      if (!biometricType) {
        throw new Error('Biometrics not available');
      }

      const { success } = await rnBiometrics.simplePrompt({
        promptMessage: 'Enable biometric authentication',
        cancelButtonText: 'Cancel',
      });

      if (success) {
        await AsyncStorage.setItem('biometrics_enabled', 'true');
        showMessage('Biometrics enabled', 'success');
      }
    } catch (error: any) {
      showMessage(error.message || 'Failed to enable biometrics', 'error');
      throw error;
    }
  }, [biometricType]);

  // Disable biometrics
  const disableBiometrics = useCallback(async () => {
    try {
      await AsyncStorage.removeItem('biometrics_enabled');
      await Keychain.resetInternetCredentials('agencydark.com');
      showMessage('Biometrics disabled', 'success');
    } catch (error: any) {
      showMessage(error.message || 'Failed to disable biometrics', 'error');
      throw error;
    }
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    biometricType,
    login,
    loginWithBiometrics,
    register,
    logout,
    refreshToken,
    updateUser,
    checkBiometricAvailability,
    enableBiometrics,
    disableBiometrics,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;