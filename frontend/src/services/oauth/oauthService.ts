/**
 * OAuth2.0 Service Layer
 * Handles OAuth authentication flow with PKCE support
 */

import axios, { AxiosInstance, AxiosError, AxiosRequestConfig } from 'axios';

// OAuth configuration interface
export interface OAuthConfig {
  authorizationEndpoint: string;
  tokenEndpoint: string;
  introspectionEndpoint: string;
  revocationEndpoint: string;
  userInfoEndpoint: string;
  clientId: string;
  redirectUri: string;
  scope: string;
  responseType: 'code';
  codeChallengeMethod: 'S256';
  prompt?: 'none' | 'login' | 'consent' | 'select_account';
}

// Token storage interface
export interface TokenStorage {
  accessToken: string;
  refreshToken?: string;
  tokenType: string;
  expiresIn: number;
  expiresAt: number;
  scope: string;
}

// OAuth state interface
export interface OAuthState {
  state: string;
  codeVerifier: string;
  redirectUri: string;
  timestamp: number;
}

// User info interface
export interface UserInfo {
  sub: string;
  email?: string;
  name?: string;
  picture?: string;
  agency_id?: string;
  roles?: string[];
  permissions?: string[];
}

// Error response interface
export interface OAuthError {
  error: string;
  error_description?: string;
  error_uri?: string;
}

/**
 * OAuth2.0 Service Class
 */
export class OAuthService {
  private config: OAuthConfig;
  private axiosInstance: AxiosInstance;
  private refreshPromise: Promise<TokenStorage> | null = null;
  private tokenRefreshSubscribers: Array<(token: string) => void> = [];

  constructor(config: Partial<OAuthConfig>) {
    this.config = {
      authorizationEndpoint: config.authorizationEndpoint || '/api/v1/oauth/authorize',
      tokenEndpoint: config.tokenEndpoint || '/api/v1/oauth/token',
      introspectionEndpoint: config.introspectionEndpoint || '/api/v1/oauth/introspect',
      revocationEndpoint: config.revocationEndpoint || '/api/v1/oauth/revoke',
      userInfoEndpoint: config.userInfoEndpoint || '/api/v1/oauth/userinfo',
      clientId: config.clientId || process.env.REACT_APP_OAUTH_CLIENT_ID || '',
      redirectUri: config.redirectUri || `${window.location.origin}/auth/callback`,
      scope: config.scope || 'read write',
      responseType: 'code',
      codeChallengeMethod: 'S256',
      prompt: config.prompt,
    };

    // Create axios instance with interceptors
    this.axiosInstance = axios.create({
      baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
      withCredentials: true,
    });

    this.setupInterceptors();
  }

  /**
   * Setup axios interceptors for token management
   */
  private setupInterceptors(): void {
    // Request interceptor to add token
    this.axiosInstance.interceptors.request.use(
      (config) => {
        const token = this.getStoredToken();
        if (token && config.headers) {
          config.headers.Authorization = `Bearer ${token.accessToken}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor to handle token refresh
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            const newToken = await this.refreshAccessToken();
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${newToken.accessToken}`;
            }
            return this.axiosInstance(originalRequest);
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

  /**
   * Generate PKCE challenge and verifier
   */
  private async generatePKCE(): Promise<{ codeVerifier: string; codeChallenge: string }> {
    // Generate code verifier
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    const codeVerifier = this.base64URLEncode(array);

    // Generate code challenge
    const encoder = new TextEncoder();
    const data = encoder.encode(codeVerifier);
    const digest = await crypto.subtle.digest('SHA-256', data);
    const codeChallenge = this.base64URLEncode(new Uint8Array(digest));

    return { codeVerifier, codeChallenge };
  }

  /**
   * Base64 URL encode
   */
  private base64URLEncode(buffer: Uint8Array): string {
    const base64 = btoa(String.fromCharCode(...buffer));
    return base64
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');
  }

  /**
   * Generate random state
   */
  private generateState(): string {
    const array = new Uint8Array(16);
    crypto.getRandomValues(array);
    return this.base64URLEncode(array);
  }

  /**
   * Build authorization URL
   */
  public async buildAuthorizationUrl(additionalParams?: Record<string, string>): Promise<string> {
    const { codeVerifier, codeChallenge } = await this.generatePKCE();
    const state = this.generateState();

    // Store OAuth state
    const oauthState: OAuthState = {
      state,
      codeVerifier,
      redirectUri: this.config.redirectUri,
      timestamp: Date.now(),
    };
    sessionStorage.setItem('oauth_state', JSON.stringify(oauthState));

    // Build authorization URL
    const params = new URLSearchParams({
      response_type: this.config.responseType,
      client_id: this.config.clientId,
      redirect_uri: this.config.redirectUri,
      scope: this.config.scope,
      state,
      code_challenge: codeChallenge,
      code_challenge_method: this.config.codeChallengeMethod,
      ...(this.config.prompt && { prompt: this.config.prompt }),
      ...additionalParams,
    });

    return `${this.config.authorizationEndpoint}?${params.toString()}`;
  }

  /**
   * Initiate OAuth flow
   */
  public async initiateOAuthFlow(additionalParams?: Record<string, string>): Promise<void> {
    const authUrl = await this.buildAuthorizationUrl(additionalParams);
    window.location.href = authUrl;
  }

  /**
   * Handle OAuth callback
   */
  public async handleOAuthCallback(
    code: string,
    state: string
  ): Promise<TokenStorage> {
    // Retrieve and validate state
    const storedStateStr = sessionStorage.getItem('oauth_state');
    if (!storedStateStr) {
      throw new Error('No OAuth state found');
    }

    const storedState: OAuthState = JSON.parse(storedStateStr);
    
    // Validate state parameter
    if (state !== storedState.state) {
      throw new Error('Invalid state parameter');
    }

    // Check state expiration (5 minutes)
    if (Date.now() - storedState.timestamp > 5 * 60 * 1000) {
      throw new Error('OAuth state expired');
    }

    // Exchange code for tokens
    const tokens = await this.exchangeCodeForTokens(
      code,
      storedState.codeVerifier,
      storedState.redirectUri
    );

    // Clear OAuth state
    sessionStorage.removeItem('oauth_state');

    // Store tokens
    this.storeTokens(tokens);

    return tokens;
  }

  /**
   * Exchange authorization code for tokens
   */
  private async exchangeCodeForTokens(
    code: string,
    codeVerifier: string,
    redirectUri: string
  ): Promise<TokenStorage> {
    const params = new URLSearchParams({
      grant_type: 'authorization_code',
      code,
      redirect_uri: redirectUri,
      client_id: this.config.clientId,
      client_secret: 'demo_secret', // For demo purposes
      code_verifier: codeVerifier,
    });

    try {
      const response = await this.axiosInstance.post(
        this.config.tokenEndpoint,
        params.toString(),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );

      const { access_token, refresh_token, token_type, expires_in, scope } = response.data;

      return {
        accessToken: access_token,
        refreshToken: refresh_token,
        tokenType: token_type,
        expiresIn: expires_in,
        expiresAt: Date.now() + expires_in * 1000,
        scope: scope || this.config.scope,
      };
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data) {
        const oauthError = error.response.data as OAuthError;
        throw new Error(oauthError.error_description || oauthError.error);
      }
      throw error;
    }
  }

  /**
   * Refresh access token
   */
  public async refreshAccessToken(): Promise<TokenStorage> {
    // Prevent multiple simultaneous refresh requests
    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    const storedToken = this.getStoredToken();
    if (!storedToken?.refreshToken) {
      throw new Error('No refresh token available');
    }

    this.refreshPromise = this.performTokenRefresh(storedToken.refreshToken);

    try {
      const newToken = await this.refreshPromise;
      this.storeTokens(newToken);
      this.notifyTokenRefreshSubscribers(newToken.accessToken);
      return newToken;
    } finally {
      this.refreshPromise = null;
    }
  }

  /**
   * Perform token refresh
   */
  private async performTokenRefresh(refreshToken: string): Promise<TokenStorage> {
    const params = new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: refreshToken,
      client_id: this.config.clientId,
    });

    try {
      const response = await this.axiosInstance.post(
        this.config.tokenEndpoint,
        params.toString(),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );

      const { access_token, refresh_token, token_type, expires_in, scope } = response.data;

      return {
        accessToken: access_token,
        refreshToken: refresh_token || refreshToken, // Keep old refresh token if not provided
        tokenType: token_type,
        expiresIn: expires_in,
        expiresAt: Date.now() + expires_in * 1000,
        scope: scope || this.config.scope,
      };
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data) {
        const oauthError = error.response.data as OAuthError;
        throw new Error(oauthError.error_description || oauthError.error);
      }
      throw error;
    }
  }

  /**
   * Subscribe to token refresh
   */
  public subscribeToTokenRefresh(callback: (token: string) => void): () => void {
    this.tokenRefreshSubscribers.push(callback);
    return () => {
      this.tokenRefreshSubscribers = this.tokenRefreshSubscribers.filter(
        (sub) => sub !== callback
      );
    };
  }

  /**
   * Notify token refresh subscribers
   */
  private notifyTokenRefreshSubscribers(token: string): void {
    this.tokenRefreshSubscribers.forEach((callback) => callback(token));
  }

  /**
   * Revoke tokens
   */
  public async revokeTokens(): Promise<void> {
    const storedToken = this.getStoredToken();
    if (!storedToken) {
      return;
    }

    // Revoke refresh token first (if available)
    if (storedToken.refreshToken) {
      await this.revokeToken(storedToken.refreshToken, 'refresh_token');
    }

    // Then revoke access token
    await this.revokeToken(storedToken.accessToken, 'access_token');

    // Clear stored tokens
    this.clearTokens();
  }

  /**
   * Revoke a specific token
   */
  private async revokeToken(token: string, tokenType: string): Promise<void> {
    const params = new URLSearchParams({
      token,
      token_type_hint: tokenType,
      client_id: this.config.clientId,
    });

    try {
      await this.axiosInstance.post(
        this.config.revocationEndpoint,
        params.toString(),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );
    } catch (error) {
      // Revocation endpoint should not return errors
      console.error('Token revocation failed:', error);
    }
  }

  /**
   * Introspect token
   */
  public async introspectToken(token?: string): Promise<any> {
    const tokenToIntrospect = token || this.getStoredToken()?.accessToken;
    if (!tokenToIntrospect) {
      throw new Error('No token to introspect');
    }

    const params = new URLSearchParams({
      token: tokenToIntrospect,
      token_type_hint: 'access_token',
      client_id: this.config.clientId,
    });

    try {
      const response = await this.axiosInstance.post(
        this.config.introspectionEndpoint,
        params.toString(),
        {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
        }
      );

      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.data) {
        throw error.response.data;
      }
      throw error;
    }
  }

  /**
   * Get user info
   */
  public async getUserInfo(): Promise<UserInfo> {
    const response = await this.axiosInstance.get(this.config.userInfoEndpoint);
    return response.data;
  }

  /**
   * Store tokens
   */
  private storeTokens(tokens: TokenStorage): void {
    localStorage.setItem('oauth_tokens', JSON.stringify(tokens));
  }

  /**
   * Get stored token
   */
  public getStoredToken(): TokenStorage | null {
    const tokensStr = localStorage.getItem('oauth_tokens');
    if (!tokensStr) {
      return null;
    }

    try {
      const tokens: TokenStorage = JSON.parse(tokensStr);
      
      // Check if token is expired
      if (tokens.expiresAt && Date.now() >= tokens.expiresAt) {
        // Token expired, try to refresh
        if (tokens.refreshToken) {
          // Will be handled by interceptor
          return tokens;
        }
        // No refresh token, clear tokens
        this.clearTokens();
        return null;
      }

      return tokens;
    } catch (error) {
      console.error('Failed to parse stored tokens:', error);
      this.clearTokens();
      return null;
    }
  }

  /**
   * Clear stored tokens
   */
  public clearTokens(): void {
    localStorage.removeItem('oauth_tokens');
    sessionStorage.removeItem('oauth_state');
  }

  /**
   * Check if user is authenticated
   */
  public isAuthenticated(): boolean {
    const token = this.getStoredToken();
    return !!token && Date.now() < token.expiresAt;
  }

  /**
   * Get axios instance for API calls
   */
  public getAxiosInstance(): AxiosInstance {
    return this.axiosInstance;
  }
}

// Create default instance
export const oauthService = new OAuthService({
  clientId: process.env.REACT_APP_OAUTH_CLIENT_ID || 'demo_client',
  redirectUri: `${window.location.origin}/callback`,
});

// Export for use in other services
export default oauthService;