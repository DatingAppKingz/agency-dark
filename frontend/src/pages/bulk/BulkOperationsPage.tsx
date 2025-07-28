import React from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import { Group as GroupIcon } from '@mui/icons-material';
import BulkOperationsDashboard from '@/components/bulk/BulkOperationsDashboard';
import { useAuth } from '@/hooks/useAuth';

const BulkOperationsPage: React.FC = () => {
  const { user } = useAuth();

  // Check if user has permission to use bulk operations
  const canUseBulkOperations = ['super_admin', 'agency_owner', 'agency_admin'].includes(user?.role || '');

  if (!canUseBulkOperations) {
    return (
      <Container maxWidth="lg">
        <Box py={4}>
          <Alert severity="error">
            You don't have permission to use bulk operations.
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
          <GroupIcon sx={{ fontSize: 40, color: 'primary.main' }} />
          <Box>
            <Typography variant="h4" gutterBottom>
              Bulk Operations
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Manage multiple items at once with powerful bulk operations
            </Typography>
          </Box>
        </Box>

        {/* Bulk Operations Dashboard */}
        <Paper elevation={0}>
          <BulkOperationsDashboard />
        </Paper>
      </Box>
    </Container>
  );
};

export default BulkOperationsPage;