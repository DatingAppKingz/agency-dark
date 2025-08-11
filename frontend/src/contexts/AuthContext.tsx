/**
 * Authentication Context with OAuth2.0 Support
 * Manages authentication state and OAuth flow
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { oauthService, UserInfo, TokenStorage } from '../services/oauth/oauthService';
import { useNavigate, useLocation } from 'react-router-dom';

// Auth context interface
interface AuthContextType {
  // State
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  // OAuth methods
  initiateOAuthFlow: (prompt?: 'login' | 'consent' | 'select_account') => Promise<void>;
  handleOAuthCallback: (code: string, state: string) => Promise<void>;
  
  // Auth methods
  login: (email?: string, password?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  
  // User methods
  updateUser: () => Promise<void>;
  checkAuth: () => Promise<void>;
  
  // Token methods
  getAccessToken: () => string | null;
  introspectToken: () => Promise<any>;
  
  // External providers
  connectProvider: (provider: string) => Promise<void>;
  disconnectProvider: (provider: string) => Promise<void>;
  getConnectedProviders: () => Promise<string[]>;
}

// Create context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Provider props
interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Authentication Provider Component
 */
export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const navigate = useNavigate();
  const location = useLocation();

  /**
   * Load user from stored token
   */
  const loadUserFromToken = useCallback(async () => {
    try {
      const token = oauthService.getStoredToken();
      if (!token) {
        setIsAuthenticated(false);
        setUser(null);
        return;
      }

      // Check if token is still valid
      const introspection = await oauthService.introspectToken();
      if (!introspection.active) {
        // Token is not active, try to refresh
        await oauthService.refreshAccessToken();
      }

      // Get user info
      const userInfo = await oauthService.getUserInfo();
      setUser(userInfo);
      setIsAuthenticated(true);
      setError(null);
    } catch (err) {
      console.error('Failed to load user:', err);
      setIsAuthenticated(false);
      setUser(null);
      oauthService.clearTokens();
    }
  }, []);

  /**
   * Initialize auth state
   */
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      await loadUserFromToken();
      setIsLoading(false);
    };

    initAuth();
  }, [loadUserFromToken]);

  /**
   * Subscribe to token refresh
   */
  useEffect(() => {
    const unsubscribe = oauthService.subscribeToTokenRefresh(async (token) => {
      // Token was refreshed, update user info
      try {
        const userInfo = await oauthService.getUserInfo();
        setUser(userInfo);
      } catch (err) {
        console.error('Failed to update user after token refresh:', err);
      }
    });

    return unsubscribe;
  }, []);

  /**
   * Initiate OAuth flow
   */
  const initiateOAuthFlow = async (prompt?: 'login' | 'consent' | 'select_account') => {
    try {
      setError(null);
      
      // Store current location for redirect after auth
      const returnUrl = location.pathname + location.search;
      sessionStorage.setItem('auth_return_url', returnUrl);
      
      // Additional parameters
      const params: Record<string, string> = {};
      if (prompt) {
        params.prompt = prompt;
      }
      
      // Get agency from subdomain or query param
      const agency = getAgencyFromContext();
      if (agency) {
        params.agency = agency;
      }
      
      await oauthService.initiateOAuthFlow(params);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'OAuth flow initiation failed';
      setError(message);
      throw new Error(message);
    }
  };

  /**
   * Handle OAuth callback
   */
  const handleOAuthCallback = async (code: string, state: string) => {
    try {
      setIsLoading(true);
      setError(null);
      
      // Exchange code for tokens
      await oauthService.handleOAuthCallback(code, state);
      
      // Load user info
      const userInfo = await oauthService.getUserInfo();
      setUser(userInfo);
      setIsAuthenticated(true);
      
      // Redirect to return URL or dashboard
      const returnUrl = sessionStorage.getItem('auth_return_url') || '/dashboard';
      sessionStorage.removeItem('auth_return_url');
      navigate(returnUrl);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'OAuth callback failed';
      setError(message);
      setIsAuthenticated(false);
      setUser(null);
      throw new Error(message);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Legacy login method (for JWT fallback)
   */
  const login = async (email?: string, password?: string) => {
    if (!email || !password) {
      // No credentials, use OAuth flow
      await initiateOAuthFlow('login');
      return;
    }
    
    // This would be the JWT fallback implementation
    // For now, redirect to OAuth
    await initiateOAuthFlow('login');
  };

  /**
   * Logout
   */
  const logout = async () => {
    try {
      setIsLoading(true);
      
      // Revoke tokens
      await oauthService.revokeTokens();
      
      // Clear state
      setUser(null);
      setIsAuthenticated(false);
      setError(null);
      
      // Redirect to login
      navigate('/login');
    } catch (err) {
      console.error('Logout error:', err);
      // Clear tokens anyway
      oauthService.clearTokens();
      setUser(null);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Refresh token
   */
  const refreshToken = async () => {
    try {
      await oauthService.refreshAccessToken();
      
      // Update user info
      const userInfo = await oauthService.getUserInfo();
      setUser(userInfo);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Token refresh failed';
      setError(message);
      throw new Error(message);
    }
  };

  /**
   * Update user info
   */
  const updateUser = async () => {
    try {
      const userInfo = await oauthService.getUserInfo();
      setUser(userInfo);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update user';
      setError(message);
      throw new Error(message);
    }
  };

  /**
   * Check authentication status
   */
  const checkAuth = async () => {
    try {
      setIsLoading(true);
      await loadUserFromToken();
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Get access token
   */
  const getAccessToken = (): string | null => {
    const token = oauthService.getStoredToken();
    return token?.accessToken || null;
  };

  /**
   * Introspect current token
   */
  const introspectToken = async () => {
    try {
      return await oauthService.introspectToken();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Token introspection failed';
      setError(message);
      throw new Error(message);
    }
  };

  /**
   * Connect external provider
   */
  const connectProvider = async (provider: string) => {
    try {
      setError(null);
      
      // Store return URL
      const returnUrl = location.pathname + location.search;
      sessionStorage.setItem('provider_return_url', returnUrl);
      
      // Redirect to provider connection endpoint
      window.location.href = `/api/v1/oauth/connect/${provider}`;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to connect provider';
      setError(message);
      throw new Error(message);
    }
  };

  /**
   * Disconnect external provider
   */
  const disconnectProvider = async (provider: string) => {
    try {
      setError(null);
      
      const api = oauthService.getAxiosInstance();
      await api.post(`/api/v1/oauth/disconnect/${provider}`);
      
      // Update user to reflect disconnection
      await updateUser();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to disconnect provider';
      setError(message);
      throw new Error(message);
    }
  };

  /**
   * Get connected providers
   */
  const getConnectedProviders = async (): Promise<string[]> => {
    try {
      const api = oauthService.getAxiosInstance();
      const response = await api.get('/api/v1/oauth/accounts');
      return response.data.accounts.map((account: any) => account.provider);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to get connected providers';
      setError(message);
      throw new Error(message);
    }
  };

  /**
   * Get agency from context (subdomain or query param)
   */
  const getAgencyFromContext = (): string | null => {
    // Check subdomain
    const hostname = window.location.hostname;
    const parts = hostname.split('.');
    if (parts.length > 2) {
      return parts[0];
    }
    
    // Check query param
    const params = new URLSearchParams(location.search);
    return params.get('agency');
  };

  // Context value
  const contextValue: AuthContextType = {
    // State
    user,
    isAuthenticated,
    isLoading,
    error,
    
    // OAuth methods
    initiateOAuthFlow,
    handleOAuthCallback,
    
    // Auth methods
    login,
    logout,
    refreshToken,
    
    // User methods
    updateUser,
    checkAuth,
    
    // Token methods
    getAccessToken,
    introspectToken,
    
    // External providers
    connectProvider,
    disconnectProvider,
    getConnectedProviders,
  };

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

/**
 * Hook to use auth context
 */
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

/**
 * HOC for protected routes
 */
export const withAuth = <P extends object>(
  Component: React.ComponentType<P>,
  redirectTo: string = '/login'
): React.FC<P> => {
  return (props: P) => {
    const { isAuthenticated, isLoading } = useAuth();
    const navigate = useNavigate();
    const location = useLocation();

    useEffect(() => {
      if (!isLoading && !isAuthenticated) {
        // Store current location for redirect after auth
        sessionStorage.setItem('auth_return_url', location.pathname + location.search);
        navigate(redirectTo);
      }
    }, [isAuthenticated, isLoading, navigate, location]);

    if (isLoading) {
      return <div>Loading...</div>;
    }

    if (!isAuthenticated) {
      return null;
    }

    return <Component {...props} />;
  };
};

/**
 * HOC for routes that require specific permissions
 */
export const withPermission = <P extends object>(
  Component: React.ComponentType<P>,
  requiredPermission: string,
  redirectTo: string = '/unauthorized'
): React.FC<P> => {
  return (props: P) => {
    const { user, isAuthenticated, isLoading } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
      if (!isLoading && isAuthenticated) {
        const hasPermission = user?.permissions?.includes(requiredPermission);
        if (!hasPermission) {
          navigate(redirectTo);
        }
      }
    }, [user, isAuthenticated, isLoading, navigate]);

    if (isLoading) {
      return <div>Loading...</div>;
    }

    if (!isAuthenticated || !user?.permissions?.includes(requiredPermission)) {
      return null;
    }

    return <Component {...props} />;
  };
};

export default AuthContext;