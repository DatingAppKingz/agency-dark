/**
 * Sync Types
 * 
 * Types for data synchronization with external platforms
 */

export enum SyncPlatform {
  INFLOW = 'inflow',
  ONLYFANS = 'onlyfans',
  ALL = 'all'
}

export enum SyncStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

export interface SyncRequest {
  model_id: string;
  platform: SyncPlatform;
  force_full_sync: boolean;
}

export interface SyncResponse {
  sync_id: string;
  model_id: string;
  status: SyncStatus;
  started_at: string;
  completed_at?: string;
  platforms: Record<string, {
    status: string;
    synced_items?: number;
    errors?: string[];
  }>;
  errors: Array<{
    platform: string;
    error: string;
  }>;
}

export interface SyncStatusResponse {
  model_id: string;
  status: SyncStatus;
  last_sync?: SyncResponse;
  next_sync?: string;
  platforms: Record<string, {
    configured: boolean;
    last_sync?: string;
    status: string;
  }>;
}

export interface SyncHistoryItem {
  sync_id: string;
  started_at: string;
  completed_at?: string;
  status: SyncStatus;
  platforms: Record<string, any>;
  errors: Array<{
    platform: string;
    error: string;
  }>;
}

export interface SyncStats {
  total_syncs_today: number;
  successful_syncs: number;
  failed_syncs: number;
  average_sync_duration: number;
  last_sync_time?: string;
  models_synced_today: number;
  total_records_synced: {
    subscribers: number;
    transactions: number;
    content: number;
    messages: number;
  };
}

export interface SyncScheduleRequest {
  model_id: string;
  platform: SyncPlatform;
  delay_minutes: number;
}

export interface SyncScheduleResponse {
  job_id: string;
  model_id: string;
  scheduled_for: string;
  platform: SyncPlatform;
}

export interface SyncOverviewResponse {
  total_api_keys: number;
  sync_enabled_keys: number;
  active_syncs: number;
  scheduled_syncs: number;
  failed_syncs_24h: number;
  successful_syncs_24h: number;
  average_sync_duration: number;
  last_sync_time?: string;
}

export interface ApiKeySyncStatusResponse {
  api_key_id: string;
  api_key_name: string;
  provider: string;
  sync_enabled: boolean;
  sync_interval_minutes: number;
  last_sync_at?: string;
  last_sync_status?: string;
  last_sync_error?: string;
  sync_failure_count: number;
  next_sync_at?: string;
  is_syncing: boolean;
}

export interface SyncHealthResponse {
  status: 'healthy' | 'warning' | 'critical';
  scheduler_running: boolean;
  active_workers: number;
  queue_size: number;
  failed_syncs_1h: number;
  failed_syncs_24h: number;
  avg_sync_duration_minutes: number;
  problematic_keys: Array<{
    api_key_id: string;
    name: string;
    provider: string;
    failure_count: number;
    last_error?: string;
  }>;
}

export interface DeltaSyncStateResponse {
  service_name: string;
  last_sync_at?: string;
  last_successful_sync_at?: string;
  last_full_sync_at?: string;
  is_initial_sync: boolean;
  total_synced: number;
  consecutive_failures: number;
  checksum_cache_size: number;
}
