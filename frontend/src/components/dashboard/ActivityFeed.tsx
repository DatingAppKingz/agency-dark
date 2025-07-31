import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Avatar,
  Chip,
  IconButton,
  Skeleton,
  useTheme,
} from '@mui/material';
import {
  PersonAdd,
  AttachMoney,
  Message,
  TrendingUp,
  Warning,
  CheckCircle,
  Info,
  MoreVert,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';

export type ActivityType = 'user_joined' | 'payment' | 'message' | 'achievement' | 'alert' | 'success' | 'info';

interface Activity {
  id: string;
  type: ActivityType;
  title: string;
  description?: string;
  timestamp: Date;
  user?: {
    name: string;
    avatar?: string;
  };
  metadata?: Record<string, any>;
}

interface ActivityFeedProps {
  activities: Activity[];
  maxItems?: number;
  loading?: boolean;
  onItemClick?: (activity: Activity) => void;
}

export const ActivityFeed: React.FC<ActivityFeedProps> = ({
  activities,
  maxItems = 5,
  loading = false,
  onItemClick,
}) => {
  const theme = useTheme();

  const getActivityIcon = (type: ActivityType) => {
    const iconProps = { sx: { fontSize: 24 } };
    
    switch (type) {
      case 'user_joined':
        return <PersonAdd {...iconProps} />;
      case 'payment':
        return <AttachMoney {...iconProps} />;
      case 'message':
        return <Message {...iconProps} />;
      case 'achievement':
        return <TrendingUp {...iconProps} />;
      case 'alert':
        return <Warning {...iconProps} />;
      case 'success':
        return <CheckCircle {...iconProps} />;
      case 'info':
      default:
        return <Info {...iconProps} />;
    }
  };

  const getActivityColor = (type: ActivityType) => {
    switch (type) {
      case 'user_joined':
        return theme.palette.primary.main;
      case 'payment':
        return theme.palette.success.main;
      case 'message':
        return theme.palette.info.main;
      case 'achievement':
        return theme.palette.secondary.main;
      case 'alert':
        return theme.palette.warning.main;
      case 'success':
        return theme.palette.success.main;
      case 'info':
      default:
        return theme.palette.info.main;
    }
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Skeleton variant="text" width="30%" height={32} sx={{ mb: 2 }} />
          <List>
            {Array.from({ length: maxItems }).map((_, index) => (
              <ListItem key={index} alignItems="flex-start">
                <ListItemAvatar>
                  <Skeleton variant="circular" width={40} height={40} />
                </ListItemAvatar>
                <ListItemText
                  primary={<Skeleton variant="text" width="60%" />}
                  secondary={<Skeleton variant="text" width="80%" />}
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>
    );
  }

  const displayActivities = activities.slice(0, maxItems);

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">Recent Activity</Typography>
          <IconButton size="small">
            <MoreVert />
          </IconButton>
        </Box>

        <List sx={{ p: 0 }}>
          {displayActivities.length === 0 ? (
            <Box textAlign="center" py={4}>
              <Typography variant="body2" color="textSecondary">
                No recent activity
              </Typography>
            </Box>
          ) : (
            displayActivities.map((activity, index) => (
              <ListItem
                key={activity.id}
                alignItems="flex-start"
                sx={{
                  px: 0,
                  cursor: onItemClick ? 'pointer' : 'default',
                  '&:hover': onItemClick ? {
                    backgroundColor: theme.palette.action.hover,
                  } : {},
                  borderBottom: index < displayActivities.length - 1 ? `1px solid ${theme.palette.divider}` : 'none',
                }}
                onClick={() => onItemClick?.(activity)}
              >
                <ListItemAvatar>
                  <Avatar
                    sx={{
                      backgroundColor: `${getActivityColor(activity.type)}20`,
                      color: getActivityColor(activity.type),
                    }}
                  >
                    {getActivityIcon(activity.type)}
                  </Avatar>
                </ListItemAvatar>
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {activity.title}
                      </Typography>
                      {activity.metadata?.amount && (
                        <Chip
                          label={`$${activity.metadata.amount}`}
                          size="small"
                          color="success"
                          sx={{ height: 20 }}
                        />
                      )}
                    </Box>
                  }
                  secondary={
                    <Box>
                      {activity.description && (
                        <Typography
                          variant="body2"
                          color="textSecondary"
                          sx={{ mt: 0.5 }}
                        >
                          {activity.description}
                        </Typography>
                      )}
                      <Typography
                        variant="caption"
                        color="textSecondary"
                        sx={{ display: 'block', mt: 0.5 }}
                      >
                        {formatDistanceToNow(activity.timestamp, { addSuffix: true })}
                      </Typography>
                    </Box>
                  }
                />
              </ListItem>
            ))
          )}
        </List>
      </CardContent>
    </Card>
  );
};
