import React from 'react';
import {
  Card,
  CardContent,
  Grid,
  Typography,
  Box,
  Divider,
  Skeleton,
  useTheme,
} from '@mui/material';
import { SvgIconComponent } from '@mui/icons-material';

interface Metric {
  label: string;
  value: string | number;
  change?: number;
  icon?: SvgIconComponent;
  color?: 'primary' | 'secondary' | 'success' | 'error' | 'warning' | 'info';
}

interface MetricsGridProps {
  title?: string;
  metrics: Metric[];
  columns?: 2 | 3 | 4;
  loading?: boolean;
}

export const MetricsGrid: React.FC<MetricsGridProps> = ({
  title,
  metrics,
  columns = 4,
  loading = false,
}) => {
  const theme = useTheme();

  const gridColumns = 12 / columns;

  if (loading) {
    return (
      <Card>
        <CardContent>
          {title && (
            <>
              <Skeleton variant="text" width="30%" height={32} />
              <Box mb={2} />
            </>
          )}
          <Grid container spacing={2}>
            {Array.from({ length: columns }).map((_, index) => (
              <Grid item xs={12} sm={6} md={gridColumns} key={index}>
                <Skeleton variant="text" width="60%" height={20} />
                <Skeleton variant="text" width="80%" height={32} sx={{ my: 1 }} />
                <Skeleton variant="text" width="40%" height={16} />
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent>
        {title && (
          <Typography variant="h6" gutterBottom sx={{ mb: 3 }}>
            {title}
          </Typography>
        )}
        
        <Grid container spacing={2}>
          {metrics.map((metric, index) => {
            const Icon = metric.icon;
            const isLastInRow = (index + 1) % columns !== 0;
            const isLastRow = index >= metrics.length - columns;

            return (
              <Grid item xs={12} sm={6} md={gridColumns} key={index}>
                <Box
                  sx={{
                    pr: isLastInRow ? 2 : 0,
                    borderRight: isLastInRow ? `1px solid ${theme.palette.divider}` : 'none',
                    pb: !isLastRow ? 2 : 0,
                  }}
                >
                  <Box display="flex" alignItems="center" gap={1} mb={1}>
                    {Icon && (
                      <Icon
                        sx={{
                          fontSize: 20,
                          color: metric.color ? theme.palette[metric.color].main : theme.palette.text.secondary,
                        }}
                      />
                    )}
                    <Typography variant="body2" color="textSecondary">
                      {metric.label}
                    </Typography>
                  </Box>
                  
                  <Typography variant="h5" sx={{ fontWeight: 600, mb: 0.5 }}>
                    {typeof metric.value === 'number' 
                      ? new Intl.NumberFormat('en-US').format(metric.value)
                      : metric.value
                    }
                  </Typography>
                  
                  {metric.change !== undefined && (
                    <Typography
                      variant="caption"
                      color={metric.change >= 0 ? 'success.main' : 'error.main'}
                      sx={{ fontWeight: 500 }}
                    >
                      {metric.change >= 0 ? '+' : ''}{metric.change}%
                    </Typography>
                  )}
                </Box>
              </Grid>
            );
          })}
        </Grid>
      </CardContent>
    </Card>
  );
};