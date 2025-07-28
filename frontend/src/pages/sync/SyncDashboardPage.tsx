import React from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import { CloudSync as CloudSyncIcon } from '@mui/icons-material';
import SyncStatusDashboard from '@/components/sync/SyncStatusDashboard';
import { useAuth } from '@/hooks/useAuth';

const SyncDashboardPage: React.FC = () => {
  const { user } = useAuth();

  // Check if user has permission to view sync dashboard
  const canViewSync = ['super_admin', 'agency_owner', 'agency_admin', 'model'].includes(user?.role || '');

  if (!canViewSync) {
    return (
      <Container maxWidth="lg">
        <Box py={4}>
          <Alert severity="error">
            You don't have permission to view the sync dashboard.
          </Alert>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl">
      <Box py={4}>
        {/* Header */}
        <Box display="flex" alignItems="center" gap={2} mb={4}>
          <CloudSyncIcon sx={{ fontSize: 40, color: 'primary.main' }} />
          <Box>
            <Typography variant="h4" gutterBottom>
              Data Sync Dashboard
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Monitor and manage data synchronization with external platforms
            </Typography>
          </Box>
        </Box>

        {/* Info Alert */}
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>Sync Information:</strong>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>Data syncs automatically every 15 minutes for active models</li>
              <li>You can trigger manual syncs at any time</li>
              <li>Full sync forces a complete data refresh (use sparingly)</li>
              <li>Check sync history to troubleshoot any issues</li>
            </ul>
          </Typography>
        </Alert>

        {/* Sync Dashboard */}
        <Paper elevation={0}>
          <SyncStatusDashboard 
            agencyId={user?.role === 'super_admin' ? undefined : user?.agency_id}
          />
        </Paper>
      </Box>
    </Container>
  );
};

export default SyncDashboardPage;