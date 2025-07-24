import { Grid, Typography, Box, Paper, Chip } from '@mui/material';
import { Message, Schedule, CheckCircle, Warning } from '@mui/icons-material';
import { StatsCard } from '@/components/dashboard/StatsCard';

export const ChatterDashboard = () => {
  // Mock data - will be replaced with real API calls
  const stats = {
    activeChats: 8,
    pendingMessages: 23,
    completedToday: 45,
    avgResponseTime: '2.5 min',
  };

  const assignedModels = [
    { id: '1', name: 'Emma Stone', activeChats: 3, priority: 'high' },
    { id: '2', name: 'Sophia Lee', activeChats: 2, priority: 'medium' },
    { id: '3', name: 'Isabella Rose', activeChats: 3, priority: 'low' },
  ];

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Chatter Dashboard
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Active Chats"
            value={stats.activeChats}
            icon={<Message fontSize="large" />}
            color="primary"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Pending Messages"
            value={stats.pendingMessages}
            icon={<Warning fontSize="large" />}
            color="warning"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Completed Today"
            value={stats.completedToday}
            icon={<CheckCircle fontSize="large" />}
            color="success"
          />
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <StatsCard
            title="Avg Response Time"
            value={stats.avgResponseTime}
            icon={<Schedule fontSize="large" />}
            color="info"
          />
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Assigned Models
            </Typography>
            <Box sx={{ mt: 2 }}>
              {assignedModels.map((model) => (
                <Box
                  key={model.id}
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    py: 2,
                    borderBottom: 1,
                    borderColor: 'divider',
                  }}
                >
                  <Box>
                    <Typography variant="body1">{model.name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {model.activeChats} active chats
                    </Typography>
                  </Box>
                  <Chip
                    label={model.priority}
                    size="small"
                    color={
                      model.priority === 'high' ? 'error' :
                      model.priority === 'medium' ? 'warning' : 'default'
                    }
                  />
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};