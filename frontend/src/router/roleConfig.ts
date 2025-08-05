import { UserRole } from '@/types/auth';

// Define which roles can access which routes
export const routeRoles: Record<string, UserRole[]> = {
  // Everyone can access
  '/dashboard': undefined,
  '/dashboard/profile': undefined,
  '/dashboard/settings': undefined,
  
  // Super Admin only
  '/dashboard/agencies': [UserRole.SUPER_ADMIN],
  '/dashboard/admin/users': [UserRole.SUPER_ADMIN],
  
  // Agency management
  '/dashboard/agency': [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  
  // User management - Agency Owners and Admins only
  '/dashboard/users': [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  
  // Model overview - specific roles
  '/dashboard/models': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  '/dashboard/models/:modelId': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  '/dashboard/models/pending': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  '/dashboard/models/onboarding': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  
  // Chat - Models and Chatters only
  '/dashboard/chat': [UserRole.MODEL, UserRole.CHATTER],
  
  // Analytics - Everyone except basic members
  '/dashboard/analytics': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL, UserRole.CHATTER],
  '/dashboard/ml-insights': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  
  // Financial - Owners, Admins, and Models
  '/dashboard/financial': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  '/dashboard/financial/payouts': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  '/dashboard/financial/transactions': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  
  // Settings - specific access
  '/dashboard/settings/api-keys': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER],
  '/dashboard/settings/webhooks': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER],
  
  // Bulk operations - Admins only
  '/dashboard/bulk-operations': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  
  // Sync - Management roles
  '/dashboard/sync': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  
  // Reports - Everyone except basic members
  '/dashboard/reports': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL, UserRole.CHATTER],
  '/dashboard/reports/builder': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  '/dashboard/reports/builder/:templateId': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  '/dashboard/reports/view/:templateId': [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL, UserRole.CHATTER],
};

// Helper function to get allowed roles for a route
export function getAllowedRoles(path: string): UserRole[] | undefined {
  // Direct match
  if (routeRoles[path] !== undefined) {
    return routeRoles[path];
  }
  
  // Check for pattern matches (e.g., /dashboard/models/:modelId)
  for (const [pattern, roles] of Object.entries(routeRoles)) {
    if (pattern.includes(':')) {
      // Simple pattern matching - replace :param with regex
      const regexPattern = pattern.replace(/:[^/]+/g, '[^/]+');
      const regex = new RegExp(`^${regexPattern}$`);
      if (regex.test(path)) {
        return roles;
      }
    }
  }
  
  return undefined; // No restrictions
}