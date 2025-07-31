/**
 * Bulk Operations Types
 */

export enum BulkOperationType {
  // User operations
  USER_UPDATE = 'user_update',
  USER_DELETE = 'user_delete',
  USER_ACTIVATE = 'user_activate',
  USER_DEACTIVATE = 'user_deactivate',
  USER_CREATE = 'user_create',
  USER_EXPORT = 'user_export',
  
  // Model operations
  MODEL_UPDATE = 'model_update',
  MODEL_ASSIGN = 'model_assign',
  
  // Transaction operations
  TRANSACTION_EXPORT = 'transaction_export',
  TRANSACTION_RECONCILE = 'transaction_reconcile',
  
  // Payout operations
  PAYOUT_SCHEDULE = 'payout_schedule',
  PAYOUT_CANCEL = 'payout_cancel',
  
  // Message operations
  MESSAGE_SEND = 'message_send',
  MESSAGE_DELETE = 'message_delete',
  
  // Content operations
  CONTENT_UPLOAD = 'content_upload',
  CONTENT_DELETE = 'content_delete',
  CONTENT_PUBLISH = 'content_publish',
  
  // Analytics operations
  ANALYTICS_EXPORT = 'analytics_export',
  
  // Data operations
  DATA_IMPORT = 'data_import',
  DATA_EXPORT = 'data_export',
}

export enum BulkOperationStatus {
  PENDING = 'pending',
  VALIDATING = 'validating',
  SCHEDULED = 'scheduled',
  PROCESSING = 'processing',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  PARTIALLY_COMPLETED = 'partially_completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
  ROLLED_BACK = 'rolled_back',
}

export interface BulkOperationCreate {
  operation_type: BulkOperationType;
  entity_type: string;
  entity_ids: string[];
  operation_params?: Record<string, any>;
  validation_rules?: Record<string, any>;
  scheduled_at?: Date | string;
  notes?: string;
}

export interface BulkOperation {
  id: string;
  operation_type: BulkOperationType;
  status: BulkOperationStatus;
  entity_type: string;
  total_count: number;
  processed_count: number;
  success_count: number;
  failed_count: number;
  progress_percentage: number;
  progress_current?: number;
  progress_total?: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  scheduled_at?: string;
  created_by: string;
  notes?: string;
  error_message?: string;
  result_url?: string;
  operation_params?: Record<string, any>;
  validation_rules?: Record<string, any>;
  rollback_available: boolean;
  failed_items?: Array<{
    entity_id: string;
    error: string;
  }>;
}

export interface BulkOperationLog {
  id: string;
  operation_id: string;
  entity_id: string;
  action: string;
  status: 'success' | 'failed' | 'skipped';
  details?: Record<string, any>;
  error?: string;
  created_at: string;
}

export interface BulkOperationTemplate {
  id: string;
  name: string;
  description?: string;
  operation_type: BulkOperationType;
  entity_type: string;
  operation_params: Record<string, any>;
  validation_rules?: Record<string, any>;
  created_at: string;
  updated_at: string;
  is_public: boolean;
}

export interface BulkOperationSchedule {
  id: string;
  operation_id: string;
  scheduled_at: string;
  recurrence_pattern?: string;
  next_run?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface BulkOperationLimit {
  id: string;
  operation_type: BulkOperationType;
  entity_type: string;
  max_entities: number;
  time_window_hours: number;
  current_usage: number;
  reset_at: string;
}

export interface BulkOperationProgress {
  operation_id: string;
  status: BulkOperationStatus;
  progress_percentage: number;
  processed_count: number;
  success_count: number;
  failed_count: number;
  current_entity_id?: string;
  estimated_completion?: string;
  message?: string;
}

export interface BulkOperationStats {
  total_operations: number;
  total_items_processed: number;
  success_rate: number;
  average_processing_time: number;
  active_operations: number;
  operations_by_type: Record<BulkOperationType, number>;
  operations_by_status: Record<BulkOperationStatus, number>;
  recent_operations: BulkOperation[];
}

export interface PaginatedBulkOperations {
  items: BulkOperation[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}
