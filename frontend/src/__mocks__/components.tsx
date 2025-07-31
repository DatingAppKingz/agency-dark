// Mock components for testing
import React from 'react';

interface PermissionGateProps {
  permission?: string;
  permissions?: string[];
  requireAll?: boolean;
  children: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({ 
  permission, 
  permissions, 
  requireAll = true, 
  children 
}) => {
  const mockPermissions = (window as { mockPermissions?: string[] }).mockPermissions || [];
  
  let hasPermission = false;
  if (permission) {
    hasPermission = mockPermissions.includes(permission) || mockPermissions.includes('*:*');
  } else if (permissions) {
    if (requireAll) {
      hasPermission = permissions.every(p => mockPermissions.includes(p) || mockPermissions.includes('*:*'));
    } else {
      hasPermission = permissions.some(p => mockPermissions.includes(p) || mockPermissions.includes('*:*'));
    }
  }
  
  return hasPermission ? <>{children}</> : null;
};

interface RoleGuardProps {
  roles: string[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({ roles, fallback, children }) => {
  const mockRole = (window as { mockUserRole?: string }).mockUserRole || 'AGENCY_ADMIN';
  const hasRole = roles.includes(mockRole);
  
  if (!hasRole) {
    return fallback ? <>{fallback}</> : null;
  }
  
  return <>{children}</>;
};

export const AuthGuard: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const isAuthenticated = localStorage.getItem('access_token') !== null;
  return isAuthenticated ? <>{children}</> : null;
};
