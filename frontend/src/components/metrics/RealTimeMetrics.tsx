import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Grid,
  LinearProgress,
  Chip,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Alert,
  Badge,
  IconButton,
  Tooltip,
  Fade,
  Grow,
} from '@mui/material';
import {
  FiberManualRecord as LiveIcon,
  Person as PersonIcon,
  VpnKey as KeyIcon,
  Speed as SpeedIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Refresh as RefreshIcon,
  Timeline as TimelineIcon,
  TrendingUp as TrendingUpIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';

interface RealTimeEvent {
  id: string;
  type: 'authentication' | 'token_issued' | 'token_revoked' | 'error' | 'security';
  message: string;
  timestamp: Date;
  severity: 'info' | 'warning' | 'error' | 'success';
  metadata?: {
    userId?: string;
    clientId?: string;
    ip?: string;
    location?: string;
  };
}

interface RealTimeStats {
  activeUsers: number;
  requestsPerSecond: number;
  averageLatency: number;
  errorRate: number;
  activeTokens: number;
  securityEvents: number;
}

export const RealTimeMetrics: React.FC = () => {
  const [events, setEvents] = useState<RealTimeEvent[]>([]);
  const [stats, setStats] = useState<RealTimeStats>({
    activeUsers: 0,
    requestsPerSecond: 0,
    averageLatency: 0,
    errorRate: 0,
    activeTokens: 0,
    securityEvents: 0,
  });
  const [isConnected, setIsConnected] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  useEffect(() => {
    // Simulate real-time updates
    const interval = setInterval(() => {
      updateMetrics();
      generateRandomEvent();
      setLastUpdate(new Date());
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const updateMetrics = () => {
    setStats({
      activeUsers: Math.floor(Math.random() * 1000) + 4000,
      requestsPerSecond: Math.floor(Math.random() * 500) + 800,
      averageLatency: Math.floor(Math.random() * 50) + 80,
      errorRate: Math.random() * 2,
      activeTokens: Math.floor(Math.random() * 5000) + 20000,
      securityEvents: Math.floor(Math.random() * 10),
    });
  };

  const generateRandomEvent = () => {
    const eventTypes: RealTimeEvent['type'][] = [
      'authentication',
      'token_issued',
      'token_revoked',
      'error',
      'security',
    ];
    
    const eventMessages = {
      authentication: [
        'User authenticated successfully',
        'OAuth authorization completed',
        'Multi-factor authentication passed',
      ],
      token_issued: [
        'Access token issued',
        'Refresh token generated',
        'ID token created',
      ],
      token_revoked: [
        'Token revoked by user',
        'Token expired and removed',
        'Client access revoked',
      ],
      error: [
        'Authentication failed: Invalid credentials',
        'Rate limit exceeded',
        'Token validation failed',
      ],
      security: [
        'Suspicious login attempt detected',
        'IP blocked due to multiple failures',
        'PKCE challenge failed',
      ],
    };

    const type = eventTypes[Math.floor(Math.random() * eventTypes.length)];
    const messages = eventMessages[type];
    const message = messages[Math.floor(Math.random() * messages.length)];
    
    const severityMap = {
      authentication: 'success',
      token_issued: 'info',
      token_revoked: 'warning',
      error: 'error',
      security: 'error',
    };

    const newEvent: RealTimeEvent = {
      id: Math.random().toString(36).substr(2, 9),
      type,
      message,
      timestamp: new Date(),
      severity: severityMap[type] as RealTimeEvent['severity'],
      metadata: {
        userId: `user_${Math.floor(Math.random() * 1000)}`,
        clientId: `client_${Math.floor(Math.random() * 100)}`,
        ip: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
        location: ['San Francisco', 'New York', 'London', 'Tokyo'][Math.floor(Math.random() * 4)],
      },
    };

    setEvents(prev => [newEvent, ...prev.slice(0, 9)]);
  };

  const getEventIcon = (type: RealTimeEvent['type']) => {
    switch (type) {
      case 'authentication':
        return <PersonIcon />;
      case 'token_issued':
        return <KeyIcon />;
      case 'token_revoked':
        return <KeyIcon />;
      case 'error':
        return <ErrorIcon />;
      case 'security':
        return <SecurityIcon />;
      default:
        return <InfoIcon />;
    }
  };

  const getEventColor = (severity: RealTimeEvent['severity']) => {
    switch (severity) {
      case 'success':
        return 'success.main';
      case 'warning':
        return 'warning.main';
      case 'error':
        return 'error.main';
      default:
        return 'info.main';
    }
  };

  const getLatencyColor = (latency: number) => {
    if (latency < 100) return 'success';
    if (latency < 200) return 'warning';
    return 'error';
  };

  const getErrorRateColor = (rate: number) => {
    if (rate < 0.5) return 'success';
    if (rate < 1) return 'warning';
    return 'error';
  };

  return (
    <Box sx={{ mb: 3 }}>
      {/* Connection Status */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Badge
            color={isConnected ? 'success' : 'error'}
            variant="dot"
            sx={{
              '& .MuiBadge-badge': {
                animation: isConnected ? 'pulse 2s infinite' : 'none',
              },
              '@keyframes pulse': {
                '0%': { opacity: 1 },
                '50%': { opacity: 0.4 },
                '100%': { opacity: 1 },
              },
            }}
          >
            <LiveIcon color={isConnected ? 'success' : 'error'} />
          </Badge>
          <Typography variant="h6">
            Real-Time Metrics
          </Typography>
          <Chip
            label={isConnected ? 'Live' : 'Disconnected'}
            size="small"
            color={isConnected ? 'success' : 'error'}
          />
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" color="textSecondary">
            Last update: {formatDistanceToNow(lastUpdate, { addSuffix: true })}
          </Typography>
          <Tooltip title="Refresh">
            <IconButton size="small" onClick={updateMetrics}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={2}>
        {/* Live Stats */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Live Performance Indicators
              </Typography>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid item xs={6} sm={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Fade in={true} timeout={1000}>
                      <Typography variant="h4" color="primary">
                        {stats.activeUsers.toLocaleString()}
                      </Typography>
                    </Fade>
                    <Typography variant="caption" color="textSecondary">
                      Active Users
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Fade in={true} timeout={1000}>
                      <Typography variant="h4" color="secondary">
                        {stats.requestsPerSecond}
                      </Typography>
                    </Fade>
                    <Typography variant="caption" color="textSecondary">
                      Requests/sec
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Fade in={true} timeout={1000}>
                      <Typography variant="h4" color={getLatencyColor(stats.averageLatency)}>
                        {stats.averageLatency}ms
                      </Typography>
                    </Fade>
                    <Typography variant="caption" color="textSecondary">
                      Avg Latency
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Chip
                      label={`${stats.errorRate.toFixed(2)}%`}
                      color={getErrorRateColor(stats.errorRate)}
                      sx={{ fontSize: '1.2rem', px: 2, py: 1 }}
                    />
                    <Typography variant="caption" color="textSecondary" display="block" sx={{ mt: 1 }}>
                      Error Rate
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color="info.main">
                      {stats.activeTokens.toLocaleString()}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Active Tokens
                    </Typography>
                  </Box>
                </Grid>
                <Grid item xs={6} sm={4}>
                  <Box sx={{ textAlign: 'center' }}>
                    <Typography variant="h4" color={stats.securityEvents > 5 ? 'error' : 'success'}>
                      {stats.securityEvents}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      Security Events
                    </Typography>
                  </Box>
                </Grid>
              </Grid>

              {/* Activity Indicators */}
              <Box sx={{ mt: 3 }}>
                <Typography variant="caption" color="textSecondary">
                  System Load
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={(stats.requestsPerSecond / 1500) * 100}
                  color={stats.requestsPerSecond > 1200 ? 'error' : stats.requestsPerSecond > 1000 ? 'warning' : 'success'}
                  sx={{ mt: 1, height: 8, borderRadius: 1 }}
                />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Live Event Feed */}
        <Grid item xs={12} md={4}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Live Event Feed
              </Typography>
              <List dense sx={{ maxHeight: 280, overflow: 'auto' }}>
                {events.map((event, index) => (
                  <Grow in={true} timeout={500 * (index + 1)} key={event.id}>
                    <ListItem disableGutters>
                      <ListItemAvatar sx={{ minWidth: 40 }}>
                        <Avatar
                          sx={{
                            width: 32,
                            height: 32,
                            bgcolor: getEventColor(event.severity),
                          }}
                        >
                          {getEventIcon(event.type)}
                        </Avatar>
                      </ListItemAvatar>
                      <ListItemText
                        primary={
                          <Typography variant="body2" noWrap>
                            {event.message}
                          </Typography>
                        }
                        secondary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                            <Typography variant="caption" color="textSecondary">
                              {formatDistanceToNow(event.timestamp, { addSuffix: true })}
                            </Typography>
                            {event.metadata?.location && (
                              <>
                                <Typography variant="caption" color="textSecondary">•</Typography>
                                <Typography variant="caption" color="textSecondary">
                                  {event.metadata.location}
                                </Typography>
                              </>
                            )}
                          </Box>
                        }
                      />
                    </ListItem>
                  </Grow>
                ))}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Alerts */}
      {stats.errorRate > 1 && (
        <Grow in={true}>
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="body2">
              Error rate is above normal threshold ({stats.errorRate.toFixed(2)}%). Monitoring for potential issues.
            </Typography>
          </Alert>
        </Grow>
      )}
      
      {stats.securityEvents > 5 && (
        <Grow in={true}>
          <Alert severity="error" sx={{ mt: 2 }}>
            <Typography variant="body2">
              Multiple security events detected ({stats.securityEvents}). Review security logs for details.
            </Typography>
          </Alert>
        </Grow>
      )}
    </Box>
  );
};