import { useState } from 'react';
import { Box, Typography, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { ViewModule, Dashboard } from '@mui/icons-material';
import { useAuthStore } from '@/store/authStore';
import { UserRole, normalizeRole } from '@/types/auth';
import { SuperAdminDashboard } from './SuperAdminDashboard';
import { AgencyOwnerDashboard } from './AgencyOwnerDashboard';
import { AgencyAdminDashboard } from './AgencyAdminDashboard';
import { ModelDashboard } from './ModelDashboard';
import { ChatterDashboard } from './ChatterDashboard';
import { MemberDashboard } from './MemberDashboard';
import { CustomizableDashboard } from '@/components/dashboard/CustomizableDashboard';
import { SEOHead } from '@/components/seo/SEOHead';

const DashboardPage = () => {
  const { user } = useAuthStore();
  const [viewMode, setViewMode] = useState<'classic' | 'custom'>('custom');
  const [editMode, setEditMode] = useState(false);

  if (!user) {
    return (
      <Box>
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  // Render role-specific dashboard
  const renderClassicDashboard = () => {
    // Normalize role to handle case differences from backend
    const normalizedRole = normalizeRole(user.role);
    
    switch (normalizedRole) {
      case UserRole.SUPER_ADMIN:
        return <SuperAdminDashboard />;
      case UserRole.AGENCY_OWNER:
        return <AgencyOwnerDashboard />;
      case UserRole.AGENCY_ADMIN:
        return <AgencyAdminDashboard />;
      case UserRole.MODEL:
        return <ModelDashboard />;
      case UserRole.CHATTER:
        return <ChatterDashboard />;
      case UserRole.AGENCY_MEMBER:
        return <MemberDashboard />;
      default:
        return (
          <Box>
            <Typography>Unknown role: {user.role} (normalized: {normalizedRole})</Typography>
          </Box>
        );
    }
  };

  return (
    <>
      <SEOHead
        title="Dashboard"
        description="Manage your OnlyFans agency operations, models, and chatters from a centralized dashboard"
        noindex={true}
      />
      
      {/* View mode toggle */}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={(_, newMode) => newMode && setViewMode(newMode)}
          size="small"
        >
          <ToggleButton value="classic">
            <ViewModule sx={{ mr: 1 }} />
            Classic View
          </ToggleButton>
          <ToggleButton value="custom">
            <Dashboard sx={{ mr: 1 }} />
            Custom View
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Render dashboard based on view mode */}
      {viewMode === 'classic' ? (
        renderClassicDashboard()
      ) : (
        <CustomizableDashboard 
          editMode={editMode} 
          onEditModeChange={setEditMode} 
        />
      )}
    </>
  );
};

export default DashboardPage;
