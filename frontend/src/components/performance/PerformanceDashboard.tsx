import React, { useEffect, useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Tooltip,
  IconButton,
  Alert,
} from '@mui/material';
import {
  Speed,
  Memory,
  Storage,
  NetworkCheck,
  Refresh,
  Info,
} from '@mui/icons-material';
import { usePerformanceMetrics, getResourceTimings, analyzeBundleSize, getMemoryUsage } from '@/utils/performance';
import { cache } from '@/utils/cache';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon: React.ReactNode;
  status: 'good' | 'warning' | 'error';
  tooltip?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, unit, icon, status, tooltip }) => {
  const statusColors = {
    good: 'success.main',
    warning: 'warning.main',
    error: 'error.main',
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <Box sx={{ color: statusColors[status], mr: 1 }}>
            {icon}
          </Box>
          <Typography variant="h6" component="h3">
            {title}
          </Typography>
          {tooltip && (
            <Tooltip title={tooltip}>
              <IconButton size="small" sx={{ ml: 'auto' }}>
                <Info fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>
        <Typography variant="h4" component="p">
          {value}
          {unit && <Typography component="span" variant="h6" color="text.secondary"> {unit}</Typography>}
        </Typography>
      </CardContent>
    </Card>
  );
};

export const PerformanceDashboard: React.FC = () => {
  const metrics = usePerformanceMetrics();
  const [resources, setResources] = useState(getResourceTimings());
  const [bundleInfo, setBundleInfo] = useState(analyzeBundleSize());
  const [memoryUsage, setMemoryUsage] = useState(getMemoryUsage());
  const [cacheStats, setCacheStats] = useState(cache.getStats());

  useEffect(() => {
    const interval = setInterval(() => {
      setResources(getResourceTimings());
      setBundleInfo(analyzeBundleSize());
      setMemoryUsage(getMemoryUsage());
      setCacheStats(cache.getStats());
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const getMetricStatus = (metric: string, value?: number): 'good' | 'warning' | 'error' => {
    if (!value) return 'good';
    
    const thresholds: Record<string, { good: number; warning: number }> = {
      FCP: { good: 1800, warning: 3000 },
      LCP: { good: 2500, warning: 4000 },
      FID: { good: 100, warning: 300 },
      CLS: { good: 0.1, warning: 0.25 },
      TTFB: { good: 800, warning: 1800 },
    };

    const threshold = thresholds[metric];
    if (!threshold) return 'good';

    if (value <= threshold.good) return 'good';
    if (value <= threshold.warning) return 'warning';
    return 'error';
  };

  const handleRefresh = () => {
    window.location.reload();
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5">Performance Dashboard</Typography>
        <IconButton onClick={handleRefresh}>
          <Refresh />
        </IconButton>
      </Box>

      {/* Core Web Vitals */}
      <Typography variant="h6" gutterBottom>Core Web Vitals</Typography>
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="FCP"
            value={metrics.FCP || '-'}
            unit="ms"
            icon={<Speed />}
            status={getMetricStatus('FCP', metrics.FCP)}
            tooltip="First Contentful Paint - Time when the first text or image is painted"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="LCP"
            value={metrics.LCP || '-'}
            unit="ms"
            icon={<Speed />}
            status={getMetricStatus('LCP', metrics.LCP)}
            tooltip="Largest Contentful Paint - Time when the largest text or image is painted"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="FID"
            value={metrics.FID || '-'}
            unit="ms"
            icon={<Speed />}
            status={getMetricStatus('FID', metrics.FID)}
            tooltip="First Input Delay - Time from when a user first interacts to when the browser responds"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <MetricCard
            title="CLS"
            value={metrics.CLS || '-'}
            unit=""
            icon={<Speed />}
            status={getMetricStatus('CLS', metrics.CLS)}
            tooltip="Cumulative Layout Shift - Measure of visual stability"
          />
        </Grid>
      </Grid>

      {/* Bundle & Memory Info */}
      <Typography variant="h6" gutterBottom>Resource Usage</Typography>
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Bundle Size Analysis
            </Typography>
            <Box sx={{ mb: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Total JavaScript: {bundleInfo.totalSizeMB} MB
              </Typography>
              <LinearProgress
                variant="determinate"
                value={Math.min((bundleInfo.totalSize / (5 * 1024 * 1024)) * 100, 100)}
                sx={{ mt: 1 }}
              />
            </Box>
            <Typography variant="caption" color="text.secondary">
              {bundleInfo.scripts.length} script files loaded
            </Typography>
          </Paper>
        </Grid>
        
        {memoryUsage && (
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Memory Usage
              </Typography>
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  JS Heap: {memoryUsage.usedJSHeapSize} / {memoryUsage.totalJSHeapSize} MB
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={(memoryUsage.usedJSHeapSize / memoryUsage.totalJSHeapSize) * 100}
                  sx={{ mt: 1 }}
                />
              </Box>
              <Typography variant="caption" color="text.secondary">
                Limit: {memoryUsage.jsHeapSizeLimit} MB
              </Typography>
            </Paper>
          </Grid>
        )}
      </Grid>

      {/* Cache Statistics */}
      <Typography variant="h6" gutterBottom>Cache Performance</Typography>
      <Paper sx={{ p: 2, mb: 4 }}>
        \<Grid container spacing={2}>
          <Grid item xs={6} sm={3}>
            <Typography variant="body2" color="text.secondary">Items Cached</Typography>
            <Typography variant="h6">{cacheStats.itemCount}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="body2" color="text.secondary">Cache Size</Typography>
            <Typography variant="h6">{cacheStats.totalSizeKB} KB</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="body2" color="text.secondary">Expired Items</Typography>
            <Typography variant="h6">{cacheStats.expiredCount}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="body2" color="text.secondary">Hit Rate</Typography>
            <Typography variant="h6">-</Typography>
          </Grid>
        </Grid>
      </Paper>

      {/* Resource Loading */}
      <Typography variant="h6" gutterBottom>Resource Loading</Typography>
      <Paper sx={{ p: 2 }}>
        <List dense>
          {resources.slice(0, 10).map((resource, index) => (
            <ListItem key={index}>
              <ListItemText
                primary={resource.name.split('/').pop()}
                secondary={`${resource.type} • ${resource.duration}ms`}
              />
              <ListItemSecondaryAction>
                <Chip
                  label={resource.cached ? 'Cached' : 'Network'}
                  size="small"
                  color={resource.cached ? 'success' : 'default'}
                />
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
        {resources.length > 10 && (
          <Typography variant="caption" color="text.secondary" sx={{ pl: 2 }}>
            And {resources.length - 10} more resources...
          </Typography>
        )}
      </Paper>

      <Alert severity="info" sx={{ mt: 2 }}>
        Performance metrics are collected using the Performance Observer API. Some metrics may not be available in all browsers.
      </Alert>
    </Box>
  );
};