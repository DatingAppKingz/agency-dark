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
