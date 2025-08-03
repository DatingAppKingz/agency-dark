import React from 'react';

export const AuthGuard = ({ children }: { children: React.ReactNode }) => {
  return <>{children}</>;
};

export const PermissionGate = ({ children }: { children: React.ReactNode }) => {
  return <>{children}</>;
};

export const RoleGuard = ({ children }: { children: React.ReactNode }) => {
  return <>{children}</>;
};

export const mockAuthStore = () => ({
  isAuthenticated: true,
  user: {
    id: '1',
    email: 'test@example.com',
    role: 'admin',
  },
});
