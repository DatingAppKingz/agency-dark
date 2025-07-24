import { Grid, Box, Typography } from '@mui/material';
import { useAuthStore } from '@/store/authStore';
import { UserRole } from '@/types/auth';
import { SuperAdminDashboard } from './SuperAdminDashboard';
import { AgencyOwnerDashboard } from './AgencyOwnerDashboard';
import { AgencyAdminDashboard } from './AgencyAdminDashboard';
import { ModelDashboard } from './ModelDashboard';
import { ChatterDashboard } from './ChatterDashboard';
import { MemberDashboard } from './MemberDashboard';

const DashboardPage = () => {
  const { user } = useAuthStore();

  if (!user) {
    return (
      <Box>
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  // Render role-specific dashboard
  switch (user.role) {
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
          <Typography>Unknown role: {user.role}</Typography>
        </Box>
      );
  }
};

export default DashboardPage;