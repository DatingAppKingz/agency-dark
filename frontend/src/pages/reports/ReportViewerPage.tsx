import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  IconButton,
  Paper,
  CircularProgress,
  Alert,
  Menu,
  MenuItem,
  Tooltip,
  Chip } from '@mui/material';
import {
  ArrowBack as BackIcon,
  Edit as EditIcon,
  Download as ExportIcon,
  Refresh as RefreshIcon,
  Share as ShareIcon,
  Schedule as ScheduleIcon,
  MoreVert as MoreIcon,
  Fullscreen as PrintIcon } from '@mui/icons-material';
import GridLayout, { WidthProvider } from 'react-grid-layout';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { format } from 'date-fns';
import { reportsService } from '@/services/api/reports';
import { ReportWidget, ReportTemplate } from '@/types/reports';
import ChartWidget from '@/components/reports/ChartWidget';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const ResponsiveGridLayout = WidthProvider(GridLayout);

const ReportViewerPage: React.FC = () => {
  const { templateId } = useParams();
  const navigate = useNavigate();
  const [widgets, setWidgets] = useState<ReportWidget[]>([]);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [setAutoRefreshTimer] = useState<NodeJS.Timeout | null>(null);

  // Fetch template
  const { data: template, isPending: loadingTemplate } = useQuery<ReportTemplate>({
    queryKey: ['report-template', templateId],
    queryFn: () => reportsService.getTemplate(templateId!),
    enabled: !!templateId,
    onSuccess: (data) => {
      // Initialize widgets from template
      const initialWidgets = data.widgets.map((w: any) => ({
        ...w,
        loading: true,
        data: null,
        error: null }));
      setWidgets(initialWidgets);
    } });

  // Fetch report data
  const { data: reportData, refetch: refetchData } = useQuery({
    queryKey: ['report-data', templateId, template?.dateRange, template?.globalFilters],
    queryFn: () => reportsService.getReportData(templateId!, {
      dateRange: template?.dateRange,
      filters: template?.globalFilters }),
    enabled: !!templateId && !!template,
    onSuccess: (data) => {
      // Update widgets with data
      const updatedWidgets = widgets.map(widget => {
        const widgetData = data.widgets.find(w => w.widgetId === widget.id);
        if (widgetData) {
          return { ...widget, data: widgetData.data, loading: false };
        }
        return { ...widget, loading: false, error: 'No data available' };
      });
      setWidgets(updatedWidgets);
      setRefreshing(false);
    },
    onError: () => {
      setRefreshing(false);
      toast.error('Failed to load report data');
    } });

  // Export report
  const exportReport = useMutation({
    mutationFn: (format: 'pdf' | 'excel' | 'csv') =>
      reportsService.exportReport(templateId!, format),
    onSuccess: () => {
      toast.success('Report export started. You will be notified when it\'s ready.');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to export report');
    } });

  // Setup auto-refresh
  useEffect(() => {
    if (template?.refreshInterval && template.refreshInterval > 0) {
      const timer = setInterval(() => {
        handleRefresh();
      }, template.refreshInterval * 1000);
      setAutoRefreshTimer(timer);

      return () => {
        if (timer) {
          clearInterval(timer);
        }
      };
    }
  }, [template?.refreshInterval]);

  const handleRefresh = () => {
    setRefreshing(true);
    refetchData();
  };

  const handleExport = (format: 'pdf' | 'excel' | 'csv') => {
    exportReport.mutate(format);
    setAnchorEl(null);
  };

  const handlePrint = () => {
    window.print();
    setAnchorEl(null);
  };

  const handleShare = () => {
    // TODO: Implement share functionality
    toast.info('Share functionality coming soon');
    setAnchorEl(null);
  };

  const handleSchedule = () => {
    // TODO: Navigate to schedule page
    navigate(`/dashboard/reports/schedule/${templateId}`);
    setAnchorEl(null);
  };

  if (loadingTemplate) {
    return (
      <Box
        sx={{
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center' }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!template) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert severity="error">Report template not found</Alert>
      </Container>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      {/* Header */}
      <Paper sx={{ p: 2, borderRadius: 0 }}>
        <Box display="flex" alignItems="center" justifyContent="space-between">
          <Box display="flex" alignItems="center" gap={2}>
            <IconButton onClick={() => navigate('/dashboard/reports')}>
              <BackIcon />
            </IconButton>
            <Box>
              <Typography variant="h5">{template?.name}</Typography>
              {template?.description && (
                <Typography variant="body2" color="text.secondary">
                  {template.description}
                </Typography>
              )}
            </Box>
          </Box>

          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="caption" color="text.secondary">
              Last updated: {reportData ? format(new Date(reportData.generatedAt), 'MMM d, yyyy HH:mm') : '-'}
            </Typography>
            
            <Tooltip title="Refresh">
              <IconButton onClick={handleRefresh} disabled={refreshing}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>

            <Tooltip title="Edit">
              <IconButton onClick={() => navigate(`/dashboard/reports/builder/${templateId}`)}>
                <EditIcon />
              </IconButton>
            </Tooltip>

            <IconButton onClick={(event) => setAnchorEl(event.currentTarget)}>
              <MoreIcon />
            </IconButton>
          </Box>
        </Box>

        {/* Date Range and Filters Info */}
        <Box display="flex" gap={2} mt={2}>
          {template.dateRange && (
            <Chip
              label={`Date: ${template.dateRange.type.replace(/_/g, ' ')}`}
              size="small"
            />
          )}
          {template.globalFilters.length > 0 && (
            <Chip
              label={`${template.globalFilters.length} filters applied`}
              size="small"
            />
          )}
          {template.refreshInterval && (
            <Chip
              icon={<ScheduleIcon />}
              label={`Auto-refresh: ${template.refreshInterval}s`}
              size="small"
              color="primary"
            />
          )}
        </Box>
      </Paper>

      {/* Report Content */}
      <Container maxWidth={false} sx={{ py: 3 }}>
        {widgets.length === 0 ? (
          <Alert severity="info">
            This report template has no widgets. Edit the template to add charts and visualizations.
          </Alert>
        ) : (
          <ResponsiveGridLayout
            className="layout"
            layout={widgets.map(w => ({
              i: w.id,
              x: w.x,
              y: w.y,
              w: w.w,
              h: w.h }))}
            cols={12}
            rowHeight={60}
            isDraggable={false}
            isResizable={false}
          >
            {widgets.map((widget) => (
              <Paper
                key={widget.id}
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  overflow: 'hidden' }}
              >
                <Box
                  sx={{
                    p: 2,
                    borderBottom: 1,
                    borderColor: 'divider',
                    bgcolor: 'background.default' }}
                >
                  <Typography variant="h6" noWrap>
                    {widget.chartConfig.title}
                  </Typography>
                  {widget.chartConfig.subtitle && (
                    <Typography variant="caption" color="text.secondary">
                      {widget.chartConfig.subtitle}
                    </Typography>
                  )}
                </Box>
                <Box sx={{ flexGrow: 1, position: 'relative' }}>
                  <ChartWidget widget={widget} onUpdate={() => {}} />
                  {refreshing && (
                    <Box
                      sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        bgcolor: 'rgba(255, 255, 255, 0.8)' }}
                    >
                      <CircularProgress />
                    </Box>
                  )}
                </Box>
              </Paper>
            ))}
          </ResponsiveGridLayout>
        )}
      </Container>

      {/* Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
      >
        <MenuItem onClick={() => handleExport('pdf')}>
          <ExportIcon sx={{ mr: 1 }} fontSize="small" />
          Export as PDF
        </MenuItem>
        <MenuItem onClick={() => handleExport('excel')}>
          <ExportIcon sx={{ mr: 1 }} fontSize="small" />
          Export as Excel
        </MenuItem>
        <MenuItem onClick={() => handleExport('csv')}>
          <ExportIcon sx={{ mr: 1 }} fontSize="small" />
          Export as CSV
        </MenuItem>
        <MenuItem onClick={handlePrint}>
          <PrintIcon sx={{ mr: 1 }} fontSize="small" />
          Print
        </MenuItem>
        <MenuItem onClick={handleShare}>
          <ShareIcon sx={{ mr: 1 }} fontSize="small" />
          Share
        </MenuItem>
        <MenuItem onClick={handleSchedule}>
          <ScheduleIcon sx={{ mr: 1 }} fontSize="small" />
          Schedule
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default ReportViewerPage;
