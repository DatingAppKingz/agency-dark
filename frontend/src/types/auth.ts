export enum UserRole {
  SUPER_ADMIN = 'super_admin',
  AGENCY_OWNER = 'agency_owner',
  AGENCY_ADMIN = 'agency_admin',
  MODEL = 'model',
  CHATTER = 'chatter',
  AGENCY_MEMBER = 'agency_member',
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  agency_id?: string;
  is_active: boolean;
  is_verified?: boolean;
  created_at: string;
  verified_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  full_name: string;
  agency_name?: string;
}
