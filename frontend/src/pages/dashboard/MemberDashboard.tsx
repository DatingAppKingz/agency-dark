import { Typography, Box, Paper } from '@mui/material';
import { useAuthStore } from '@/store/authStore';

export const MemberDashboard = () => {
  const { user } = useAuthStore();

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Welcome, {user?.full_name}!
      </Typography>

      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h6" gutterBottom>
          Agency Member Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Your dashboard is being prepared. Please check back soon for updates.
        </Typography>
      </Paper>
    </Box>
  );
};
