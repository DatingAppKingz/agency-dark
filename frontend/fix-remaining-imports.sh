#!/bin/bash

# Fix remaining import issues
echo "Fixing remaining import issues..."

# Remove references to non-existent mocks
find tests -name "*.ts*" -type f -exec sed -i '' \
  -e '/import.*__mocks__\/components/d' \
  -e '/import.*__mocks__\/store-mocks/d' \
  -e '/import.*AuthGuard.*__mocks__/d' \
  -e '/import.*PermissionGate.*__mocks__/d' \
  -e '/import.*RoleGuard.*__mocks__/d' \
  -e '/import.*mockAuthStore.*__tests__/d' \
  {} +

# Fix the LoginPage and other page imports
find tests -name "*.ts*" -type f -exec sed -i '' \
  -e 's|import { LoginPage, RegisterPage } from '\''@/pages'\'';|import LoginPage from '\''@/pages/auth/LoginPage'\''; import RegisterPage from '\''@/pages/auth/RegisterPage'\'';|g' \
  -e 's|import { ModelsPage, UsersPage, AnalyticsPage } from '\''@/pages'\'';|import ModelsPage from '\''@/pages/models/ModelsPage'\''; import UsersPage from '\''@/pages/users/UsersPage'\''; import AnalyticsPage from '\''@/pages/analytics/AnalyticsPage'\'';|g' \
  -e 's|import { LoginPage } from '\''@/pages/auth/LoginPage'\'';|import LoginPage from '\''@/pages/auth/LoginPage'\'';|g' \
  -e 's|import { DashboardPage } from '\''@/pages/dashboard/DashboardPage'\'';|import DashboardPage from '\''@/pages/dashboard/DashboardPage'\'';|g' \
  {} +

# Create a simple mock for missing components
cat > tests/utils/component-mocks.tsx << 'EOF'
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
EOF

echo "Import fixes completed!"