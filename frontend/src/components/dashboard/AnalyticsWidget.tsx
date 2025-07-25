import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Skeleton,
  useTheme,
} from '@mui/material';
import { TrendingUp, TrendingDown } from '@mui/icons-material';

interface AnalyticsWidgetProps {
  title: string;
  value: string | number;
  previousValue?: string | number;
  format?: 'number' | 'currency' | 'percentage';
  icon?: React.ReactNode;
  color?: 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info';
  progress?: number;
  loading?: boolean;
  onClick?: () => void;
}

export const AnalyticsWidget: React.FC<AnalyticsWidgetProps> = ({
  title,
  value,
  previousValue,
  format = 'number',
  icon,
  color = 'primary',
  progress,
  loading = false,
  onClick,
}) => {
  const theme = useTheme();

  const formatValue = (val: string | number): string => {
    if (typeof val === 'string') return val;
    
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
        }).format(val);
      case 'percentage':
        return `${val}%`;
      default:
        return new Intl.NumberFormat('en-US').format(val);
    }
  };

  const calculateChange = (): { value: number; isPositive: boolean } | null => {
    if (!previousValue || typeof value !== 'number' || typeof previousValue !== 'number') {
      return null;
    }
    
    const change = ((value - previousValue) / previousValue) * 100;
    return {
      value: Math.abs(change),
      isPositive: change >= 0,
    };
  };

  const change = calculateChange();

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Skeleton variant="text" width="60%" height={24} />
          <Skeleton variant="text" width="80%" height={40} sx={{ my: 1 }} />
          <Skeleton variant="text" width="40%" height={20} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      sx={{
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.3s ease',
        '&:hover': onClick ? {
          transform: 'translateY(-4px)',
          boxShadow: theme.shadows[4],
        } : {},
      }}
      onClick={onClick}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start">
          <Box flex={1}>
            <Typography
              color="textSecondary"
              gutterBottom
              variant="body2"
              sx={{ fontWeight: 500 }}
            >
              {title}
            </Typography>
            
            <Typography
              variant="h4"
              component="div"
              sx={{ fontWeight: 600, my: 1 }}
            >
              {formatValue(value)}
            </Typography>

            {change && (
              <Box display="flex" alignItems="center" gap={0.5}>
                {change.isPositive ? (
                  <TrendingUp
                    sx={{
                      fontSize: 20,
                      color: theme.palette.success.main,
                    }}
                  />
                ) : (
                  <TrendingDown
                    sx={{
                      fontSize: 20,
                      color: theme.palette.error.main,
                    }}
                  />
                )}
                <Typography
                  variant="body2"
                  color={change.isPositive ? 'success.main' : 'error.main'}
                  sx={{ fontWeight: 500 }}
                >
                  {change.value.toFixed(1)}%
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  vs last period
                </Typography>
              </Box>
            )}
          </Box>

          {icon && (
            <Box
              sx={{
                backgroundColor: theme.palette[color].light,
                borderRadius: 2,
                p: 1.5,
                color: theme.palette[color].main,
              }}
            >
              {icon}
            </Box>
          )}
        </Box>

        {progress !== undefined && (
          <Box mt={2}>
            <Box display="flex" justifyContent="space-between" mb={0.5}>
              <Typography variant="caption" color="textSecondary">
                Progress
              </Typography>
              <Typography variant="caption" color="textSecondary">
                {progress}%
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={progress}
              color={color}
              sx={{
                height: 6,
                borderRadius: 3,
                backgroundColor: theme.palette.action.hover,
              }}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );
};