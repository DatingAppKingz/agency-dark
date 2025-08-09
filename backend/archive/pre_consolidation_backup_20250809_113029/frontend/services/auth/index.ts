/**
 * Auth Service Export
 * Exports the appropriate auth service based on configuration
 */

// Check if we should use the new security_v2 backend
const USE_SECURITY_V2 = import.meta.env.VITE_USE_SECURITY_V2 === 'true' || false;

// Import both services
import { authService as authServiceOld } from './authService';
import authServiceV2 from './authServiceV2';

// Export the appropriate service
export const authService = USE_SECURITY_V2 ? authServiceV2 : authServiceOld;

// Also export default for compatibility
export default authService;

// Also export the specific services for testing
export { authServiceOld, authServiceV2 };

// Export a function to check which service is being used
export function isUsingSecurityV2(): boolean {
  return USE_SECURITY_V2;
}