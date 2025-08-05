export enum UserRole {
  SUPER_ADMIN = 'super_admin',
  AGENCY_OWNER = 'agency_owner',
  AGENCY_ADMIN = 'agency_admin',
  AGENCY_STAFF = 'agency_staff',
  MODEL = 'model',
  CHATTER = 'chatter',
  AGENCY_MEMBER = 'agency_member',
}

// Helper function to normalize role strings from backend
export function normalizeRole(role: string): string {
  // Convert UPPER_CASE to lower_case
  return role.toLowerCase();
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole | string;  // Accept both enum values and string for compatibility
  agency_id: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  verified_at?: string;
  assigned_model_ids?: string[];
  impersonating_agency_id?: string;
  first_name?: string;
  last_name?: string;
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
