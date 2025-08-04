import React from 'react';
import { Box, Container } from '@mui/material';
import { MLInsightsDashboard } from '@/components/ml/MLInsightsDashboard';
import { useAuthStore } from '@/store/authStore';
import { UserRole } from '@/types/auth';
import { Navigate } from 'react-router-dom';

export default function MLInsightsPage() {
  const { user } = useAuthStore();

  // Check if user has permission to view ML insights
  const hasPermission = user && [
    UserRole.SUPER_ADMIN,
    UserRole.AGENCY_OWNER,
    UserRole.AGENCY_ADMIN
  ].includes(user.role);

  if (!hasPermission) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 3 }}>
        <MLInsightsDashboard />
      </Box>
    </Container>
  );
}