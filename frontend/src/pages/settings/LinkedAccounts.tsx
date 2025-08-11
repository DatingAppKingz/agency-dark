/**
 * Linked Accounts Settings Page
 * Manage external OAuth provider connections
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { 
  ConnectedAccounts, 
  ConnectedAccount,
  DEFAULT_PROVIDERS 
} from '../../components/auth/SocialLogin';
import {
  Container,
  Paper,
  Typography,
  Box,
  Alert,
  CircularProgress,
  Breadcrumbs,
  Link,
  Tab,
  Tabs,
  Card,
  CardContent,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Switch,
  Button,
  Divider,
  Chip,
  Stack,
} from '@mui/material';
import {
  AccountCircle as AccountIcon,
  Security as SecurityIcon,
  Sync as SyncIcon,
  History as HistoryIcon,
  Settings as SettingsIcon,
  NavigateNext as NavigateNextIcon,
  Info as InfoIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Schedule as ScheduleIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

// Tab panel component
interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index }) => {
  return (
    <div role="tabpanel" hidden={value !== index}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

/**
 * Linked Accounts Settings Page Component
 */
const LinkedAccounts: React.FC = () => {
  const navigate = useNavigate();
  const { 
    user,
    connectProvider, 
    disconnectProvider,
    getConnectedProviders 
  } = useAuth();
  
  // State
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connectedAccounts, setConnectedAccounts] = useState<ConnectedAccount[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  const [syncSettings, setSyncSettings] = useState({
    autoSync: true,
    syncFrequency: 'daily',
    syncContent: true,
    syncMetrics: true,
  });
  
  /**
   * Load connected accounts
   */
  const loadConnectedAccounts = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      // Get connected providers from backend
      const providers = await getConnectedProviders();
      
      // Mock account details (in production, this would come from the backend)
      const accounts: ConnectedAccount[] = providers.map((provider: string) => ({
        provider,
        providerName: DEFAULT_PROVIDERS.find(p => p.id === provider)?.name || provider,
        accountId: `${provider}_123`,
        accountName: `User ${provider}`,
        email: `user@${provider}.com`,
        connectedAt: new Date(),
        lastSync: new Date(),
        status: 'connected' as const,
      }));
      
      setConnectedAccounts(accounts);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load connected accounts';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };
  
  /**
   * Initialize on mount
   */
  useEffect(() => {
    loadConnectedAccounts();
  }, []);
  
  /**
   * Handle connect provider
   */
  const handleConnect = async (providerId: string) => {
    try {
      await connectProvider(providerId);
      // Reload accounts after connection
      await loadConnectedAccounts();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to connect provider';
      setError(message);
    }
  };
  
  /**
   * Handle disconnect provider
   */
  const handleDisconnect = async (providerId: string) => {
    try {
      await disconnectProvider(providerId);
      // Reload accounts after disconnection
      await loadConnectedAccounts();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to disconnect provider';
      setError(message);
    }
  };
  
  /**
   * Handle refresh provider
   */
  const handleRefresh = async (providerId: string) => {
    try {
      // In production, this would refresh the OAuth tokens
      await connectProvider(providerId);
      await loadConnectedAccounts();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to refresh provider';
      setError(message);
    }
  };
  
  /**
   * Handle sync setting change
   */
  const handleSyncSettingChange = (setting: string, value: any) => {
    setSyncSettings(prev => ({
      ...prev,
      [setting]: value,
    }));
    
    // In production, save settings to backend
  };
  
  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs 
        separator={<NavigateNextIcon fontSize="small" />}
        sx={{ mb: 3 }}
      >
        <Link
          underline="hover"
          color="inherit"
          href="/dashboard"
          onClick={(e) => {
            e.preventDefault();
            navigate('/dashboard');
          }}
        >
          Dashboard
        </Link>
        <Link
          underline="hover"
          color="inherit"
          href="/settings"
          onClick={(e) => {
            e.preventDefault();
            navigate('/settings');
          }}
        >
          Settings
        </Link>
        <Typography color="text.primary">Linked Accounts</Typography>
      </Breadcrumbs>
      
      {/* Header */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box>
            <Typography variant="h4" gutterBottom>
              Linked Accounts
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Manage your connected social media and external accounts
            </Typography>
          </Box>
          <Box>
            <Chip
              icon={<AccountIcon />}
              label={`${connectedAccounts.length} Connected`}
              color="primary"
              variant="outlined"
            />
          </Box>
        </Box>
      </Paper>
      
      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      
      {/* Main Content */}
      <Paper sx={{ p: 3 }}>
        <Tabs
          value={activeTab}
          onChange={(e, newValue) => setActiveTab(newValue)}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Connected Accounts" icon={<AccountIcon />} iconPosition="start" />
          <Tab label="Sync Settings" icon={<SyncIcon />} iconPosition="start" />
          <Tab label="Security" icon={<SecurityIcon />} iconPosition="start" />
          <Tab label="Activity Log" icon={<HistoryIcon />} iconPosition="start" />
        </Tabs>
        
        {/* Connected Accounts Tab */}
        <TabPanel value={activeTab} index={0}>
          {isLoading ? (
            <Box display="flex" justifyContent="center" p={4}>
              <CircularProgress />
            </Box>
          ) : (
            <ConnectedAccounts
              accounts={connectedAccounts}
              onConnect={handleConnect}
              onDisconnect={handleDisconnect}
              onRefresh={handleRefresh}
              availableProviders={DEFAULT_PROVIDERS}
              showAddButton={true}
            />
          )}
        </TabPanel>
        
        {/* Sync Settings Tab */}
        <TabPanel value={activeTab} index={1}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <SyncIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                    Automatic Sync
                  </Typography>
                  
                  <List>
                    <ListItem>
                      <ListItemText
                        primary="Enable Auto-Sync"
                        secondary="Automatically sync data from connected accounts"
                      />
                      <Switch
                        checked={syncSettings.autoSync}
                        onChange={(e) => handleSyncSettingChange('autoSync', e.target.checked)}
                      />
                    </ListItem>
                    
                    <ListItem>
                      <ListItemText
                        primary="Sync Content"
                        secondary="Import posts and media from connected accounts"
                      />
                      <Switch
                        checked={syncSettings.syncContent}
                        onChange={(e) => handleSyncSettingChange('syncContent', e.target.checked)}
                        disabled={!syncSettings.autoSync}
                      />
                    </ListItem>
                    
                    <ListItem>
                      <ListItemText
                        primary="Sync Analytics"
                        secondary="Import metrics and insights"
                      />
                      <Switch
                        checked={syncSettings.syncMetrics}
                        onChange={(e) => handleSyncSettingChange('syncMetrics', e.target.checked)}
                        disabled={!syncSettings.autoSync}
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    <ScheduleIcon sx={{ verticalAlign: 'middle', mr: 1 }} />
                    Sync Schedule
                  </Typography>
                  
                  <Stack spacing={2} mt={2}>
                    <Button
                      variant={syncSettings.syncFrequency === 'realtime' ? 'contained' : 'outlined'}
                      onClick={() => handleSyncSettingChange('syncFrequency', 'realtime')}
                      disabled={!syncSettings.autoSync}
                    >
                      Real-time
                    </Button>
                    <Button
                      variant={syncSettings.syncFrequency === 'hourly' ? 'contained' : 'outlined'}
                      onClick={() => handleSyncSettingChange('syncFrequency', 'hourly')}
                      disabled={!syncSettings.autoSync}
                    >
                      Every Hour
                    </Button>
                    <Button
                      variant={syncSettings.syncFrequency === 'daily' ? 'contained' : 'outlined'}
                      onClick={() => handleSyncSettingChange('syncFrequency', 'daily')}
                      disabled={!syncSettings.autoSync}
                    >
                      Daily
                    </Button>
                    <Button
                      variant={syncSettings.syncFrequency === 'weekly' ? 'contained' : 'outlined'}
                      onClick={() => handleSyncSettingChange('syncFrequency', 'weekly')}
                      disabled={!syncSettings.autoSync}
                    >
                      Weekly
                    </Button>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
          
          <Box mt={3}>
            <Button variant="contained" color="primary">
              Save Sync Settings
            </Button>
          </Box>
        </TabPanel>
        
        {/* Security Tab */}
        <TabPanel value={activeTab} index={2}>
          <Alert severity="info" icon={<InfoIcon />} sx={{ mb: 3 }}>
            Your connected accounts use OAuth 2.0 for secure authentication. 
            We never store your passwords.
          </Alert>
          
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Security Status
                  </Typography>
                  
                  <List>
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon color="success" />
                      </ListItemIcon>
                      <ListItemText
                        primary="OAuth 2.0 Authentication"
                        secondary="Secure token-based authentication"
                      />
                    </ListItem>
                    
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon color="success" />
                      </ListItemIcon>
                      <ListItemText
                        primary="Encrypted Tokens"
                        secondary="All tokens are encrypted at rest"
                      />
                    </ListItem>
                    
                    <ListItem>
                      <ListItemIcon>
                        <CheckCircleIcon color="success" />
                      </ListItemIcon>
                      <ListItemText
                        primary="Limited Scope Access"
                        secondary="Apps only access permitted data"
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>
            
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Permissions
                  </Typography>
                  
                  <Typography variant="body2" color="text.secondary" paragraph>
                    Each connected account has specific permissions granted during authorization.
                  </Typography>
                  
                  <Stack spacing={1}>
                    {connectedAccounts.map((account) => (
                      <Box key={account.provider}>
                        <Typography variant="subtitle2">
                          {account.providerName}
                        </Typography>
                        <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                          <Chip label="Read" size="small" />
                          <Chip label="Write" size="small" />
                          <Chip label="Profile" size="small" />
                        </Stack>
                      </Box>
                    ))}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </TabPanel>
        
        {/* Activity Log Tab */}
        <TabPanel value={activeTab} index={3}>
          <Alert severity="info" sx={{ mb: 3 }}>
            Recent activity from your connected accounts
          </Alert>
          
          <List>
            {connectedAccounts.map((account) => (
              <React.Fragment key={account.provider}>
                <ListItem>
                  <ListItemText
                    primary={`Connected ${account.providerName}`}
                    secondary={account.connectedAt.toLocaleString()}
                  />
                </ListItem>
                {account.lastSync && (
                  <ListItem>
                    <ListItemText
                      primary={`Last synced ${account.providerName}`}
                      secondary={account.lastSync.toLocaleString()}
                    />
                  </ListItem>
                )}
                <Divider />
              </React.Fragment>
            ))}
          </List>
        </TabPanel>
      </Paper>
    </Container>
  );
};

export default LinkedAccounts;