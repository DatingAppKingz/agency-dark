import React from 'react';
import { useAuth } from '@/hooks/useAuth';
import SuperAdminApiKeysPage from './SuperAdminApiKeysPage';
import AgencyApiKeysPage from './AgencyApiKeysPage';
import { Box, Typography, Alert } from '@mui/material';

/**
 * API Keys Page Router
 * 
 * This component routes to the appropriate API keys management page
 * based on the user's role:
 * 
 * - Super Admin: Platform-wide API keys (email, payment, storage, etc.)
 * - Agency Owner/Admin: Agency-specific API keys (OnlyFans, Stripe, Inflow)
 * - Others: Access denied
 */
const ApiKeysPage = () => {
  const { user } = useAuth();

  // Super admin sees platform-wide API keys
  if (user?.role === 'super_admin') {
    return <SuperAdminApiKeysPage />;
  }

  // Agency owners and admins see agency-specific API keys
  if (user?.role === 'agency_owner' || user?.role === 'agency_admin') {
    return <AgencyApiKeysPage />;
  }

  // Models and chatters don't have access to API keys
  return (
    <Box p={3}>
      <Typography variant="h4" gutterBottom>
        API Keys
      </Typography>
      <Alert severity="error">
        <Typography>
          Access Denied: You don't have permission to manage API keys.
        </Typography>
      </Alert>
    </Box>
  );
};

export default ApiKeysPage;