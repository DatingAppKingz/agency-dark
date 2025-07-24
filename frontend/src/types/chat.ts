export interface ChatUser {
  id: string;
  name: string;
  avatar_url?: string;
  is_online: boolean;
  last_seen?: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_type: 'model' | 'fan' | 'chatter';
  content: string;
  attachments?: MessageAttachment[];
  created_at: string;
  read_at?: string;
  delivered_at?: string;
  is_automated?: boolean;
}

export interface MessageAttachment {
  id: string;
  type: 'image' | 'video' | 'audio' | 'file';
  url: string;
  thumbnail_url?: string;
  filename: string;
  size: number;
  duration?: number; // for audio/video
}

export interface Conversation {
  id: string;
  fan_id: string;
  model_id: string;
  assigned_chatter_id?: string;
  fan: ChatUser;
  model: ChatUser;
  assigned_chatter?: ChatUser;
  last_message?: Message;
  unread_count: number;
  is_pinned: boolean;
  is_archived: boolean;
  is_favorite: boolean;
  created_at: string;
  updated_at: string;
}

export interface TypingStatus {
  conversation_id: string;
  user_id: string;
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
}

export interface NewMessage {
  conversation_id: string;
  content: string;
  attachments?: any[];
}

export interface ChatStats {
  total_conversations: number;
  unread_messages: number;
  active_chats: number;
  avg_response_time: number;
}