/**
 * API Key Types
 * 
 * Defines types for managing external API keys securely
 */

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string; // First 8 characters for display
  provider: ApiKeyProvider;
  scopes: string[];
  last_used: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
  is_active: boolean;
  created_by: string;
}

export enum ApiKeyProvider {
  INFLOW = 'inflow',
  ONLYFANS = 'onlyfans',
  STRIPE = 'stripe',
  PAYPAL = 'paypal',
  CUSTOM = 'custom'
}

export interface ApiKeyCreateRequest {
  name: string;
  provider: ApiKeyProvider;
  key: string;
  scopes: string[];
  expires_at?: string;
}

export interface ApiKeyUpdateRequest {
  name?: string;
  scopes?: string[];
  is_active?: boolean;
}

export interface ApiKeyRotateRequest {
  new_key: string;
}

export interface ApiKeyUsageStats {
  key_id: string;
  daily_usage: Array<{
    date: string;
    count: number;
    errors: number;
  }>;
  total_requests: number;
  total_errors: number;
  last_error: string | null;
  average_response_time: number;
}

export interface ApiKeyAuditLog {
  id: string;
  key_id: string;
  action: ApiKeyAction;
  user_id: string;
  user_email: string;
  ip_address: string;
  user_agent: string;
  metadata: Record<string, any>;
  created_at: string;
}

export enum ApiKeyAction {
  CREATED = 'created',
  VIEWED = 'viewed',
  UPDATED = 'updated',
  ROTATED = 'rotated',
  DELETED = 'deleted',
  USED = 'used',
  FAILED = 'failed'
}

export interface ApiKeyValidationResult {
  valid: boolean;
  provider: ApiKeyProvider;
  message?: string;
  scopes?: string[];
  rate_limits?: {
    requests_per_minute: number;
    requests_per_day: number;
  };
}

export interface ApiKeyListResponse {
  keys: ApiKey[];
  total: number;
  page: number;
  limit: number;
}

export interface ApiKeyFilters {
  provider?: ApiKeyProvider;
  is_active?: boolean;
  created_after?: string;
  created_before?: string;
  search?: string;
}
