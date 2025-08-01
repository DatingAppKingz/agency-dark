export enum MediaType {
  IMAGE = 'image',
  VIDEO = 'video',
  AUDIO = 'audio',
  DOCUMENT = 'document',
  OTHER = 'other'
}

export enum MediaStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  READY = 'ready',
  FAILED = 'failed',
  DELETED = 'deleted'
}

export enum MediaVisibility {
  PRIVATE = 'private',
  AGENCY = 'agency',
  MODEL = 'model',
  PUBLIC = 'public'
}

export interface Media {
  id: string;
  filename: string;
  original_filename: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  file_hash?: string;
  media_type: MediaType;
  width?: number;
  height?: number;
  duration?: number;
  status: MediaStatus;
  processing_error?: string;
  cdn_url?: string;
  thumbnail_url?: string;
  optimized_versions?: Record<string, string>;
  folder_id?: string;
  tags: string[];
  visibility: MediaVisibility;
  password_protected: boolean;
  agency_id: string;
  model_id?: string;
  uploaded_by: string;
  is_nsfw: boolean;
  moderation_status?: string;
  moderation_labels?: string[];
  view_count: number;
  download_count: number;
  last_accessed_at?: string;
  title?: string;
  description?: string;
  alt_text?: string;
  copyright_info?: string;
  exif_data?: Record<string, any>;
  custom_metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
  deleted_at?: string;
}

export interface MediaFolder {
  id: string;
  name: string;
  description?: string;
  parent_id?: string;
  agency_id: string;
  model_id?: string;
  created_by: string;
  is_public: boolean;
  color?: string;
  icon?: string;
  created_at: string;
  updated_at: string;
  media_count?: number;
}

export interface MediaShare {
  id: string;
  media_id: string;
  share_token: string;
  share_url?: string;
  expires_at?: string;
  max_views?: number;
  current_views: number;
  password_protected: boolean;
  allow_download: boolean;
  allow_embed: boolean;
  created_by: string;
  created_at: string;
  last_accessed_at?: string;
  is_expired?: boolean;
}

export interface MediaSearchParams {
  query?: string;
  media_type?: MediaType;
  folder_id?: string;
  visibility?: MediaVisibility;
  status?: MediaStatus;
  tags?: string[];
  search?: string;
  sort_by?: 'created_at' | 'updated_at' | 'file_size' | 'title';
  sort_order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export interface MediaBulkOperation {
  media_ids: string[];
  action: 'delete' | 'move' | 'update_visibility' | 'add_tags' | 'remove_tags';
  data: Record<string, any>;
}

export interface MediaUploadResponse {
  media: Media;
  upload_url?: string;
  presigned_url?: string;
}

export interface MediaListResponse {
  items: Media[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface MediaAnalytics {
  total_files: number;
  total_size: number;
  size_by_type: Record<MediaType, number>;
  count_by_type: Record<MediaType, number>;
  uploads_by_day: Array<{
    date: string;
    count: number;
    size: number;
  }>;
  popular_tags: Array<{
    tag: string;
    count: number;
  }>;
  top_viewed: Media[];
  top_downloaded: Media[];
}