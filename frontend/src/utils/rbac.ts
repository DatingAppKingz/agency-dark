import { User } from '@/types/auth';

// Helper functions for RBAC
export const hasPermission = (permissions: string[], permission: string): boolean => {
  return permissions.includes(permission) || permissions.includes('*:*');
};

export const hasAnyPermission = (permissions: string[], requiredPermissions: string[]): boolean => {
  return requiredPermissions.some(perm => hasPermission(permissions, perm));
};

export const hasAllPermissions = (permissions: string[], requiredPermissions: string[]): boolean => {
  return requiredPermissions.every(perm => hasPermission(permissions, perm));
};

export const hasRole = (user: User | null, roles: string[]): boolean => {
  if (!user) return false;
  return roles.includes(user.role);
};

// Permission types
export type Permission = 
  | 'users:read'
  | 'users:write'
  | 'agencies:manage'
  | 'agency:settings'
  | 'models:manage'
  | 'chat:access'
  | 'chat:manage_all'
  | 'chat:manage_assigned'
  | 'financial:view_all'
  | 'financial:view_agency'
  | 'financial:view_own'
  | 'financial:view_any'
  | 'analytics:view_all'
  | 'analytics:view_agency'
  | 'analytics:view_basic'
  | 'dashboard:view';

// Role permissions mapping
const rolePermissions: Record<User['role'], Permission[]> = {
  super_admin: [
    // Full system access
    'users:read',
    'users:write',
    'agencies:manage',
    'agency:settings',
    'models:manage',
    'chat:access',
    'chat:manage_all',
    'financial:view_all',
    'financial:view_agency',
    'financial:view_own',
    'analytics:view_all',
    'analytics:view_agency',
    'analytics:view_basic',
    'dashboard:view',
  ],
  agency_owner: [
    // Full agency access
    'agency:settings',
    'models:manage',
    'chat:access',
    'chat:manage_all',
    'financial:view_agency',
    'financial:view_own',
    'analytics:view_agency',
    'analytics:view_basic',
    'dashboard:view',
  ],
  agency_admin: [
    // Agency management
    'models:manage',
    'chat:access',
    'chat:manage_all',
    'financial:view_agency',
    'analytics:view_agency',
    'analytics:view_basic',
    'dashboard:view',
  ],
  model: [
    // Model-specific access
    'chat:access',
    'financial:view_own',
    'analytics:view_basic',
    'dashboard:view',
  ],
  chatter: [
    // Chat management
    'chat:access',
    'chat:manage_assigned',
    'analytics:view_basic',
    'dashboard:view',
  ],
  member: [
    // Basic access
    'analytics:view_basic',
    'dashboard:view',
  ],
};

export function hasPermission(user: User | null, permission: Permission): boolean {
  if (!user) return false;
  
  const userPermissions = rolePermissions[user.role] || [];
  return userPermissions.includes(permission);
}

export function hasAnyPermission(user: User | null, permissions: Permission[]): boolean {
  return permissions.some(permission => hasPermission(user, permission));
}

export function hasAllPermissions(user: User | null, permissions: Permission[]): boolean {
  return permissions.every(permission => hasPermission(user, permission));
}

export function canAccessRoute(user: User | null, route: string): boolean {
  if (!user) return false;

  const routePermissions: Record<string, Permission[]> = {
    '/users': ['users:read'],
    '/agencies': ['agencies:manage'],
    '/models': ['models:manage', 'chat:access'], // Either permission allows access
    '/chat': ['chat:access'],
    '/financial': ['financial:view_all', 'financial:view_agency', 'financial:view_own'],
    '/analytics': ['analytics:view_all', 'analytics:view_agency', 'analytics:view_basic'],
    '/settings': ['agency:settings'],
  };

  const requiredPermissions = routePermissions[route];
  if (!requiredPermissions) return true; // No restrictions

  return hasAnyPermission(user, requiredPermissions);
}