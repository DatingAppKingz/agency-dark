/**
 * Webhook Types
 */

export enum WebhookEvent {
  // Message events
  MESSAGE_RECEIVED = 'message.received',
  MESSAGE_SENT = 'message.sent',
  MESSAGE_READ = 'message.read',
  
  // Fan events
  FAN_SUBSCRIBED = 'fan.subscribed',
  FAN_UNSUBSCRIBED = 'fan.unsubscribed',
  FAN_UPDATED = 'fan.updated',
  
  // Payment events
  PAYMENT_RECEIVED = 'payment.received',
  PAYMENT_FAILED = 'payment.failed',
  PAYMENT_REFUNDED = 'payment.refunded',
  
  // Model events
  MODEL_ONLINE = 'model.online',
  MODEL_OFFLINE = 'model.offline',
  MODEL_UPDATED = 'model.updated',
  
  // Analytics events
  DAILY_SUMMARY = 'analytics.daily_summary',
  MILESTONE_REACHED = 'analytics.milestone',
}

export enum DeliveryStatus {
  PENDING = 'pending',
  SUCCESS = 'success',
  FAILED = 'failed',
  RETRYING = 'retrying',
}

export interface WebhookCreate {
  url: string;
  events: WebhookEvent[];
  description?: string;
  is_active?: boolean;
  retry_enabled?: boolean;
  max_retries?: number;
  timeout_seconds?: number;
  custom_headers?: Record<string, string>;
}

export interface WebhookUpdate {
  url?: string;
  events?: WebhookEvent[];
  description?: string;
  is_active?: boolean;
  retry_enabled?: boolean;
  max_retries?: number;
  timeout_seconds?: number;
  custom_headers?: Record<string, string>;
}

export interface WebhookResponse {
  id: string;
  url: string;
  events: string[];
  description?: string;
  is_active: boolean;
  retry_enabled: boolean;
  max_retries: number;
  timeout_seconds: number;
  custom_headers: Record<string, string>;
  
  // Statistics
  total_deliveries: number;
  successful_deliveries: number;
  failed_deliveries: number;
  success_rate: number;
  last_delivery_at?: string;
  last_success_at?: string;
  last_failure_at?: string;
  
  created_at: string;
  updated_at: string;
}

export interface WebhookDelivery {
  id: string;
  webhook_id: string;
  event_type: string;
  event_id: string;
  status: DeliveryStatus;
  attempts: number;
  response_status_code?: number;
  response_time_ms?: number;
  error_message?: string;
  created_at: string;
  delivered_at?: string;
}

export interface WebhookDeadLetter {
  id: string;
  webhook_id: string;
  event_type: string;
  event_id: string;
  payload: any;
  final_status_code?: number;
  total_attempts: number;
  first_attempt_at: string;
  last_attempt_at: string;
  error_summary: string;
  is_reprocessed: boolean;
  reprocessed_at?: string;
  created_at: string;
  expires_at: string;
}

export interface WebhookPayload {
  event: WebhookEvent;
  event_id: string;
  timestamp: string;
  data: any;
}

export interface WebhookTestResult {
  success: boolean;
  response_time_ms?: number;
  status_code?: number;
  message?: string;
  response?: any;
  error?: string;
}

export interface PaginatedWebhookDeadLetters {
  items: WebhookDeadLetter[];
  total: number;
  page: number;
  per_page: number;
}
