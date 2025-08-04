export enum ModelStatus {
  PENDING = 'pending',
  UNDER_REVIEW = 'under_review',
  ACTIVE = 'active',
  PAUSED = 'paused',
  INACTIVE = 'inactive',
  BANNED = 'banned',
  REJECTED = 'rejected',
  DELETED = 'deleted',
}

export enum Platform {
  ONLYFANS = 'onlyfans',
  FANSLY = 'fansly',
  FANVUE = 'fanvue',
  CUSTOM = 'custom',
}

export interface ModelProfile {
  id: string;
  user_id: string;
  agency_id: string;
  stage_name: string;
  real_name?: string;
  bio?: string;
  profile_photo_url?: string;
  avatar_url?: string; // Alias for backward compatibility
  cover_photo_url?: string;
  cover_image_url?: string; // Alias for backward compatibility
  platform: Platform;
  platform_username: string;
  platform_url?: string;
  status: ModelStatus;
  verification_status: string;
  verified_at?: string;
  subscription_price: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  
  // Approval workflow
  reviewed_by?: string;
  reviewed_at?: string;
  rejection_reason?: string;
  admin_notes?: string;
  id_document_url?: string;
  
  // Additional fields
  email?: string;
  phone?: string;
  categories?: string[];
  tags?: string[];
  languages?: string[];
  chat_enabled?: boolean;
  commission_rate?: number;
  
  // Relations
  user?: {
    id: string;
    email: string;
    full_name: string;
  };
  
  // Stats
  total_fans?: number;
  total_earnings?: number;
  active_chats?: number;
}

export interface ModelContent {
  id: string;
  model_id: string;
  type: 'image' | 'video' | 'audio';
  url: string;
  thumbnail_url?: string;
  title?: string;
  description?: string;
  price: number;
  is_free: boolean;
  created_at: string;
}

export interface ModelAvailability {
  id: string;
  model_id: string;
  day_of_week: number; // 0-6 (Sunday-Saturday)
  start_time: string; // HH:MM format
  end_time: string; // HH:MM format
  timezone: string;
}

export interface ModelPreferences {
  id: string;
  model_id: string;
  auto_reply_enabled: boolean;
  welcome_message?: string;
  content_categories: string[];
  blocked_words: string[];
  min_tip_amount: number;
  chat_rate_per_minute?: number;
}

export interface ModelStats {
  model_id: string;
  period: 'day' | 'week' | 'month' | 'year';
  total_earnings: number;
  total_tips: number;
  total_messages: number;
  new_fans: number;
  lost_fans: number;
  conversion_rate: number;
  avg_response_time: number;
  top_earning_content: ModelContent[];
}

export interface CreateModelProfileData {
  user_id: string;
  stage_name: string;
  bio?: string;
  subscription_price: number;
  is_active?: boolean;
}

export interface UpdateModelProfileData {
  stage_name?: string;
  bio?: string;
  avatar_url?: string;
  cover_image_url?: string;
  subscription_price?: number;
  is_active?: boolean;
}
