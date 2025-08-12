# OAuth Frontend Integration Guide

## Overview
This guide provides step-by-step instructions for integrating OAuth 2.0 authentication into the Agency Dark frontend application. The implementation uses the Authorization Code flow with PKCE for enhanced security.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [OAuth Service Setup](#oauth-service-setup)
- [Authentication Context](#authentication-context)
- [UI Components](#ui-components)
- [Token Management](#token-management)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before implementing OAuth in your frontend:

1. **Client Registration**: Obtain OAuth client credentials from the admin panel
2. **Redirect URI**: Configure allowed redirect URIs for your application
3. **Dependencies**: Install required packages:
   ```bash
   npm install axios crypto-js js-cookie
   ```

---

## Quick Start

### 1. Initialize OAuth Service

```typescript
// src/services/oauth/oauthService.ts
import { OAuthService } from './oauthService';

const oauthService = new OAuthService({
  clientId: process.env.REACT_APP_OAUTH_CLIENT_ID,
  redirectUri: process.env.REACT_APP_OAUTH_REDIRECT_URI,
  authorizationEndpoint: '/oauth/authorize',
  tokenEndpoint: '/oauth/token',
  userInfoEndpoint: '/oauth/userinfo',
  scopes: ['read:profile', 'write:campaigns']
});
```

### 2. Implement Login Flow

```tsx
// src/pages/Login.tsx
import React from 'react';
import { useAuth } from '../contexts/AuthContext';

export const Login: React.FC = () => {
  const { initiateOAuthFlow } = useAuth();

  const handleLogin = async () => {
    try {
      await initiateOAuthFlow();
    } catch (error) {
      console.error('Login failed:', error);
    }
  };

  return (
    <button onClick={handleLogin}>
      Sign in with OAuth
    </button>
  );
};
```

### 3. Handle OAuth Callback

```tsx
// src/pages/OAuthCallback.tsx
import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

export const OAuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { handleOAuthCallback } = useAuth();

  useEffect(() => {
    const processCallback = async () => {
      try {
        const code = searchParams.get('code');
        const state = searchParams.get('state');
        const error = searchParams.get('error');

        if (error) {
          throw new Error(error);
        }

        await handleOAuthCallback(code!, state!);
        navigate('/dashboard');
      } catch (error) {
        console.error('OAuth callback failed:', error);
        navigate('/login?error=oauth_failed');
      }
    };

    processCallback();
  }, [searchParams]);

  return <div>Processing authentication...</div>;
};
```

---

## OAuth Service Setup

### Complete OAuth Service Implementation

```typescript
// src/services/oauth/oauthService.ts
import axios from 'axios';
import CryptoJS from 'crypto-js';

interface OAuthConfig {
  clientId: string;
  redirectUri: string;
  authorizationEndpoint: string;
  tokenEndpoint: string;
  userInfoEndpoint: string;
  scopes: string[];
}

interface PKCEChallenge {
  codeVerifier: string;
  codeChallenge: string;
}

interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  expires_in: number;
  token_type: string;
  scope?: string;
}

export class OAuthService {
  private config: OAuthConfig;
  private tokenStorage = new TokenStorage();

  constructor(config: OAuthConfig) {
    this.config = config;
    this.setupInterceptors();
  }

  /**
   * Generate PKCE challenge for secure authorization
   */
  private generatePKCEChallenge(): PKCEChallenge {
    const codeVerifier = this.generateRandomString(128);
    const hash = CryptoJS.SHA256(codeVerifier);
    const codeChallenge = hash.toString(CryptoJS.enc.Base64url);

    return { codeVerifier, codeChallenge };
  }

  /**
   * Generate cryptographically secure random string
   */
  private generateRandomString(length: number): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
    const array = new Uint8Array(length);
    crypto.getRandomValues(array);
    return Array.from(array, byte => chars[byte % chars.length]).join('');
  }

  /**
   * Initiate OAuth authorization flow
   */
  public async initiateAuthFlow(agencyId?: string): Promise<void> {
    const state = this.generateRandomString(32);
    const { codeVerifier, codeChallenge } = this.generatePKCEChallenge();

    // Store PKCE and state in session storage
    sessionStorage.setItem('oauth_state', state);
    sessionStorage.setItem('oauth_code_verifier', codeVerifier);

    const params = new URLSearchParams({
      response_type: 'code',
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      scope: this.config.scopes.join(' '),
      state,
      code_challenge: codeChallenge,
      code_challenge_method: 'S256'
    });

    if (agencyId) {
      params.append('agency_id', agencyId);
    }

    // Redirect to authorization endpoint
    window.location.href = `${this.config.authorizationEndpoint}?${params}`;
  }

  /**
   * Exchange authorization code for tokens
   */
  public async exchangeCodeForTokens(code: string, state: string): Promise<TokenResponse> {
    // Validate state parameter
    const storedState = sessionStorage.getItem('oauth_state');
    if (state !== storedState) {
      throw new Error('Invalid state parameter - possible CSRF attack');
    }

    const codeVerifier = sessionStorage.getItem('oauth_code_verifier');
    if (!codeVerifier) {
      throw new Error('Code verifier not found');
    }

    const response = await axios.post<TokenResponse>(
      this.config.tokenEndpoint,
      new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        redirect_uri: this.config.redirectUri,
        client_id: this.config.clientId,
        code_verifier: codeVerifier
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );

    // Clean up session storage
    sessionStorage.removeItem('oauth_state');
    sessionStorage.removeItem('oauth_code_verifier');

    // Store tokens securely
    this.tokenStorage.setTokens(response.data);

    return response.data;
  }

  /**
   * Refresh access token using refresh token
   */
  public async refreshAccessToken(): Promise<TokenResponse> {
    const refreshToken = this.tokenStorage.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    try {
      const response = await axios.post<TokenResponse>(
        this.config.tokenEndpoint,
        new URLSearchParams({
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
          client_id: this.config.clientId
        }),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        }
      );

      this.tokenStorage.setTokens(response.data);
      return response.data;
    } catch (error) {
      // If refresh fails, clear tokens and redirect to login
      this.tokenStorage.clearTokens();
      throw error;
    }
  }

  /**
   * Get current user information
   */
  public async getUserInfo(): Promise<any> {
    const accessToken = this.tokenStorage.getAccessToken();
    if (!accessToken) {
      throw new Error('No access token available');
    }

    const response = await axios.get(this.config.userInfoEndpoint, {
      headers: {
        Authorization: `Bearer ${accessToken}`
      }
    });

    return response.data;
  }

  /**
   * Revoke tokens and logout
   */
  public async logout(): Promise<void> {
    const accessToken = this.tokenStorage.getAccessToken();
    const refreshToken = this.tokenStorage.getRefreshToken();

    // Revoke tokens on the server
    const revocationPromises = [];
    
    if (accessToken) {
      revocationPromises.push(
        axios.post('/oauth/revoke', 
          new URLSearchParams({ token: accessToken, token_type_hint: 'access_token' }),
          { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        ).catch(() => {}) // Ignore revocation errors
      );
    }

    if (refreshToken) {
      revocationPromises.push(
        axios.post('/oauth/revoke',
          new URLSearchParams({ token: refreshToken, token_type_hint: 'refresh_token' }),
          { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
        ).catch(() => {}) // Ignore revocation errors
      );
    }

    await Promise.all(revocationPromises);
    this.tokenStorage.clearTokens();
  }

  /**
   * Setup axios interceptors for automatic token handling
   */
  private setupInterceptors(): void {
    // Request interceptor to add token
    axios.interceptors.request.use(
      (config) => {
        const token = this.tokenStorage.getAccessToken();
        if (token && !config.headers.Authorization) {
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
            await this.refreshAccessToken();
            const token = this.tokenStorage.getAccessToken();
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return axios(originalRequest);
          } catch (refreshError) {
            // Redirect to login on refresh failure
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        return Promise.reject(error);
      }
    );
  }
}

/**
 * Secure token storage with encryption
 */
class TokenStorage {
  private readonly ACCESS_TOKEN_KEY = 'oauth_access_token';
  private readonly REFRESH_TOKEN_KEY = 'oauth_refresh_token';
  private readonly TOKEN_EXPIRY_KEY = 'oauth_token_expiry';

  public setTokens(tokens: TokenResponse): void {
    // Store in memory for this session
    sessionStorage.setItem(this.ACCESS_TOKEN_KEY, tokens.access_token);
    
    // Store refresh token more persistently (encrypted)
    if (tokens.refresh_token) {
      const encrypted = this.encrypt(tokens.refresh_token);
      localStorage.setItem(this.REFRESH_TOKEN_KEY, encrypted);
    }

    // Calculate and store expiry time
    const expiryTime = Date.now() + (tokens.expires_in * 1000);
    sessionStorage.setItem(this.TOKEN_EXPIRY_KEY, expiryTime.toString());
  }

  public getAccessToken(): string | null {
    const token = sessionStorage.getItem(this.ACCESS_TOKEN_KEY);
    const expiry = sessionStorage.getItem(this.TOKEN_EXPIRY_KEY);

    if (token && expiry && Date.now() < parseInt(expiry)) {
      return token;
    }

    return null;
  }

  public getRefreshToken(): string | null {
    const encrypted = localStorage.getItem(this.REFRESH_TOKEN_KEY);
    if (encrypted) {
      return this.decrypt(encrypted);
    }
    return null;
  }

  public clearTokens(): void {
    sessionStorage.removeItem(this.ACCESS_TOKEN_KEY);
    sessionStorage.removeItem(this.TOKEN_EXPIRY_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
  }

  private encrypt(data: string): string {
    // Use a proper encryption key in production
    const key = process.env.REACT_APP_ENCRYPTION_KEY || 'default-key';
    return CryptoJS.AES.encrypt(data, key).toString();
  }

  private decrypt(data: string): string {
    const key = process.env.REACT_APP_ENCRYPTION_KEY || 'default-key';
    const bytes = CryptoJS.AES.decrypt(data, key);
    return bytes.toString(CryptoJS.enc.Utf8);
  }
}
```

---

## Authentication Context

### Complete Auth Context Implementation

```tsx
// src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { OAuthService } from '../services/oauth/oauthService';
import { User } from '../types/user';

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  initiateOAuthFlow: (agencyId?: string) => Promise<void>;
  handleOAuthCallback: (code: string, state: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const oauthService = new OAuthService({
  clientId: process.env.REACT_APP_OAUTH_CLIENT_ID!,
  redirectUri: process.env.REACT_APP_OAUTH_REDIRECT_URI!,
  authorizationEndpoint: '/oauth/authorize',
  tokenEndpoint: '/oauth/token',
  userInfoEndpoint: '/oauth/userinfo',
  scopes: ['read:profile', 'write:campaigns']
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Initialize authentication state on mount
   */
  useEffect(() => {
    const initAuth = async () => {
      try {
        const userInfo = await oauthService.getUserInfo();
        setUser(userInfo);
      } catch (error) {
        // User not authenticated or token expired
        console.debug('User not authenticated');
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  /**
   * Initiate OAuth flow
   */
  const initiateOAuthFlow = useCallback(async (agencyId?: string) => {
    setIsLoading(true);
    await oauthService.initiateAuthFlow(agencyId);
  }, []);

  /**
   * Handle OAuth callback
   */
  const handleOAuthCallback = useCallback(async (code: string, state: string) => {
    setIsLoading(true);
    try {
      await oauthService.exchangeCodeForTokens(code, state);
      const userInfo = await oauthService.getUserInfo();
      setUser(userInfo);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Logout user
   */
  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await oauthService.logout();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Refresh access token
   */
  const refreshToken = useCallback(async () => {
    try {
      await oauthService.refreshAccessToken();
      const userInfo = await oauthService.getUserInfo();
      setUser(userInfo);
    } catch (error) {
      // If refresh fails, user needs to re-authenticate
      setUser(null);
      throw error;
    }
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    isLoading,
    initiateOAuthFlow,
    handleOAuthCallback,
    logout,
    refreshToken
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

---

## UI Components

### Social Login Component

```tsx
// src/components/auth/SocialLogin.tsx
import React from 'react';
import { FaGoogle, FaInstagram, FaMicrosoft } from 'react-icons/fa';

interface SocialLoginProps {
  onProviderSelect: (provider: string) => void;
  disabled?: boolean;
}

export const SocialLogin: React.FC<SocialLoginProps> = ({ onProviderSelect, disabled }) => {
  const providers = [
    { id: 'google', name: 'Google', icon: FaGoogle, color: '#4285F4' },
    { id: 'instagram', name: 'Instagram', icon: FaInstagram, color: '#E4405F' },
    { id: 'microsoft', name: 'Microsoft', icon: FaMicrosoft, color: '#0078D4' }
  ];

  return (
    <div className="social-login">
      <div className="divider">
        <span>Or continue with</span>
      </div>
      <div className="provider-buttons">
        {providers.map((provider) => {
          const Icon = provider.icon;
          return (
            <button
              key={provider.id}
              onClick={() => onProviderSelect(provider.id)}
              disabled={disabled}
              className="provider-button"
              style={{ borderColor: provider.color }}
            >
              <Icon style={{ color: provider.color }} />
              <span>{provider.name}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
```

### Protected Route Component

```tsx
// src/components/auth/ProtectedRoute.tsx
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermissions?: string[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredPermissions = [] 
}) => {
  const { isAuthenticated, user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredPermissions.length > 0) {
    const hasPermissions = requiredPermissions.every(
      permission => user?.permissions?.includes(permission)
    );

    if (!hasPermissions) {
      return <Navigate to="/unauthorized" replace />;
    }
  }

  return <>{children}</>;
};
```

---

## Token Management

### Automatic Token Refresh

```typescript
// src/services/tokenRefreshManager.ts
export class TokenRefreshManager {
  private refreshTimer: NodeJS.Timeout | null = null;
  private readonly REFRESH_BUFFER = 5 * 60 * 1000; // 5 minutes before expiry

  public scheduleRefresh(expiresIn: number, refreshCallback: () => Promise<void>): void {
    this.cancelRefresh();

    // Schedule refresh 5 minutes before token expires
    const refreshTime = (expiresIn * 1000) - this.REFRESH_BUFFER;
    
    this.refreshTimer = setTimeout(async () => {
      try {
        await refreshCallback();
        // Schedule next refresh after successful refresh
        this.scheduleRefresh(expiresIn, refreshCallback);
      } catch (error) {
        console.error('Token refresh failed:', error);
      }
    }, refreshTime);
  }

  public cancelRefresh(): void {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
  }
}
```

### Cross-Tab Synchronization

```typescript
// src/services/authSync.ts
export class AuthSync {
  private readonly SYNC_EVENT = 'auth-sync';
  
  constructor() {
    window.addEventListener('storage', this.handleStorageChange);
  }

  private handleStorageChange = (event: StorageEvent): void => {
    if (event.key === this.SYNC_EVENT) {
      const data = JSON.parse(event.newValue || '{}');
      
      switch (data.type) {
        case 'LOGIN':
          window.location.reload(); // Reload to fetch new user data
          break;
        case 'LOGOUT':
          // Clear local session and redirect
          sessionStorage.clear();
          window.location.href = '/login';
          break;
        case 'TOKEN_REFRESH':
          // Update tokens in current tab
          this.updateTokens(data.tokens);
          break;
      }
    }
  };

  public broadcastLogin(tokens: any): void {
    localStorage.setItem(this.SYNC_EVENT, JSON.stringify({
      type: 'LOGIN',
      tokens,
      timestamp: Date.now()
    }));
  }

  public broadcastLogout(): void {
    localStorage.setItem(this.SYNC_EVENT, JSON.stringify({
      type: 'LOGOUT',
      timestamp: Date.now()
    }));
  }

  private updateTokens(tokens: any): void {
    sessionStorage.setItem('oauth_access_token', tokens.access_token);
    sessionStorage.setItem('oauth_token_expiry', tokens.expiry);
  }
}
```

---

## Error Handling

### OAuth Error Handler

```typescript
// src/utils/oauthErrorHandler.ts
export interface OAuthError {
  error: string;
  error_description?: string;
  error_uri?: string;
}

export class OAuthErrorHandler {
  private static readonly ERROR_MESSAGES: Record<string, string> = {
    'invalid_request': 'The request is missing required parameters or is malformed.',
    'unauthorized_client': 'You are not authorized to access this resource.',
    'access_denied': 'Access was denied. Please try again or contact support.',
    'unsupported_response_type': 'The authorization server does not support this response type.',
    'invalid_scope': 'The requested permissions are invalid or not available.',
    'server_error': 'The server encountered an error. Please try again later.',
    'temporarily_unavailable': 'The service is temporarily unavailable. Please try again later.',
    'invalid_grant': 'Your session has expired. Please sign in again.',
    'invalid_token': 'Your session is invalid. Please sign in again.'
  };

  public static getErrorMessage(error: OAuthError | string): string {
    if (typeof error === 'string') {
      return this.ERROR_MESSAGES[error] || 'An unexpected error occurred.';
    }
    
    return error.error_description || 
           this.ERROR_MESSAGES[error.error] || 
           'An unexpected error occurred.';
  }

  public static handleError(error: any): void {
    const message = this.getErrorMessage(error);
    
    // Log to monitoring service
    console.error('OAuth Error:', error);
    
    // Show user-friendly message
    this.showErrorNotification(message);
  }

  private static showErrorNotification(message: string): void {
    // Implement your notification system here
    // Example: toast.error(message);
  }
}
```

---

## Testing

### Unit Tests

```typescript
// src/services/oauth/__tests__/oauthService.test.ts
import { OAuthService } from '../oauthService';
import axios from 'axios';

jest.mock('axios');

describe('OAuthService', () => {
  let service: OAuthService;

  beforeEach(() => {
    service = new OAuthService({
      clientId: 'test-client',
      redirectUri: 'http://localhost:3000/callback',
      authorizationEndpoint: '/oauth/authorize',
      tokenEndpoint: '/oauth/token',
      userInfoEndpoint: '/oauth/userinfo',
      scopes: ['read:profile']
    });
  });

  describe('PKCE Challenge', () => {
    it('should generate valid PKCE challenge', () => {
      const challenge = service['generatePKCEChallenge']();
      
      expect(challenge.codeVerifier).toHaveLength(128);
      expect(challenge.codeChallenge).toBeTruthy();
      expect(challenge.codeChallenge).not.toContain('+');
      expect(challenge.codeChallenge).not.toContain('/');
      expect(challenge.codeChallenge).not.toContain('=');
    });
  });

  describe('Token Exchange', () => {
    it('should exchange code for tokens', async () => {
      const mockTokens = {
        access_token: 'access-token',
        refresh_token: 'refresh-token',
        expires_in: 3600,
        token_type: 'Bearer'
      };

      (axios.post as jest.Mock).mockResolvedValue({ data: mockTokens });

      sessionStorage.setItem('oauth_state', 'test-state');
      sessionStorage.setItem('oauth_code_verifier', 'test-verifier');

      const tokens = await service.exchangeCodeForTokens('test-code', 'test-state');

      expect(tokens).toEqual(mockTokens);
      expect(sessionStorage.getItem('oauth_state')).toBeNull();
      expect(sessionStorage.getItem('oauth_code_verifier')).toBeNull();
    });

    it('should reject invalid state', async () => {
      sessionStorage.setItem('oauth_state', 'valid-state');

      await expect(
        service.exchangeCodeForTokens('test-code', 'invalid-state')
      ).rejects.toThrow('Invalid state parameter');
    });
  });

  describe('Token Refresh', () => {
    it('should refresh access token', async () => {
      const mockTokens = {
        access_token: 'new-access-token',
        expires_in: 3600,
        token_type: 'Bearer'
      };

      (axios.post as jest.Mock).mockResolvedValue({ data: mockTokens });

      // Mock refresh token in storage
      localStorage.setItem('oauth_refresh_token', 'encrypted-refresh-token');

      const tokens = await service.refreshAccessToken();

      expect(tokens).toEqual(mockTokens);
    });
  });
});
```

### Integration Tests

```typescript
// src/contexts/__tests__/AuthContext.test.tsx
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../AuthContext';
import { BrowserRouter } from 'react-router-dom';

const TestComponent: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  
  return (
    <div>
      {isLoading && <div>Loading...</div>}
      {isAuthenticated && <div>Authenticated: {user?.name}</div>}
      {!isAuthenticated && !isLoading && <div>Not authenticated</div>}
    </div>
  );
};

describe('AuthContext', () => {
  it('should initialize with loading state', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('should handle authenticated user', async () => {
    // Mock getUserInfo to return user data
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ name: 'John Doe', email: 'john@example.com' })
    });

    render(
      <BrowserRouter>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Authenticated: John Doe')).toBeInTheDocument();
    });
  });
});
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. CORS Errors
**Problem**: Browser blocks OAuth requests due to CORS policy.

**Solution**:
```typescript
// Ensure your API allows the frontend origin
// Backend CORS configuration should include:
cors({
  origin: process.env.FRONTEND_URL,
  credentials: true
})
```

#### 2. State Mismatch Errors
**Problem**: "Invalid state parameter" error during callback.

**Solution**:
- Ensure cookies/session storage is enabled
- Check for multiple redirect URIs causing confusion
- Verify no browser extensions are blocking storage

#### 3. Token Expiration Issues
**Problem**: Users get logged out unexpectedly.

**Solution**:
```typescript
// Implement proactive token refresh
const refreshBuffer = 5 * 60 * 1000; // 5 minutes
const refreshTime = (expiresIn * 1000) - refreshBuffer;

setTimeout(() => {
  oauthService.refreshAccessToken();
}, refreshTime);
```

#### 4. Popup Blockers
**Problem**: OAuth popup windows are blocked.

**Solution**:
```typescript
// Use redirect flow instead of popup
// Or ensure popup is triggered by user action
const handleLogin = () => {
  // This will not be blocked as it's user-initiated
  window.open(authUrl, 'oauth', 'width=600,height=700');
};
```

#### 5. Multi-Tab Synchronization
**Problem**: User logs out in one tab but remains logged in others.

**Solution**:
```typescript
// Implement storage event listener
window.addEventListener('storage', (e) => {
  if (e.key === 'logout') {
    window.location.href = '/login';
  }
});
```

---

## Best Practices

1. **Security**
   - Always use PKCE for public clients
   - Store tokens securely (memory/sessionStorage for access tokens)
   - Implement CSRF protection with state parameter
   - Use HTTPS in production

2. **Performance**
   - Cache user info to reduce API calls
   - Implement token refresh before expiry
   - Use lazy loading for OAuth components

3. **User Experience**
   - Show loading states during authentication
   - Provide clear error messages
   - Remember user preferences (e.g., selected agency)
   - Implement smooth redirect flows

4. **Monitoring**
   - Log authentication events
   - Track OAuth errors and success rates
   - Monitor token refresh failures
   - Set up alerts for high failure rates

---

## Migration from JWT

If migrating from JWT authentication:

1. **Update Login Flow**:
   ```typescript
   // Old JWT login
   const login = async (email, password) => {
     const { token } = await api.post('/auth/login', { email, password });
     localStorage.setItem('jwt', token);
   };

   // New OAuth login
   const login = async () => {
     await oauthService.initiateAuthFlow();
   };
   ```

2. **Update API Calls**:
   ```typescript
   // Old JWT header
   headers: { 'Authorization': `Bearer ${jwt}` }

   // New OAuth header (handled automatically by interceptor)
   // No manual header needed
   ```

3. **Update Token Storage**:
   ```typescript
   // Remove JWT tokens
   localStorage.removeItem('jwt');
   
   // OAuth tokens are managed by OAuthService
   ```

---

## Resources

- [OAuth 2.0 Specification (RFC 6749)](https://tools.ietf.org/html/rfc6749)
- [PKCE Specification (RFC 7636)](https://tools.ietf.org/html/rfc7636)
- [OAuth Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [Agency Dark OAuth API Documentation](./oauth-endpoints.md)

---

## Support

For additional help:
- Check the [FAQ section](../faq/oauth-faq.md)
- Contact the development team
- Submit issues to the project repository