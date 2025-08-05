import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { PageLoader } from '@/components/common/PageLoader';
import { UserRole, normalizeRole } from '@/types/auth';
import { Box, Typography, Button } from '@mui/material';
import { Lock } from '@mui/icons-material';

interface RoleProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles: UserRole[];
}

export const RoleProtectedRoute: React.FC<RoleProtectedRouteProps> = ({ 
  children, 
  allowedRoles 
}) => {
  const { isAuthenticated, isPending, user } = useAuthStore();
  const location = useLocation();

  if (isPending) {
    return <PageLoader />;
  }

  if (!isAuthenticated || !user) {
    // Redirect to login page with return url
    return <Navigate to="/auth/login" state={{ from: location }} replace />;
  }

  // Normalize user role for comparison
  const normalizedUserRole = normalizeRole(user.role);
  const hasAccess = allowedRoles.some(role => role === normalizedUserRole);

  if (!hasAccess) {
    // Show access denied page
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          textAlign: 'center',
          p: 3,
        }}
      >
        <Lock sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h4" gutterBottom>
          Access Denied
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
          You don't have permission to access this page.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Your role: <strong>{user.role.replace(/_/g, ' ')}</strong>
        </Typography>
        <Button 
          variant="contained" 
          onClick={() => window.history.back()}
        >
          Go Back
        </Button>
      </Box>
    );
  }

  return <>{children}</>;
};