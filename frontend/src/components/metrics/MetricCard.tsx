import React from 'react';
import {
  Card,
  CardContent,
  Box,
  Typography,
  Avatar,
  Chip,
  Skeleton,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  TrendingFlat as TrendingFlatIcon,
} from '@mui/icons-material';

interface MetricCardProps {
  title: string;
  value: string | number;
  trend?: number;
  trendLabel?: string;
  icon?: React.ReactNode;
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
  loading?: boolean;
  subtitle?: string;
  format?: 'number' | 'currency' | 'percentage';
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  trend,
  trendLabel,
  icon,
  color = 'primary',
  loading = false,
  subtitle,
  format = 'number',
}) => {
  const getTrendIcon = () => {
    if (trend === undefined || trend === 0) {
      return <TrendingFlatIcon fontSize="small" />;
    }
    return trend > 0 ? (
      <TrendingUpIcon fontSize="small" />
    ) : (
      <TrendingDownIcon fontSize="small" />
    );
  };

  const getTrendColor = () => {
    if (trend === undefined || trend === 0) return 'default';
    
    // For error metrics, negative trend is good
    if (color === 'error' || color === 'warning') {
      return trend < 0 ? 'success' : 'error';
    }
    
    // For positive metrics, positive trend is good
    return trend > 0 ? 'success' : 'error';
  };

  const formatValue = (val: string | number): string => {
    if (typeof val === 'string') return val;
    
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(val);
      case 'percentage':
        return `${val}%`;
      default:
        return val.toLocaleString();
    }
  };

  if (loading) {
    return (
      <Card sx={{ height: '100%' }}>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box sx={{ flexGrow: 1 }}>
              <Skeleton variant="text" width="60%" height={24} />
              <Skeleton variant="text" width="80%" height={40} sx={{ my: 1 }} />
              <Skeleton variant="text" width="40%" height={20} />
            </Box>
            <Skeleton variant="circular" width={40} height={40} />
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card 
      sx={{ 
        height: '100%',
        transition: 'all 0.3s ease',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: 4,
        },
      }}
    >
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="body2" color="textSecondary" gutterBottom>
              {title}
            </Typography>
            
            <Typography variant="h4" sx={{ my: 1, fontWeight: 'bold' }}>
              {formatValue(value)}
            </Typography>
            
            {subtitle && (
              <Typography variant="caption" color="textSecondary" display="block" sx={{ mb: 1 }}>
                {subtitle}
              </Typography>
            )}
            
            {trend !== undefined && (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <Chip
                  label={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      {getTrendIcon()}
                      <Typography variant="caption">
                        {Math.abs(trend)}% {trendLabel || 'vs last period'}
                      </Typography>
                    </Box>
                  }
                  size="small"
                  color={getTrendColor() as any}
                  variant="outlined"
                />
              </Box>
            )}
          </Box>
          
          {icon && (
            <Avatar
              sx={{
                bgcolor: `${color}.light`,
                color: `${color}.main`,
                width: 48,
                height: 48,
              }}
            >
              {icon}
            </Avatar>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};