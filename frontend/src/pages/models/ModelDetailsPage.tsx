import React from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Avatar,
  Chip,
  Tabs,
  Tab,
  Button,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  ArrowBack,
  Edit,
  TrendingUp,
  AttachMoney,
  People,
  Star,
  Schedule,
  CheckCircle,
  Warning,
  Image,
  VideoLibrary,
  Description,
  Visibility,
  ThumbUp,
  Message,
} from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { useAuthStore } from '@/store/authStore';
import { normalizeRole, UserRole } from '@/types/auth';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const ModelDetailsPage: React.FC = () => {
  const { modelId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = React.useState(0);

  const userRole = user ? normalizeRole(user.role) : '';
  const isModel = userRole === UserRole.MODEL;
  const canEdit = !isModel || user?.id === modelId;

  // Fetch model data
  const { data: modelData, isLoading } = useQuery({
    queryKey: ['model-details', modelId],
    queryFn: async () => {
      try {
        const response = await fetch(`/api/v1/admin/users/list?page=1&size=1`, {
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error('Failed to fetch model');
        }
        const data = await response.json();
        // Find the specific model - in real app this would be a specific endpoint
        const model = data.data.find((u: any) => u.id === modelId);
        if (!model) {
          // Return mock data for demonstration
          return {
            id: modelId,
            email: 'model@example.com',
            full_name: 'Jane Doe',
            stage_name: 'JaneDoe',
            role: 'MODEL',
            agency_id: 'agency-1',
            is_active: true,
            is_verified: true,
            created_at: new Date().toISOString(),
            last_login: new Date().toISOString(),
          };
        }
        return model;
      } catch (error) {
        console.error('Error fetching model:', error);
        return null;
      }
    },
  });

  // Mock data for demonstration
  const mockStats = {
    totalEarnings: 45850,
    monthlyEarnings: 8500,
    totalSubscribers: 856,
    activeSubscribers: 742,
    contentCount: 324,
    avgRating: 4.7,
    profileCompletion: 85,
    recentActivity: [
      { type: 'content', action: 'Posted new photo set', time: '2 hours ago' },
      { type: 'message', action: 'Replied to 5 messages', time: '5 hours ago' },
      { type: 'earnings', action: 'Earned $250 from tips', time: '1 day ago' },
      { type: 'subscriber', action: 'Gained 12 new subscribers', time: '2 days ago' },
    ],
    contentStats: {
      photos: 256,
      videos: 68,
      posts: 145,
      totalViews: 125600,
      totalLikes: 45200,
      totalComments: 8960,
    },
    performanceMetrics: {
      responseRate: 94,
      avgResponseTime: '2.5 hours',
      subscriberRetention: 78,
      contentEngagement: 36,
    },
  };

  const renderOverviewTab = () => (
    <Grid container spacing={3}>
      {/* Profile Info */}
      <Grid item xs={12} md={4}>
        <Card>
          <CardContent>
            <Box display="flex" flexDirection="column" alignItems="center">
              <Avatar 
                sx={{ width: 120, height: 120, mb: 2 }}
              >
                {modelData?.stage_name?.[0] || modelData?.full_name?.[0] || 'M'}
              </Avatar>
              <Typography variant="h5" gutterBottom>
                {modelData?.stage_name || modelData?.full_name}
              </Typography>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                {modelData?.email}
              </Typography>
              <Box display="flex" gap={1} mt={2}>
                <Chip 
                  label={modelData?.is_active ? 'Active' : 'Inactive'} 
                  color={modelData?.is_active ? 'success' : 'default'}
                  size="small"
                />
                <Chip 
                  label={modelData?.is_verified ? 'Verified' : 'Unverified'} 
                  color={modelData?.is_verified ? 'info' : 'default'}
                  size="small"
                />
              </Box>
              {canEdit && (
                <Button
                  variant="outlined"
                  startIcon={<Edit />}
                  sx={{ mt: 2 }}
                  fullWidth
                >
                  Edit Profile
                </Button>
              )}
            </Box>
          </CardContent>
        </Card>

        {/* Profile Completion */}
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant="subtitle2" gutterBottom>
              Profile Completion
            </Typography>
            <Box display="flex" alignItems="center" gap={2}>
              <Box flex={1}>
                <LinearProgress 
                  variant="determinate" 
                  value={mockStats.profileCompletion} 
                  color={mockStats.profileCompletion >= 80 ? 'success' : 'warning'}
                  sx={{ height: 8, borderRadius: 4 }}
                />
              </Box>
              <Typography variant="body2" fontWeight="medium">
                {mockStats.profileCompletion}%
              </Typography>
            </Box>
            <List dense sx={{ mt: 1 }}>
              <ListItem disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <CheckCircle color="success" fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Profile photo uploaded" />
              </ListItem>
              <ListItem disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <CheckCircle color="success" fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Bio completed" />
              </ListItem>
              <ListItem disablePadding>
                <ListItemIcon sx={{ minWidth: 32 }}>
                  <Warning color="warning" fontSize="small" />
                </ListItemIcon>
                <ListItemText primary="Verification pending" />
              </ListItem>
            </List>
          </CardContent>
        </Card>
      </Grid>

      {/* Stats Cards */}
      <Grid item xs={12} md={8}>
        <Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography color="text.secondary" variant="caption">
                      Total Earnings
                    </Typography>
                    <Typography variant="h6">
                      ${mockStats.totalEarnings.toLocaleString()}
                    </Typography>
                  </Box>
                  <AttachMoney color="success" />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography color="text.secondary" variant="caption">
                      Active Subs
                    </Typography>
                    <Typography variant="h6">
                      {mockStats.activeSubscribers}
                    </Typography>
                  </Box>
                  <People color="primary" />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography color="text.secondary" variant="caption">
                      Content
                    </Typography>
                    <Typography variant="h6">
                      {mockStats.contentCount}
                    </Typography>
                  </Box>
                  <Image color="info" />
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Card>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography color="text.secondary" variant="caption">
                      Rating
                    </Typography>
                    <Typography variant="h6">
                      {mockStats.avgRating}
                    </Typography>
                  </Box>
                  <Star color="warning" />
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Recent Activity */}
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Recent Activity
            </Typography>
            <List>
              {mockStats.recentActivity.map((activity, index) => (
                <React.Fragment key={index}>
                  <ListItem disablePadding>
                    <ListItemIcon>
                      {activity.type === 'content' && <Image color="action" />}
                      {activity.type === 'message' && <Message color="action" />}
                      {activity.type === 'earnings' && <AttachMoney color="action" />}
                      {activity.type === 'subscriber' && <People color="action" />}
                    </ListItemIcon>
                    <ListItemText 
                      primary={activity.action}
                      secondary={activity.time}
                    />
                  </ListItem>
                  {index < mockStats.recentActivity.length - 1 && <Divider />}
                </React.Fragment>
              ))}
            </List>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const renderPerformanceTab = () => (
    <Grid container spacing={3}>
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Performance Metrics
            </Typography>
            <List>
              <ListItem>
                <ListItemText 
                  primary="Response Rate"
                  secondary={`${mockStats.performanceMetrics.responseRate}%`}
                />
                <CircularProgress 
                  variant="determinate" 
                  value={mockStats.performanceMetrics.responseRate}
                  color="success"
                />
              </ListItem>
              <Divider />
              <ListItem>
                <ListItemText 
                  primary="Average Response Time"
                  secondary={mockStats.performanceMetrics.avgResponseTime}
                />
                <Schedule color="action" />
              </ListItem>
              <Divider />
              <ListItem>
                <ListItemText 
                  primary="Subscriber Retention"
                  secondary={`${mockStats.performanceMetrics.subscriberRetention}%`}
                />
                <TrendingUp color="primary" />
              </ListItem>
              <Divider />
              <ListItem>
                <ListItemText 
                  primary="Content Engagement"
                  secondary={`${mockStats.performanceMetrics.contentEngagement}%`}
                />
                <ThumbUp color="info" />
              </ListItem>
            </List>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Content Statistics
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Box textAlign="center" p={2}>
                  <Image color="action" sx={{ fontSize: 40 }} />
                  <Typography variant="h4">{mockStats.contentStats.photos}</Typography>
                  <Typography variant="caption">Photos</Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box textAlign="center" p={2}>
                  <VideoLibrary color="action" sx={{ fontSize: 40 }} />
                  <Typography variant="h4">{mockStats.contentStats.videos}</Typography>
                  <Typography variant="caption">Videos</Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box textAlign="center" p={2}>
                  <Visibility color="action" sx={{ fontSize: 40 }} />
                  <Typography variant="h4">
                    {(mockStats.contentStats.totalViews / 1000).toFixed(1)}k
                  </Typography>
                  <Typography variant="caption">Total Views</Typography>
                </Box>
              </Grid>
              <Grid item xs={6}>
                <Box textAlign="center" p={2}>
                  <ThumbUp color="action" sx={{ fontSize: 40 }} />
                  <Typography variant="h4">
                    {(mockStats.contentStats.totalLikes / 1000).toFixed(1)}k
                  </Typography>
                  <Typography variant="caption">Total Likes</Typography>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  if (isLoading) {
    return (
      <Container maxWidth="xl">
        <Box display="flex" justifyContent="center" alignItems="center" height={400}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl">
      <Box py={4}>
        {/* Header */}
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={4}>
          <Box display="flex" alignItems="center" gap={2}>
            <IconButton onClick={() => navigate(-1)}>
              <ArrowBack />
            </IconButton>
            <Box>
              <Typography variant="h4">
                {modelData?.stage_name || modelData?.full_name || 'Model Details'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Member since {modelData?.created_at ? format(new Date(modelData.created_at), 'MMMM yyyy') : 'Unknown'}
              </Typography>
            </Box>
          </Box>
          <Box display="flex" gap={2}>
            <Button variant="outlined" startIcon={<Message />}>
              Send Message
            </Button>
            <Button variant="contained" startIcon={<TrendingUp />}>
              View Analytics
            </Button>
          </Box>
        </Box>

        {/* Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)}>
            <Tab label="Overview" />
            <Tab label="Performance" />
            <Tab label="Content" />
            <Tab label="Earnings" />
          </Tabs>
        </Paper>

        {/* Tab Panels */}
        <TabPanel value={activeTab} index={0}>
          {renderOverviewTab()}
        </TabPanel>
        <TabPanel value={activeTab} index={1}>
          {renderPerformanceTab()}
        </TabPanel>
        <TabPanel value={activeTab} index={2}>
          <Typography>Content management coming soon...</Typography>
        </TabPanel>
        <TabPanel value={activeTab} index={3}>
          <Typography>Earnings details coming soon...</Typography>
        </TabPanel>
      </Box>
    </Container>
  );
};

export default ModelDetailsPage;