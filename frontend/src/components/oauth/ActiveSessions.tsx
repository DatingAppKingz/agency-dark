import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  ListItemSecondaryAction,
  Avatar,
  IconButton,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Card,
  CardContent,
  Grid,
  Tooltip,
  Menu,
  MenuItem,
  Divider,
  LinearProgress,
} from '@mui/material';
import {
  Computer as ComputerIcon,
  Smartphone as SmartphoneIcon,
  Tablet as TabletIcon,
  Watch as WatchIcon,
  Tv as TvIcon,
  MoreVert as MoreVertIcon,
  LocationOn as LocationIcon,
  AccessTime as AccessTimeIcon,
  Security as SecurityIcon,
  Block as BlockIcon,
  Info as InfoIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  ExitToApp as LogoutIcon,
} from '@mui/icons-material';
import { formatDistanceToNow, format, isAfter, subMinutes } from 'date-fns';
import { useOAuthSessions } from '../../hooks/useOAuthSessions';

interface ActiveSessionsProps {
  onRefresh?: () => void;
}

interface Session {
  id: string;
  deviceType: 'desktop' | 'mobile' | 'tablet' | 'watch' | 'tv' | 'unknown';
  deviceName: string;
  browser?: string;
  os?: string;
  location?: {
    city?: string;
    country?: string;
    ip: string;
  };
  createdAt: string;
  lastActiveAt: string;
  isCurrent: boolean;
  isActive: boolean;
  tokenCount: number;
  scopes: string[];
  clientName?: string;
  riskLevel?: 'low' | 'medium' | 'high';
  suspicious?: boolean;
}

export const ActiveSessions: React.FC<ActiveSessionsProps> = ({ onRefresh }) => {
  const { getSessions, revokeSession, revokeAllSessions } = useOAuthSessions();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSession, setSelectedSession] = useState<Session | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showRevokeDialog, setShowRevokeDialog] = useState(false);
  const [showRevokeAllDialog, setShowRevokeAllDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuSession, setMenuSession] = useState<Session | null>(null);

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const data = await getSessions();
      setSessions(data);
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, session: Session) => {
    setAnchorEl(event.currentTarget);
    setMenuSession(session);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setMenuSession(null);
  };

  const handleViewDetails = (session: Session) => {
    setSelectedSession(session);
    setShowDetails(true);
    handleMenuClose();
  };

  const handleRevokeClick = (session: Session) => {
    setSelectedSession(session);
    setShowRevokeDialog(true);
    handleMenuClose();
  };

  const handleRevokeConfirm = async () => {
    if (selectedSession) {
      await revokeSession(selectedSession.id);
      setShowRevokeDialog(false);
      setSelectedSession(null);
      fetchSessions();
      onRefresh?.();
    }
  };

  const handleRevokeAllConfirm = async () => {
    await revokeAllSessions();
    setShowRevokeAllDialog(false);
    fetchSessions();
    onRefresh?.();
  };

  const getDeviceIcon = (deviceType: string) => {
    switch (deviceType) {
      case 'desktop':
        return <ComputerIcon />;
      case 'mobile':
        return <SmartphoneIcon />;
      case 'tablet':
        return <TabletIcon />;
      case 'watch':
        return <WatchIcon />;
      case 'tv':
        return <TvIcon />;
      default:
        return <ComputerIcon />;
    }
  };

  const getSessionStatus = (session: Session) => {
    const lastActive = new Date(session.lastActiveAt);
    const fiveMinutesAgo = subMinutes(new Date(), 5);
    
    if (session.isCurrent) {
      return { label: 'Current Session', color: 'success' as const, icon: <CheckCircleIcon /> };
    }
    if (isAfter(lastActive, fiveMinutesAgo)) {
      return { label: 'Active', color: 'success' as const, icon: <CheckCircleIcon /> };
    }
    if (session.suspicious) {
      return { label: 'Suspicious', color: 'error' as const, icon: <WarningIcon /> };
    }
    return { label: 'Idle', color: 'default' as const, icon: <AccessTimeIcon /> };
  };

  const getRiskBadge = (riskLevel?: string) => {
    if (!riskLevel) return null;
    
    const colors = {
      low: 'success' as const,
      medium: 'warning' as const,
      high: 'error' as const,
    };
    
    return (
      <Chip
        label={`${riskLevel} risk`}
        size="small"
        color={colors[riskLevel as keyof typeof colors]}
      />
    );
  };

  // Mock data for demonstration
  const mockSessions: Session[] = [
    {
      id: '1',
      deviceType: 'desktop',
      deviceName: 'Chrome on MacBook Pro',
      browser: 'Chrome 120',
      os: 'macOS Sonoma',
      location: {
        city: 'San Francisco',
        country: 'United States',
        ip: '192.168.1.1',
      },
      createdAt: new Date().toISOString(),
      lastActiveAt: new Date().toISOString(),
      isCurrent: true,
      isActive: true,
      tokenCount: 3,
      scopes: ['openid', 'profile', 'email'],
      clientName: 'Web App',
      riskLevel: 'low',
    },
    {
      id: '2',
      deviceType: 'mobile',
      deviceName: 'Safari on iPhone',
      browser: 'Safari 17',
      os: 'iOS 17.2',
      location: {
        city: 'San Francisco',
        country: 'United States',
        ip: '192.168.1.2',
      },
      createdAt: new Date(Date.now() - 86400000).toISOString(),
      lastActiveAt: new Date(Date.now() - 3600000).toISOString(),
      isCurrent: false,
      isActive: true,
      tokenCount: 2,
      scopes: ['openid', 'profile'],
      clientName: 'Mobile App',
      riskLevel: 'low',
    },
    {
      id: '3',
      deviceType: 'tablet',
      deviceName: 'Chrome on iPad',
      browser: 'Chrome 120',
      os: 'iPadOS 17',
      location: {
        city: 'New York',
        country: 'United States',
        ip: '10.0.0.1',
      },
      createdAt: new Date(Date.now() - 172800000).toISOString(),
      lastActiveAt: new Date(Date.now() - 7200000).toISOString(),
      isCurrent: false,
      isActive: false,
      tokenCount: 1,
      scopes: ['openid'],
      clientName: 'Tablet App',
      riskLevel: 'medium',
      suspicious: true,
    },
  ];

  const displaySessions = sessions.length > 0 ? sessions : mockSessions;

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h6">Active Sessions</Typography>
          <Typography variant="body2" color="textSecondary">
            Manage devices and browsers where you're signed in
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            startIcon={<RefreshIcon />}
            onClick={fetchSessions}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button
            variant="outlined"
            color="error"
            startIcon={<LogoutIcon />}
            onClick={() => setShowRevokeAllDialog(true)}
            disabled={displaySessions.filter(s => !s.isCurrent).length === 0}
          >
            Sign Out All
          </Button>
        </Box>
      </Box>

      {/* Security Alert */}
      {displaySessions.some(s => s.suspicious) && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          <Typography variant="body2">
            We detected unusual activity in one or more sessions. Please review and sign out from any sessions you don't recognize.
          </Typography>
        </Alert>
      )}

      {/* Loading */}
      {loading && <LinearProgress sx={{ mb: 2 }} />}

      {/* Sessions List */}
      <List>
        {displaySessions.map((session, index) => {
          const status = getSessionStatus(session);
          
          return (
            <React.Fragment key={session.id}>
              {index > 0 && <Divider />}
              <ListItem>
                <ListItemAvatar>
                  <Avatar sx={{ bgcolor: session.suspicious ? 'error.light' : 'primary.light' }}>
                    {getDeviceIcon(session.deviceType)}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="body1" fontWeight="medium">
                        {session.deviceName}
                      </Typography>
                      {session.isCurrent && (
                        <Chip label="This Device" size="small" color="primary" />
                      )}
                      {getRiskBadge(session.riskLevel)}
                      <Chip
                        label={status.label}
                        size="small"
                        color={status.color}
                        icon={status.icon}
                      />
                    </Box>
                  }
                  secondary={
                    <Box sx={{ mt: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 0.5 }}>
                        {session.location && (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <LocationIcon fontSize="small" color="action" />
                            <Typography variant="caption">
                              {session.location.city}, {session.location.country}
                            </Typography>
                          </Box>
                        )}
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <AccessTimeIcon fontSize="small" color="action" />
                          <Typography variant="caption">
                            Last active {formatDistanceToNow(new Date(session.lastActiveAt), { addSuffix: true })}
                          </Typography>
                        </Box>
                      </Box>
                      {session.browser && (
                        <Typography variant="caption" color="textSecondary">
                          {session.browser} • {session.os} • IP: {session.location?.ip}
                        </Typography>
                      )}
                    </Box>
                  }
                />
                <ListItemSecondaryAction>
                  <IconButton
                    edge="end"
                    onClick={(e) => handleMenuOpen(e, session)}
                    disabled={session.isCurrent}
                  >
                    <MoreVertIcon />
                  </IconButton>
                </ListItemSecondaryAction>
              </ListItem>
            </React.Fragment>
          );
        })}
      </List>

      {/* No Sessions */}
      {!loading && displaySessions.length === 0 && (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body2" color="textSecondary">
            No active sessions found
          </Typography>
        </Box>
      )}

      {/* Session Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => menuSession && handleViewDetails(menuSession)}>
          <InfoIcon fontSize="small" sx={{ mr: 1 }} />
          View Details
        </MenuItem>
        <MenuItem 
          onClick={() => menuSession && handleRevokeClick(menuSession)}
          sx={{ color: 'error.main' }}
        >
          <BlockIcon fontSize="small" sx={{ mr: 1 }} />
          Sign Out
        </MenuItem>
      </Menu>

      {/* Session Details Dialog */}
      <Dialog open={showDetails} onClose={() => setShowDetails(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Session Details</DialogTitle>
        <DialogContent>
          {selectedSession && (
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" gutterBottom>
                      Device Information
                    </Typography>
                    <List dense>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Device"
                          secondary={selectedSession.deviceName}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Browser"
                          secondary={selectedSession.browser || 'Unknown'}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Operating System"
                          secondary={selectedSession.os || 'Unknown'}
                        />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" gutterBottom>
                      Session Information
                    </Typography>
                    <List dense>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Created"
                          secondary={format(new Date(selectedSession.createdAt), 'PPpp')}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Last Active"
                          secondary={format(new Date(selectedSession.lastActiveAt), 'PPpp')}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Active Tokens"
                          secondary={selectedSession.tokenCount}
                        />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" gutterBottom>
                      Location
                    </Typography>
                    <List dense>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Location"
                          secondary={`${selectedSession.location?.city}, ${selectedSession.location?.country}`}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="IP Address"
                          secondary={selectedSession.location?.ip}
                        />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" gutterBottom>
                      Permissions
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                      {selectedSession.scopes.map((scope) => (
                        <Chip key={scope} label={scope} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDetails(false)}>Close</Button>
          <Button
            onClick={() => {
              setShowDetails(false);
              selectedSession && handleRevokeClick(selectedSession);
            }}
            color="error"
            variant="contained"
          >
            Sign Out This Session
          </Button>
        </DialogActions>
      </Dialog>

      {/* Revoke Session Dialog */}
      <Dialog open={showRevokeDialog} onClose={() => setShowRevokeDialog(false)}>
        <DialogTitle>Sign Out From Session?</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              This will sign you out from this device and revoke all associated tokens.
            </Typography>
          </Alert>
          {selectedSession && (
            <Typography variant="body2">
              Device: {selectedSession.deviceName}
              <br />
              Location: {selectedSession.location?.city}, {selectedSession.location?.country}
            </Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowRevokeDialog(false)}>Cancel</Button>
          <Button onClick={handleRevokeConfirm} color="error" variant="contained">
            Sign Out
          </Button>
        </DialogActions>
      </Dialog>

      {/* Revoke All Sessions Dialog */}
      <Dialog open={showRevokeAllDialog} onClose={() => setShowRevokeAllDialog(false)}>
        <DialogTitle>Sign Out From All Sessions?</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              This will sign you out from all devices except this one and revoke all associated tokens.
              You'll need to sign in again on other devices.
            </Typography>
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowRevokeAllDialog(false)}>Cancel</Button>
          <Button onClick={handleRevokeAllConfirm} color="error" variant="contained">
            Sign Out All
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};