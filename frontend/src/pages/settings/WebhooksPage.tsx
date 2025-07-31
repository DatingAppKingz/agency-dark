import React from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import { Webhook as WebhookIcon } from '@mui/icons-material';
import WebhookManager from '@/components/webhooks/WebhookManager';
import { useAuth } from '@/hooks/useAuth';

const WebhooksPage: React.FC = () => {
  const { user } = useAuth();

  // Check if user has permission to manage webhooks
  const canManageWebhooks = ['super_admin', 'agency_owner', 'agency_admin'].includes(user?.role || '');

  if (!canManageWebhooks) {
    return (
      <Container maxWidth="lg">
        <Box py={4}>
          <Alert severity="error">
            You don't have permission to manage webhooks.
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
          <WebhookIcon sx={{ fontSize: 40, color: 'primary.main' }} />
          <Box>
            <Typography variant="h4" gutterBottom>
              Webhook Configuration
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Configure webhooks to receive real-time notifications about events in your agency
            </Typography>
          </Box>
        </Box>

        {/* Info Alert */}
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>Webhook Information:</strong>
            <ul style={{ margin: '8px 0', paddingLeft: '20px' }}>
              <li>Webhooks allow you to receive real-time notifications when events occur</li>
              <li>Failed webhooks are automatically retried with exponential backoff</li>
              <li>All webhooks are signed for security - verify signatures on your server</li>
              <li>Dead letter queue stores failed webhooks for manual reprocessing</li>
            </ul>
          </Typography>
        </Alert>

        {/* Webhook Manager */}
        <Paper elevation={0}>
          <WebhookManager />
        </Paper>
      </Box>
    </Container>
  );
};

export default WebhooksPage;
