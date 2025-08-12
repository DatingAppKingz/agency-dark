import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Tabs,
  Tab,
  Card,
  CardContent,
  Grid,
  Button,
  Alert,
  Badge,
  Avatar,
  Chip,
  IconButton,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Security as SecurityIcon,
  Apps as AppsIcon,
  DevicesOther as DevicesIcon,
  Settings as SettingsIcon,
  Shield as ShieldIcon,
  Notifications as NotificationsIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { ActiveSessions } from '../../components/oauth/ActiveSessions';
import { ConnectedApps } from '../../components/oauth/ConnectedApps';
import { OAuthSecuritySettings } from '../../components/oauth/OAuthSecuritySettings';
import { useAuth } from '../../hooks/useAuth';
import { useOAuthSessions } from '../../hooks/useOAuthSessions';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`oauth-tabpanel-${index}`}
      aria-labelledby={`oauth-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

const OAuthDashboard: React.FC = () => {
  const { user } = useAuth();
  const { getSessionStats, getSecurityAlerts } = useOAuthSessions();
  const [activeTab, setActiveTab] = useState(0);
  const [stats, setStats] = useState({
    activeSessions: 0,
    connectedApps: 0,
    recentActivity: 0,
    securityScore: 0,
  });
  const [securityAlerts, setSecurityAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const [statsData, alertsData] = await Promise.all([
        getSessionStats(),
        getSecurityAlerts(),
      ]);
      setStats(statsData);
      setSecurityAlerts(alertsData);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const getSecurityScoreColor = (score: number) => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'error';
  };

  const getSecurityScoreLabel = (score: number) => {
    if (score >= 80) return 'Excellent';
    if (score >= 60) return 'Good';
    if (score >= 40) return 'Fair';
    return 'Needs Improvement';
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          OAuth Security Center
        </Typography>
        <Typography variant="body1" color="textSecondary">
          Manage your connected applications, active sessions, and security settings
        </Typography>
      </Box>

      {/* Security Alerts */}
      {securityAlerts.length > 0 && (
        <Alert 
          severity="warning" 
          sx={{ mb: 3 }}
          action={
            <Button size="small" color="inherit">
              Review
            </Button>
          }
        >
          <Typography variant="body2">
            You have {securityAlerts.length} security alert{securityAlerts.length > 1 ? 's' : ''} that require your attention
          </Typography>
        </Alert>
      )}

      {/* Statistics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4">
                    {loading ? <LinearProgress /> : stats.activeSessions}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Active Sessions
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'primary.light' }}>
                  <DevicesIcon />
                </Avatar>
              </Box>
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" color="textSecondary">
                  Across all devices
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4">
                    {loading ? <LinearProgress /> : stats.connectedApps}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Connected Apps
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'success.light' }}>
                  <AppsIcon />
                </Avatar>
              </Box>
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" color="textSecondary">
                  Authorized applications
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="h4">
                    {loading ? <LinearProgress /> : stats.recentActivity}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Recent Activities
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'info.light' }}>
                  <NotificationsIcon />
                </Avatar>
              </Box>
              <Box sx={{ mt: 2 }}>
                <Typography variant="caption" color="textSecondary">
                  Last 7 days
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="h4">
                      {loading ? <LinearProgress /> : `${stats.securityScore}%`}
                    </Typography>
                    {!loading && (
                      <Chip
                        label={getSecurityScoreLabel(stats.securityScore)}
                        size="small"
                        color={getSecurityScoreColor(stats.securityScore)}
                      />
                    )}
                  </Box>
                  <Typography variant="body2" color="textSecondary">
                    Security Score
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: `${getSecurityScoreColor(stats.securityScore)}.light` }}>
                  <ShieldIcon />
                </Avatar>
              </Box>
              <Box sx={{ mt: 2 }}>
                <LinearProgress
                  variant="determinate"
                  value={stats.securityScore}
                  color={getSecurityScoreColor(stats.securityScore)}
                  sx={{ height: 6, borderRadius: 1 }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Main Content Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={handleTabChange}>
            <Tab 
              label="Active Sessions" 
              icon={<DevicesIcon />} 
              iconPosition="start"
            />
            <Tab 
              label={
                <Badge badgeContent={stats.connectedApps} color="primary">
                  Connected Apps
                </Badge>
              }
              icon={<AppsIcon />} 
              iconPosition="start"
            />
            <Tab 
              label="Security Settings" 
              icon={<SecurityIcon />} 
              iconPosition="start"
            />
          </Tabs>
        </Box>

        <CardContent>
          <TabPanel value={activeTab} index={0}>
            <ActiveSessions onRefresh={fetchDashboardData} />
          </TabPanel>

          <TabPanel value={activeTab} index={1}>
            <ConnectedApps onRefresh={fetchDashboardData} />
          </TabPanel>

          <TabPanel value={activeTab} index={2}>
            <OAuthSecuritySettings onRefresh={fetchDashboardData} />
          </TabPanel>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <Box sx={{ mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          Quick Actions
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <WarningIcon color="warning" />
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      Review Permissions
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Check app permissions
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <SecurityIcon color="primary" />
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      Security Checkup
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Review security settings
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <DevicesIcon color="info" />
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      Manage Devices
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      View signed-in devices
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} sm={6} md={3}>
            <Card sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <NotificationsIcon color="action" />
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      Activity Log
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      View recent activity
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>

      {/* Security Tips */}
      <Box sx={{ mt: 4 }}>
        <Card variant="outlined">
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
              <InfoIcon color="info" />
              <Typography variant="h6">Security Tips</Typography>
            </Box>
            <Grid container spacing={2}>
              <Grid item xs={12} md={4}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  <CheckCircleIcon fontSize="small" color="success" />
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      Review apps regularly
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Remove access for apps you no longer use
                    </Typography>
                  </Box>
                </Box>
              </Grid>
              <Grid item xs={12} md={4}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  <CheckCircleIcon fontSize="small" color="success" />
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      Check permissions
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Ensure apps only have necessary permissions
                    </Typography>
                  </Box>
                </Box>
              </Grid>
              <Grid item xs={12} md={4}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  <CheckCircleIcon fontSize="small" color="success" />
                  <Box>
                    <Typography variant="body2" fontWeight="medium">
                      Monitor sessions
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Sign out from devices you don't recognize
                    </Typography>
                  </Box>
                </Box>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Box>
    </Container>
  );
};

export default OAuthDashboard;