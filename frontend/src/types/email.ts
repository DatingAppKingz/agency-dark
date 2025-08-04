export enum EmailStatus {
  PENDING = 'pending',
  QUEUED = 'queued',
  SENT = 'sent',
  DELIVERED = 'delivered',
  OPENED = 'opened',
  CLICKED = 'clicked',
  BOUNCED = 'bounced',
  FAILED = 'failed',
  SCHEDULED = 'scheduled',
  CANCELLED = 'cancelled',
}

export interface EmailTemplate {
  id: string;
  name: string;
  subject: string;
  body_html: string;
  body_text: string;
  variables: string[];
  category: string;
  is_active: boolean;
  preview_text?: string;
  from_name?: string;
  from_email?: string;
  reply_to?: string;
  created_at: string;
  updated_at: string;
  used_count?: number;
  last_used_at?: string;
}

export interface EmailRecipient {
  email: string;
  name?: string;
  type: 'model' | 'fan' | 'agency' | 'admin';
  model_id?: string;
  fan_id?: string;
  agency_id?: string;
  variables?: Record<string, any>;
}

export interface EmailCampaign {
  id: string;
  name: string;
  template_id: string;
  status: 'draft' | 'active' | 'paused' | 'completed' | 'cancelled';
  audience_type: 'all_models' | 'active_models' | 'new_models' | 'custom';
  filters?: {
    min_earnings?: number;
    max_earnings?: number;
    joined_after?: string;
    joined_before?: string;
    has_active_subscriptions?: boolean;
    platform?: string[];
    tags?: string[];
  };
  scheduled_at: string | null;
  launched_at?: string;
  completed_at?: string;
  sent_count: number;
  delivered_count?: number;
  open_count: number;
  click_count: number;
  bounce_count?: number;
  unsubscribe_count?: number;
  created_at: string;
  updated_at: string;
}

export interface EmailSchedule {
  id: string;
  email_id?: string;
  campaign_id?: string;
  scheduled_for: string;
  status: 'pending' | 'sent' | 'cancelled' | 'failed';
  sent_at?: string;
  error?: string;
  created_at: string;
  updated_at: string;
}

export interface EmailTracking {
  id: string;
  email_id: string;
  recipient: string;
  status: EmailStatus;
  sent_at: string;
  delivered_at?: string;
  opened_at?: string;
  clicked_at?: string;
  bounced_at?: string;
  failed_at?: string;
  clicks?: Array<{
    url: string;
    clicked_at: string;
    user_agent?: string;
    ip_address?: string;
  }>;
  opens?: Array<{
    opened_at: string;
    user_agent?: string;
    ip_address?: string;
  }>;
  bounce_reason?: string;
  failure_reason?: string;
}

export interface EmailSubscriptionPreferences {
  model_id: string;
  marketing: boolean;
  notifications: boolean;
  weekly_digest: boolean;
  monthly_report: boolean;
  platform_updates?: boolean;
  earnings_alerts?: boolean;
  fan_messages?: boolean;
  updated_at: string;
}

export interface EmailAutomationFlow {
  id: string;
  name: string;
  trigger: 'model_signup' | 'first_earning' | 'inactive_7days' | 'milestone_reached' | 'custom';
  is_active: boolean;
  steps: Array<{
    id?: string;
    template_id: string;
    delay_hours: number;
    condition?: {
      field: string;
      operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains';
      value: any;
    };
  }>;
  created_at: string;
  updated_at: string;
  triggered_count?: number;
  completed_count?: number;
}

export interface SendEmailData {
  to: string | string[];
  subject: string;
  body_html: string;
  body_text?: string;
  from_name?: string;
  from_email?: string;
  reply_to?: string;
  cc?: string[];
  bcc?: string[];
  attachments?: Array<{
    filename: string;
    content: string; // Base64 encoded
    content_type: string;
  }>;
  headers?: Record<string, string>;
  metadata?: Record<string, any>;
}

export interface SendTemplateEmailData {
  to: string | string[];
  template_id: string;
  variables?: Record<string, any>;
  cc?: string[];
  bcc?: string[];
  attachments?: Array<{
    filename: string;
    content: string;
    content_type: string;
  }>;
  metadata?: Record<string, any>;
}

export interface BulkEmailData {
  template_id: string;
  recipients: EmailRecipient[];
  from_name?: string;
  from_email?: string;
  reply_to?: string;
  batch_size?: number;
  delay_between_batches?: number;
  metadata?: Record<string, any>;
}

export interface EmailAnalytics {
  sent_count: number;
  delivered_count: number;
  open_count: number;
  click_count: number;
  bounce_count: number;
  unsubscribe_count: number;
  spam_count?: number;
  open_rate: number;
  click_rate: number;
  bounce_rate: number;
  unsubscribe_rate?: number;
  delivery_rate?: number;
  engagement_score?: number;
  by_date?: Array<{
    date: string;
    sent: number;
    delivered: number;
    opened: number;
    clicked: number;
  }>;
  by_device?: {
    desktop: number;
    mobile: number;
    tablet: number;
  };
  top_links?: Array<{
    url: string;
    clicks: number;
    unique_clicks: number;
  }>;
}

export interface EmailSettings {
  default_from_name: string;
  default_from_email: string;
  default_reply_to: string;
  footer_text?: string;
  unsubscribe_url: string;
  branding?: {
    logo_url?: string;
    primary_color?: string;
    secondary_color?: string;
  };
  sending_limits?: {
    hourly_limit?: number;
    daily_limit?: number;
    monthly_limit?: number;
  };
  bounce_handling?: {
    soft_bounce_threshold?: number;
    hard_bounce_action?: 'disable' | 'flag';
  };
}