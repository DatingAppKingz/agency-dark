import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActions,
  Button,
  IconButton,
  Chip,
  Avatar,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  TextField,
  InputAdornment,
  Menu,
  MenuItem,
  Tooltip,
  Switch,
  FormControlLabel,
  LinearProgress,
} from '@mui/material';
import {
  Apps as AppsIcon,
  MoreVert as MoreVertIcon,
  Search as SearchIcon,
  Block as BlockIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Settings as SettingsIcon,
  Security as SecurityIcon,
  AccessTime as AccessTimeIcon,
  Link as LinkIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  VerifiedUser as VerifiedIcon,
  Schedule as ScheduleIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow, isAfter, addDays } from 'date-fns';
import { useConnectedApps } from '../../hooks/useConnectedApps';

interface ConnectedAppsProps {
  onRefresh?: () => void;
}

interface ConnectedApp {
  id: string;
  clientId: string;
  name: string;
  description?: string;
  icon?: string;
  website?: string;
  developer?: string;
  verified?: boolean;
  category?: string;
  authorizedAt: string;
  lastUsedAt?: string;
  expiresAt?: string;
  scopes: string[];
  permissions: {
    read: boolean;
    write: boolean;
    delete: boolean;
  };
  dataAccess: {
    profile: boolean;
    email: boolean;
    contacts?: boolean;
    calendar?: boolean;
    files?: boolean;
  };
  tokenCount: number;
  isActive: boolean;
  trustLevel: 'high' | 'medium' | 'low';
}

const scopeDescriptions: Record<string, string> = {
  openid: 'Basic authentication',
  profile: 'Your profile information',
  email: 'Your email address',
  phone: 'Your phone number',
  address: 'Your physical address',
  offline_access: 'Access your data anytime',
  'api:read': 'Read your data',
  'api:write': 'Modify your data',
  'api:delete': 'Delete your data',
  contacts: 'Access your contacts',
  calendar: 'Access your calendar',
  files: 'Access your files',
};

export const ConnectedApps: React.FC<ConnectedAppsProps> = ({ onRefresh }) => {
  const { getConnectedApps, revokeApp, updateAppPermissions } = useConnectedApps();
  const [apps, setApps] = useState<ConnectedApp[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedApp, setSelectedApp] = useState<ConnectedApp | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showRevokeDialog, setShowRevokeDialog] = useState(false);
  const [showPermissionsDialog, setShowPermissionsDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuApp, setMenuApp] = useState<ConnectedApp | null>(null);
  const [filterVerified, setFilterVerified] = useState(false);
  const [showExpired, setShowExpired] = useState(false);

  useEffect(() => {
    fetchConnectedApps();
  }, []);

  const fetchConnectedApps = async () => {
    setLoading(true);
    try {
      const data = await getConnectedApps();
      setApps(data);
    } catch (error) {
      console.error('Failed to fetch connected apps:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, app: ConnectedApp) => {
    setAnchorEl(event.currentTarget);
    setMenuApp(app);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setMenuApp(null);
  };

  const handleViewDetails = (app: ConnectedApp) => {
    setSelectedApp(app);
    setShowDetails(true);
    handleMenuClose();
  };

  const handleManagePermissions = (app: ConnectedApp) => {
    setSelectedApp(app);
    setShowPermissionsDialog(true);
    handleMenuClose();
  };

  const handleRevokeClick = (app: ConnectedApp) => {
    setSelectedApp(app);
    setShowRevokeDialog(true);
    handleMenuClose();
  };

  const handleRevokeConfirm = async () => {
    if (selectedApp) {
      await revokeApp(selectedApp.id);
      setShowRevokeDialog(false);
      setSelectedApp(null);
      fetchConnectedApps();
      onRefresh?.();
    }
  };

  const getTrustBadge = (trustLevel: string, verified?: boolean) => {
    if (verified) {
      return <Chip label="Verified" size="small" color="success" icon={<VerifiedIcon />} />;
    }
    
    const colors = {
      high: 'success' as const,
      medium: 'warning' as const,
      low: 'error' as const,
    };
    
    return (
      <Chip
        label={`${trustLevel} trust`}
        size="small"
        color={colors[trustLevel as keyof typeof colors]}
      />
    );
  };

  const getAppStatus = (app: ConnectedApp) => {
    if (!app.isActive) {
      return { label: 'Inactive', color: 'default' as const };
    }
    if (app.expiresAt && isAfter(new Date(), new Date(app.expiresAt))) {
      return { label: 'Expired', color: 'error' as const };
    }
    if (app.expiresAt && isAfter(addDays(new Date(), 7), new Date(app.expiresAt))) {
      return { label: 'Expiring Soon', color: 'warning' as const };
    }
    return { label: 'Active', color: 'success' as const };
  };

  // Mock data for demonstration
  const mockApps: ConnectedApp[] = [
    {
      id: '1',
      clientId: 'client_1',
      name: 'Productivity Suite',
      description: 'All-in-one productivity tools for your workflow',
      icon: '📊',
      website: 'https://productivity.example.com',
      developer: 'Productivity Inc.',
      verified: true,
      category: 'Productivity',
      authorizedAt: new Date(Date.now() - 30 * 86400000).toISOString(),
      lastUsedAt: new Date(Date.now() - 3600000).toISOString(),
      scopes: ['openid', 'profile', 'email', 'api:read', 'api:write'],
      permissions: { read: true, write: true, delete: false },
      dataAccess: { profile: true, email: true, contacts: true, calendar: true, files: false },
      tokenCount: 5,
      isActive: true,
      trustLevel: 'high',
    },
    {
      id: '2',
      clientId: 'client_2',
      name: 'Analytics Dashboard',
      description: 'Advanced analytics and reporting',
      icon: '📈',
      website: 'https://analytics.example.com',
      developer: 'Data Insights Co.',
      verified: false,
      category: 'Analytics',
      authorizedAt: new Date(Date.now() - 60 * 86400000).toISOString(),
      lastUsedAt: new Date(Date.now() - 7 * 86400000).toISOString(),
      expiresAt: new Date(Date.now() + 5 * 86400000).toISOString(),
      scopes: ['openid', 'profile', 'api:read'],
      permissions: { read: true, write: false, delete: false },
      dataAccess: { profile: true, email: false, contacts: false, calendar: false, files: false },
      tokenCount: 2,
      isActive: true,
      trustLevel: 'medium',
    },
    {
      id: '3',
      clientId: 'client_3',
      name: 'Social Media Manager',
      description: 'Manage all your social media accounts',
      icon: '🔗',
      website: 'https://social.example.com',
      developer: 'Social Tools Ltd.',
      verified: true,
      category: 'Social',
      authorizedAt: new Date(Date.now() - 90 * 86400000).toISOString(),
      lastUsedAt: new Date(Date.now() - 30 * 86400000).toISOString(),
      expiresAt: new Date(Date.now() - 86400000).toISOString(),
      scopes: ['openid', 'profile', 'email', 'api:read', 'api:write', 'api:delete'],
      permissions: { read: true, write: true, delete: true },
      dataAccess: { profile: true, email: true, contacts: false, calendar: false, files: false },
      tokenCount: 0,
      isActive: false,
      trustLevel: 'low',
    },
  ];

  const displayApps = apps.length > 0 ? apps : mockApps;
  
  const filteredApps = displayApps.filter(app => {
    const matchesSearch = !searchQuery || 
      app.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.developer?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesVerified = !filterVerified || app.verified;
    const matchesExpired = showExpired || app.isActive;
    
    return matchesSearch && matchesVerified && matchesExpired;
  });

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6">Connected Applications</Typography>
        <Typography variant="body2" color="textSecondary">
          Apps and services that have access to your account
        </Typography>
      </Box>

      {/* Filters */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, alignItems: 'center' }}>
        <TextField
          placeholder="Search apps..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ flexGrow: 1 }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={filterVerified}
              onChange={(e) => setFilterVerified(e.target.checked)}
            />
          }
          label="Verified only"
        />
        <FormControlLabel
          control={
            <Switch
              checked={showExpired}
              onChange={(e) => setShowExpired(e.target.checked)}
            />
          }
          label="Show expired"
        />
      </Box>

      {/* Security Alert */}
      {filteredApps.some(app => app.trustLevel === 'low' && app.isActive) && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="body2">
            Some apps have low trust scores. Review their permissions to ensure they only have access to necessary data.
          </Typography>
        </Alert>
      )}

      {/* Loading */}
      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {/* Apps Grid */}
      <Grid container spacing={3}>
        {filteredApps.map((app) => {
          const status = getAppStatus(app);
          
          return (
            <Grid item xs={12} md={6} lg={4} key={app.id}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Avatar sx={{ bgcolor: 'primary.light' }}>
                        {app.icon || <AppsIcon />}
                      </Avatar>
                      <Box>
                        <Typography variant="h6">{app.name}</Typography>
                        {app.developer && (
                          <Typography variant="caption" color="textSecondary">
                            by {app.developer}
                          </Typography>
                        )}
                      </Box>
                    </Box>
                    <IconButton size="small" onClick={(e) => handleMenuOpen(e, app)}>
                      <MoreVertIcon />
                    </IconButton>
                  </Box>

                  <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                    {getTrustBadge(app.trustLevel, app.verified)}
                    <Chip label={status.label} size="small" color={status.color} />
                  </Box>

                  {app.description && (
                    <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                      {app.description}
                    </Typography>
                  )}

                  <Box sx={{ mb: 2 }}>
                    <Typography variant="caption" color="textSecondary">
                      Permissions:
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                      {app.scopes.slice(0, 3).map((scope) => (
                        <Chip key={scope} label={scope} size="small" variant="outlined" />
                      ))}
                      {app.scopes.length > 3 && (
                        <Chip label={`+${app.scopes.length - 3} more`} size="small" variant="outlined" />
                      )}
                    </Box>
                  </Box>

                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="caption" color="textSecondary">
                      <AccessTimeIcon fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />
                      {app.lastUsedAt 
                        ? `Last used ${formatDistanceToNow(new Date(app.lastUsedAt), { addSuffix: true })}`
                        : 'Never used'}
                    </Typography>
                  </Box>
                </CardContent>

                <CardActions>
                  <Button size="small" onClick={() => handleViewDetails(app)}>
                    View Details
                  </Button>
                  <Button size="small" onClick={() => handleManagePermissions(app)}>
                    Permissions
                  </Button>
                  <Button size="small" color="error" onClick={() => handleRevokeClick(app)}>
                    Revoke
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          );
        })}
      </Grid>

      {/* No Apps */}
      {!loading && filteredApps.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body2" color="textSecondary">
            {searchQuery ? 'No apps found matching your search' : 'No connected applications'}
          </Typography>
        </Box>
      )}

      {/* App Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => menuApp && handleViewDetails(menuApp)}>
          <InfoIcon fontSize="small" sx={{ mr: 1 }} />
          View Details
        </MenuItem>
        <MenuItem onClick={() => menuApp && handleManagePermissions(menuApp)}>
          <SecurityIcon fontSize="small" sx={{ mr: 1 }} />
          Manage Permissions
        </MenuItem>
        {menuApp?.website && (
          <MenuItem onClick={() => window.open(menuApp.website, '_blank')}>
            <LinkIcon fontSize="small" sx={{ mr: 1 }} />
            Visit Website
          </MenuItem>
        )}
        <Divider />
        <MenuItem 
          onClick={() => menuApp && handleRevokeClick(menuApp)}
          sx={{ color: 'error.main' }}
        >
          <BlockIcon fontSize="small" sx={{ mr: 1 }} />
          Revoke Access
        </MenuItem>
      </Menu>

      {/* App Details Dialog */}
      <Dialog open={showDetails} onClose={() => setShowDetails(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Avatar sx={{ bgcolor: 'primary.light' }}>
              {selectedApp?.icon || <AppsIcon />}
            </Avatar>
            <Box>
              <Typography variant="h6">{selectedApp?.name}</Typography>
              {selectedApp?.developer && (
                <Typography variant="caption" color="textSecondary">
                  by {selectedApp.developer}
                </Typography>
              )}
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedApp && (
            <Box>
              <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  {getTrustBadge(selectedApp.trustLevel, selectedApp.verified)}
                  <Chip 
                    label={getAppStatus(selectedApp).label} 
                    size="small" 
                    color={getAppStatus(selectedApp).color} 
                  />
                  {selectedApp.category && (
                    <Chip label={selectedApp.category} size="small" variant="outlined" />
                  )}
                </Box>
              </Box>

              {selectedApp.description && (
                <Typography variant="body2" paragraph>
                  {selectedApp.description}
                </Typography>
              )}

              <List>
                <ListItem disableGutters>
                  <ListItemIcon>
                    <AccessTimeIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Authorized"
                    secondary={format(new Date(selectedApp.authorizedAt), 'PPP')}
                  />
                </ListItem>
                
                {selectedApp.lastUsedAt && (
                  <ListItem disableGutters>
                    <ListItemIcon>
                      <ScheduleIcon />
                    </ListItemIcon>
                    <ListItemText
                      primary="Last Used"
                      secondary={format(new Date(selectedApp.lastUsedAt), 'PPpp')}
                    />
                  </ListItem>
                )}
                
                {selectedApp.expiresAt && (
                  <ListItem disableGutters>
                    <ListItemIcon>
                      <WarningIcon color={isAfter(new Date(), new Date(selectedApp.expiresAt)) ? 'error' : 'inherit'} />
                    </ListItemIcon>
                    <ListItemText
                      primary="Expires"
                      secondary={format(new Date(selectedApp.expiresAt), 'PPP')}
                    />
                  </ListItem>
                )}
                
                <ListItem disableGutters>
                  <ListItemIcon>
                    <SecurityIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Active Tokens"
                    secondary={selectedApp.tokenCount}
                  />
                </ListItem>
              </List>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" gutterBottom>
                Permissions & Scopes
              </Typography>
              <List dense>
                {selectedApp.scopes.map((scope) => (
                  <ListItem key={scope} disableGutters>
                    <ListItemIcon>
                      <CheckCircleIcon fontSize="small" color="success" />
                    </ListItemIcon>
                    <ListItemText
                      primary={scope}
                      secondary={scopeDescriptions[scope] || 'Custom permission'}
                    />
                  </ListItem>
                ))}
              </List>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" gutterBottom>
                Data Access
              </Typography>
              <Grid container spacing={1}>
                {Object.entries(selectedApp.dataAccess).map(([key, hasAccess]) => (
                  <Grid item xs={6} key={key}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {hasAccess ? (
                        <CheckCircleIcon fontSize="small" color="success" />
                      ) : (
                        <BlockIcon fontSize="small" color="action" />
                      )}
                      <Typography variant="body2" color={hasAccess ? 'textPrimary' : 'textSecondary'}>
                        {key.charAt(0).toUpperCase() + key.slice(1)}
                      </Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDetails(false)}>Close</Button>
          <Button 
            onClick={() => {
              setShowDetails(false);
              selectedApp && handleManagePermissions(selectedApp);
            }}
            variant="outlined"
          >
            Manage Permissions
          </Button>
          <Button
            onClick={() => {
              setShowDetails(false);
              selectedApp && handleRevokeClick(selectedApp);
            }}
            color="error"
            variant="contained"
          >
            Revoke Access
          </Button>
        </DialogActions>
      </Dialog>

      {/* Permissions Management Dialog */}
      <Dialog open={showPermissionsDialog} onClose={() => setShowPermissionsDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Manage Permissions - {selectedApp?.name}</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              Changing permissions may affect the app's functionality. The app will be notified of any changes.
            </Typography>
          </Alert>
          
          {selectedApp && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Current Permissions
              </Typography>
              <List>
                {selectedApp.scopes.map((scope) => (
                  <ListItem key={scope}>
                    <ListItemIcon>
                      <Checkbox checked disabled />
                    </ListItemIcon>
                    <ListItemText
                      primary={scope}
                      secondary={scopeDescriptions[scope] || 'Custom permission'}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowPermissionsDialog(false)}>Cancel</Button>
          <Button variant="contained" onClick={() => setShowPermissionsDialog(false)}>
            Save Changes
          </Button>
        </DialogActions>
      </Dialog>

      {/* Revoke App Dialog */}
      <Dialog open={showRevokeDialog} onClose={() => setShowRevokeDialog(false)}>
        <DialogTitle>Revoke App Access?</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              This will revoke all access for this application and delete all associated tokens.
              You may need to sign in again if you want to use this app in the future.
            </Typography>
          </Alert>
          {selectedApp && (
            <Box>
              <Typography variant="body2">
                <strong>App:</strong> {selectedApp.name}
              </Typography>
              <Typography variant="body2">
                <strong>Developer:</strong> {selectedApp.developer}
              </Typography>
              <Typography variant="body2">
                <strong>Permissions:</strong> {selectedApp.scopes.length} scope(s)
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowRevokeDialog(false)}>Cancel</Button>
          <Button onClick={handleRevokeConfirm} color="error" variant="contained">
            Revoke Access
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};