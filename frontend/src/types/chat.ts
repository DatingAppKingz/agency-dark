export interface ChatUser {
  id: string;
  name: string;
  avatar_url?: string;
  is_online: boolean;
  last_seen?: string;
  subscription_tier?: string;
}

export enum MessageType {
  TEXT = 'text',
  VOICE = 'voice',
  IMAGE = 'image',
  VIDEO = 'video',
  FILE = 'file',
}

export enum MessageStatus {
  SENDING = 'sending',
  SENT = 'sent',
  DELIVERED = 'delivered',
  READ = 'read',
  FAILED = 'failed',
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_type: 'model' | 'fan' | 'chatter';
  content: string;
  message_type: MessageType;
  status?: MessageStatus;
  attachments?: MessageAttachment[];
  created_at: string;
  updated_at?: string;
  read_at?: string;
  delivered_at?: string;
  is_automated?: boolean;
  is_edited?: boolean;
  metadata?: Record<string, any>;
}

export interface MessageAttachment {
  id: string;
  type: 'image' | 'video' | 'audio' | 'file';
  url: string;
  thumbnail_url?: string;
  filename: string;
  size: number;
  duration?: number; // for audio/video
  mime_type?: string;
}

export interface ConversationParticipant {
  id: string;
  role: 'model' | 'fan' | 'chatter';
  name: string;
  avatar_url?: string;
  last_seen: string;
  is_online: boolean;
}

export interface Conversation {
  id: string;
  participants: ConversationParticipant[];
  last_message?: {
    id: string;
    content: string;
    sender_id: string;
    created_at: string;
  };
  unread_count: number;
  is_pinned: boolean;
  is_muted: boolean;
  is_archived?: boolean;
  is_favorite?: boolean;
  created_at: string;
  updated_at: string;
  // Legacy fields for backward compatibility
  fan_id?: string;
  model_id?: string;
  assigned_chatter_id?: string;
  fan?: ChatUser;
  model?: ChatUser;
  assigned_chatter?: ChatUser;
}

export interface TypingStatus {
  user_id: string;
  conversation_id: string;
  is_typing: boolean;
}

export interface ChatFilters {
  search: string;
  status: 'all' | 'unread' | 'pinned' | 'archived';
  assigned_to: 'me' | 'all' | 'team' | 'unassigned';
  model_id?: string;
  subscription_tier?: string;
  tags?: string[];
}

export interface SendMessageData {
  conversation_id: string;
  content: string;
  attachments?: File[];
  // Properties for backend API
  fan_id?: string;
  text?: string;
  media_urls?: string[];
  price?: number;
  model_id?: string;
  sender_id?: string;
}

export interface NewMessage {
  conversation_id: string;
  content: string;
  message_type?: 'text' | 'voice' | 'image' | 'video';
  attachments?: MessageAttachment[];
}

export interface ChatStats {
  total_conversations: number;
  unread_messages: number;
  active_chats: number;
  avg_response_time: number;
}
