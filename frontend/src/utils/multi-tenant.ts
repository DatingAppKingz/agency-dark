import { User } from '@/types/auth';

interface FilterOptions {
  includeGlobal?: boolean;
}

/**
 * Filter data by agency based on user's role and agency
 */
export function filterByAgency<T extends { agency_id: string | null }>(
  data: T[],
  user: User | null,
  options: FilterOptions = {}
): T[] {
  if (!user) return [];

  // Super admin sees all data unless impersonating
  if (user.role === 'super_admin' && !user.impersonating_agency_id) {
    return data;
  }

  // Determine effective agency ID
  const effectiveAgencyId = user.impersonating_agency_id || user.agency_id;
  
  if (!effectiveAgencyId) {
    // User has no agency context, only return global resources if allowed
    return options.includeGlobal ? data.filter(item => item.agency_id === null) : [];
  }

  // Filter by agency
  return data.filter(item => {
    if (item.agency_id === effectiveAgencyId) return true;
    if (options.includeGlobal && item.agency_id === null) return true;
    return false;
  });
}

/**
 * Validate if user can access a specific agency context
 */
export function validateAgencyContext(
  user: User | null,
  targetAgencyId: string
): boolean {
  if (!user) return false;

  // Super admin can access any agency
  if (user.role === 'super_admin' && !user.impersonating_agency_id) {
    return true;
  }

  // Check effective agency ID
  const effectiveAgencyId = user.impersonating_agency_id || user.agency_id;
  return effectiveAgencyId === targetAgencyId;
}

/**
 * Check if user can access a specific resource
 */
export function canAccessResource(
  user: User | null,
  resourceType: 'model' | 'conversation' | 'earnings' | 'analytics',
  resourceId: string,
  resourceData?: { agency_id?: string | null }
): boolean {
  if (!user) return false;

  // Super admin can access everything (unless impersonating)
  if (user.role === 'super_admin' && !user.impersonating_agency_id) {
    return true;
  }

  switch (resourceType) {
    case 'model':
      // Chatters can only access assigned models
      if (user.role === 'chatter') {
        return user.assigned_model_ids?.includes(resourceId) || false;
      }
      
      // Agency roles can access all models in their agency
      if (resourceData?.agency_id) {
        return validateAgencyContext(user, resourceData.agency_id);
      }
      break;

    case 'earnings':
      // Models can only view their own earnings
      if (user.role === 'model') {
        return user.id === resourceId;
      }
      
      // Agency roles can view all earnings in their agency
      if (user.role === 'agency_owner' || user.role === 'agency_admin') {
        return true; // Would need additional check for agency context
      }
      break;

    case 'conversation':
      // Models can access their own conversations
      if (user.role === 'model') {
        return true; // Would need to check conversation.model_id
      }
      
      // Chatters can access assigned model conversations
      if (user.role === 'chatter') {
        return true; // Would need to check if conversation belongs to assigned model
      }
      
      // Agency roles can access all conversations in their agency
      break;

    case 'analytics':
      // Basic analytics access is role-based, handled by RBAC
      return true;
  }

  // Default: check agency context if available
  if (resourceData?.agency_id) {
    return validateAgencyContext(user, resourceData.agency_id);
  }

  return false;
}

/**
 * Get effective agency ID for the current user
 */
export function getEffectiveAgencyId(user: User | null): string | null {
  if (!user) return null;
  return user.impersonating_agency_id || user.agency_id;
}

/**
 * Check if user is currently impersonating
 */
export function isImpersonating(user: User | null): boolean {
  return !!user?.impersonating_agency_id;
}