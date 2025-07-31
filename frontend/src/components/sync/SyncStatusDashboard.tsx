import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Button,
  Chip,
  LinearProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Switch,
  Tooltip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Skeleton } from '@mui/material';
import {
  Sync as SyncIcon,
  Schedule as ScheduleIcon,
  History as HistoryIcon,
  Error as ErrorIcon,
  CheckCircle as SuccessIcon,
  Warning as WarningIcon,
  PlayArrow as PlayIcon,
  Refresh as RefreshIcon,
  CloudSync as CloudSyncIcon } from '@mui/icons-material';
import { format, formatDistanceToNow } from 'date-fns';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { SyncPlatform, SyncStatus } from '@/types/sync';
import { syncService } from '@/services/api/sync';
import { useModels } from '@/hooks/useModels';

interface SyncStatusDashboardProps {
  modelId?: string;
  agencyId?: string;
}

const SyncStatusDashboard: React.FC<SyncStatusDashboardProps> = ({ modelId, agencyId }) => {
  const [selectedModel, setSelectedModel] = useState<string>(modelId || '');
  const [showScheduleDialog, setShowScheduleDialog] = useState(false);
  const [scheduleData, setScheduleData] = useState({
    platform: SyncPlatform.ALL,
    delay_minutes: 0 });
  const [forceFullSync, setForceFullSync] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const queryClient = useQueryClient();
  const { data: models } = useModels();

  // Get sync stats
  const { data: stats, isPending: statsLoading } = useQuery({
    queryKey: ['sync-stats', agencyId],
    queryFn: () => syncService.getStats(agencyId),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Get sync status for selected model
  const { data: status, isPending: isStatusLoading } = useQuery({
    queryKey: ['sync-status', selectedModel],
    queryFn: () => syncService.getStatus(selectedModel),
    enabled: !!selectedModel,
    refetchInterval: 5000, // Refresh every 5 seconds when running
  });

  // Get sync history
  const { data: history } = useQuery({
    queryKey: ['sync-history', selectedModel],
    queryFn: () => syncService.getHistory(selectedModel, 20),
    enabled: !!selectedModel && showHistory });

  // Sync now mutation
  const syncNow = useMutation({
    mutationFn: (platform: SyncPlatform) => 
      syncService.syncNow({
        model_id: selectedModel,
        platform,
        force_full_sync: forceFullSync }),
    onSuccess: () => {
      toast.success('Sync started successfully');
      queryClient.invalidateQueries({ queryKey: ['sync-status'] });
      queryClient.invalidateQueries({ queryKey: ['sync-stats'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start sync');
    } });

  // Schedule sync mutation
  const scheduleSync = useMutation({
    mutationFn: () => 
      syncService.scheduleSync({
        model_id: selectedModel,
        platform: scheduleData.platform,
        delay_minutes: scheduleData.delay_minutes }),
    onSuccess: () => {
      toast.success('Sync scheduled successfully');
      setShowScheduleDialog(false);
      queryClient.invalidateQueries({ queryKey: ['sync-status'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to schedule sync');
    } });

  // Sync all models
  const syncAll = useMutation({
    mutationFn: (platform: SyncPlatform) => 
      syncService.syncAll(platform, agencyId),
    onSuccess: () => {
      toast.success('Bulk sync started for all models');
      queryClient.invalidateQueries({ queryKey: ['sync-stats'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start bulk sync');
    } });

  // Auto-select first model if none selected
  useEffect(() => {
    if (!selectedModel && models?.length > 0) {
      setSelectedModel(models[0].id);
    }
  }, [models, selectedModel]);

  const getStatusColor = (status: SyncStatus): 'default' | 'primary' | 'success' | 'error' | 'warning' => {
    switch (status) {
      case SyncStatus.PENDING:
        return 'default';
      case SyncStatus.RUNNING:
        return 'primary';
      case SyncStatus.COMPLETED:
        return 'success';
      case SyncStatus.FAILED:
        return 'error';
      case SyncStatus.CANCELLED:
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: SyncStatus) => {
    switch (status) {
      case SyncStatus.RUNNING:
        return <SyncIcon className="rotating" />;
      case SyncStatus.COMPLETED:
        return <SuccessIcon />;
      case SyncStatus.FAILED:
        return <ErrorIcon />;
      case SyncStatus.CANCELLED:
        return <WarningIcon />;
      default:
        return <SyncIcon />;
    }
  };

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`;
  };

  return (
    <Box>
      {/* Stats Overview */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Syncs Today
                  </Typography>
                  <Typography variant="h4">
                    {statsLoading ? <Skeleton width={60} /> : stats?.total_syncs_today || 0}
                  </Typography>
                </Box>
                <CloudSyncIcon color="primary" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Success Rate
                  </Typography>
                  <Typography variant="h4">
                    {statsLoading ? (
                      <Skeleton width={60} />
                    ) : stats && stats.total_syncs_today > 0 ? (
                      `${Math.round((stats.successful_syncs / stats.total_syncs_today) * 100)}%`
                    ) : (
                      '0%'
                    )}
                  </Typography>
                </Box>
                <SuccessIcon color="success" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Avg Duration
                  </Typography>
                  <Typography variant="h4">
                    {statsLoading ? (
                      <Skeleton width={60} />
                    ) : (
                      formatDuration(stats?.average_sync_duration || 0)
                    )}
                  </Typography>
                </Box>
                <ScheduleIcon color="action" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Box>
                  <Typography color="text.secondary" gutterBottom>
                    Records Synced
                  </Typography>
                  <Typography variant="h4">
                    {statsLoading ? (
                      <Skeleton width={60} />
                    ) : (
                      Object.values(stats?.total_records_synced || {}).reduce((a, b) => a + b, 0)
                    )}
                  </Typography>
                </Box>
                <HistoryIcon color="action" sx={{ fontSize: 40 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Model Sync Control */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">Model Sync Control</Typography>
            <Box display="flex" gap={1}>
              <Button
                size="small"
                startIcon={<RefreshIcon />}
                onClick={() => queryClient.invalidateQueries()}
              >
                Refresh
              </Button>
              <Button
                size="small"
                variant="contained"
                startIcon={<CloudSyncIcon />}
                onClick={() => syncAll.mutate(SyncPlatform.ALL)}
                disabled={syncAll.isPending}
              >
                Sync All Models
              </Button>
            </Box>
          </Box>

          {/* Model Selection */}
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <FormControl fullWidth size="small">
                <InputLabel>Select Model</InputLabel>
                <Select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  label="Select Model"
                >
                  {models?.map((model) => (
                    <MenuItem key={model.id} value={model.id}>
                      {model.stage_name || model.username}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} md={8}>
              {selectedModel && status && (
                <Box display="flex" alignItems="center" gap={2}>
                  <Chip
                    icon={getStatusIcon(status.status)}
                    label={status.status}
                    color={getStatusColor(status.status)}
                  />
                  
                  {status.platforms.inflow && (
                    <Tooltip title="Inflow configured">
                      <Chip
                        label="Inflow"
                        size="small"
                        color={status.platforms.inflow.configured ? 'success' : 'default'}
                      />
                    </Tooltip>
                  )}
                  
                  {status.platforms.onlyfans && (
                    <Tooltip title="OnlyFans configured">
                      <Chip
                        label="OnlyFans"
                        size="small"
                        color={status.platforms.onlyfans.configured ? 'success' : 'default'}
                      />
                    </Tooltip>
                  )}

                  <FormControlLabel
                    control={
                      <Switch
                        checked={forceFullSync}
                        onChange={(e) => setForceFullSync(e.target.checked)}
                        size="small"
                      />
                    }
                    label="Force Full Sync"
                  />
                </Box>
              )}
            </Grid>
          </Grid>

          {/* Sync Actions */}
          {selectedModel && (
            <Box mt={3} display="flex" gap={2} flexWrap="wrap">
              <Button
                variant="contained"
                startIcon={<PlayIcon />}
                onClick={() => syncNow.mutate(SyncPlatform.ALL)}
                disabled={syncNow.isPending || status?.status === SyncStatus.RUNNING}
              >
                Sync All Platforms
              </Button>
              
              {status?.platforms.inflow?.configured && (
                <Button
                  variant="outlined"
                  startIcon={<SyncIcon />}
                  onClick={() => syncNow.mutate(SyncPlatform.INFLOW)}
                  disabled={syncNow.isPending || status?.status === SyncStatus.RUNNING}
                >
                  Sync Inflow
                </Button>
              )}
              
              {status?.platforms.onlyfans?.configured && (
                <Button
                  variant="outlined"
                  startIcon={<SyncIcon />}
                  onClick={() => syncNow.mutate(SyncPlatform.ONLYFANS)}
                  disabled={syncNow.isPending || status?.status === SyncStatus.RUNNING}
                >
                  Sync OnlyFans
                </Button>
              )}
              
              <Button
                variant="outlined"
                startIcon={<ScheduleIcon />}
                onClick={() => setShowScheduleDialog(true)}
              >
                Schedule Sync
              </Button>
              
              <Button
                variant="outlined"
                startIcon={<HistoryIcon />}
                onClick={() => setShowHistory(!showHistory)}
              >
                {showHistory ? 'Hide' : 'Show'} History
              </Button>
            </Box>
          )}

          {/* Progress Bar */}
          {status?.status === SyncStatus.RUNNING && (
            <Box mt={2}>
              <LinearProgress />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                Sync in progress...
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Sync History */}
      {showHistory && selectedModel && (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Sync History
            </Typography>
            
            {history && history.length > 0 ? (
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Started</TableCell>
                      <TableCell>Duration</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Platforms</TableCell>
                      <TableCell>Records</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {history.map((item) => {
                      const duration = item.completed_at
                        ? (new Date(item.completed_at).getTime() - new Date(item.started_at).getTime()) / 1000
                        : null;
                      
                      return (
                        <TableRow key={item.sync_id}>
                          <TableCell>
                            <Tooltip title={format(new Date(item.started_at), 'PPpp')}>
                              <span>{formatDistanceToNow(new Date(item.started_at), { addSuffix: true })}</span>
                            </Tooltip>
                          </TableCell>
                          <TableCell>
                            {duration ? formatDuration(duration) : '-'}
                          </TableCell>
                          <TableCell>
                            <Chip
                              size="small"
                              label={item.status}
                              color={getStatusColor(item.status)}
                            />
                          </TableCell>
                          <TableCell>
                            {Object.keys(item.platforms).join(', ') || '-'}
                          </TableCell>
                          <TableCell>
                            {Object.values(item.platforms).reduce((total, platform: any) => {
                              if (typeof platform === 'object') {
                                return total + 
                                  (platform.subscribers?.added || 0) +
                                  (platform.transactions?.added || 0) +
                                  (platform.content?.added || 0);
                              }
                              return total;
                            }, 0)}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Alert severity="info">No sync history available</Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Schedule Sync Dialog */}
      <Dialog open={showScheduleDialog} onClose={() => setShowScheduleDialog(false)}>
        <DialogTitle>Schedule Sync</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} sx={{ pt: 1, minWidth: 300 }}>
            <FormControl fullWidth>
              <InputLabel>Platform</InputLabel>
              <Select
                value={scheduleData.platform}
                onChange={(e) => setScheduleData({ ...scheduleData, platform: e.target.value as SyncPlatform })}
                label="Platform"
              >
                <MenuItem value={SyncPlatform.ALL}>All Platforms</MenuItem>
                <MenuItem value={SyncPlatform.INFLOW}>Inflow Only</MenuItem>
                <MenuItem value={SyncPlatform.ONLYFANS}>OnlyFans Only</MenuItem>
              </Select>
            </FormControl>
            
            <FormControl fullWidth>
              <InputLabel>Delay</InputLabel>
              <Select
                value={scheduleData.delay_minutes}
                onChange={(e) => setScheduleData({ ...scheduleData, delay_minutes: Number(e.target.value) })}
                label="Delay"
              >
                <MenuItem value={0}>Now</MenuItem>
                <MenuItem value={15}>15 minutes</MenuItem>
                <MenuItem value={30}>30 minutes</MenuItem>
                <MenuItem value={60}>1 hour</MenuItem>
                <MenuItem value={120}>2 hours</MenuItem>
                <MenuItem value={240}>4 hours</MenuItem>
                <MenuItem value={480}>8 hours</MenuItem>
                <MenuItem value={1440}>24 hours</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowScheduleDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={() => scheduleSync.mutate()}
            disabled={scheduleSync.isPending}
          >
            Schedule
          </Button>
        </DialogActions>
      </Dialog>

      <style jsx>{`
        @keyframes rotate {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .rotating {
          animation: rotate 2s linear infinite;
        }
      `}</style>
    </Box>
  );
};

export default SyncStatusDashboard;
