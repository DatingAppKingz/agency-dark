import React, { useState, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  TextField,
  FormControl,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  ListItemButton,
  Collapse,
  FormControlLabel,
  Switch } from '@mui/material';
import {
  Add as AddIcon,
  Save as SaveIcon,
  SaveAs as ExportIcon,
  Schedule as RefreshIcon,
  Settings as SettingsIcon,
  Close as DragIcon,
  ShowChart as LineChartIcon,
  BarChart as BarChartIcon,
  PieChart as PieChartIcon,
  TableChart as TableIcon,
  Dashboard as MetricIcon,
  FilterList as FilterIcon,
  DateRange as ExpandLess,
  ExpandMore,
  Delete as DeleteIcon,
  Edit as FullscreenIcon,
  FullscreenExit as ExitFullscreenIcon } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import GridLayout, { WidthProvider } from 'react-grid-layout';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { reportsService } from '@/services/api/reports';
import {
  ReportWidget,
  ChartType,
  ReportFilter,
  DateRangeType,
  ReportType } from '@/types/reports';
import ChartWidget from './ChartWidget';
import MetricSelector from './MetricSelector';
import DimensionSelector from './DimensionSelector';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const ResponsiveGridLayout = WidthProvider(GridLayout);

interface ReportBuilderProps {
  templateId?: string;
  onSave?: (templateId: string) => void;
}

const ReportBuilder: React.FC<ReportBuilderProps> = ({ templateId, onSave }) => {
  const [widgets, setWidgets] = useState<ReportWidget[]>([]);
  const [selectedWidget, setSelectedWidget] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [templateName, setTemplateName] = useState('');
  const [templateDescription, setTemplateDescription] = useState('');
  const [dateRange, setDateRange] = useState({
    type: DateRangeType.LAST_30_DAYS,
    startDate: undefined as string | undefined,
    endDate: undefined as string | undefined });
  const [globalFilters, ] = useState<ReportFilter[]>([]);
  const [refreshInterval, setRefreshInterval] = useState<number | undefined>(undefined);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [fullscreenWidget, setFullscreenWidget] = useState<string | null>(null);
  const [metricsOpen, setMetricsOpen] = useState(true);
  const [dimensionsOpen, setDimensionsOpen] = useState(true);
  const [chartsOpen, setChartsOpen] = useState(true);

  const queryClient = useQueryClient();
  const containerRef = useRef<HTMLDivElement>(null);

  // Load template if provided
  const { data: template, isPending: isTemplateLoading } = useQuery({
    queryKey: ['report-template', templateId],
    queryFn: () => reportsService.getTemplate(templateId!),
    enabled: !!templateId });

  // Get builder config
  const { data: builderConfig } = useQuery({
    queryKey: ['report-builder-config'],
    queryFn: () => reportsService.getBuilderConfig() });

  // Generate report data
  const generateReport = useMutation({
    mutationFn: (event: string[]) => {
      const widgetsToGenerate = widgets.filter(w => event.includes(w.id));
      return reportsService.generateReport({
        widgets: widgetsToGenerate.map(w => w.chartConfig),
        dateRange,
        filters: globalFilters });
    },
    onSuccess: (data, ) => {
      // Update widget data
      const updatedWidgets = widgets.map(widget => {
        const widgetData = data.widgets.find(w => w.widgetId === widget.id);
        if (widgetData) {
          return { ...widget, data: widgetData.data, loading: false };
        }
        return widget;
      });
      setWidgets(updatedWidgets);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to generate report');
    } });

  // Save template
  const saveTemplate = useMutation({
    mutationFn: (data: any) => {
      if (templateId) {
        return reportsService.updateTemplate(templateId, data);
      }
      return reportsService.createTemplate(data);
    },
    onSuccess: (template) => {
      toast.success('Report template saved successfully');
      setSaveDialogOpen(false);
      if (onSave) {
        onSave(template.id);
      }
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to save template');
    } });

  const addWidget = (chartType: ChartType) => {
    const newWidget: ReportWidget = {
      id: `widget-${Date.now()}`,
      x: 0,
      y: 0,
      w: 6,
      h: 4,
      chartConfig: {
        type: chartType,
        title: 'New Chart',
        metrics: [],
        dimensions: [],
        filters: [],
        options: {
          showLegend: true,
          showGrid: true,
          showTooltip: true } } };

    setWidgets([...widgets, newWidget]);
    setSelectedWidget(newWidget.id);
  };

  const updateWidget = (widgetId: string, updates: Partial<ReportWidget>) => {
    setWidgets(widgets.map(w => w.id === widgetId ? { ...w, ...updates } : w));
  };

  const deleteWidget = (widgetId: string) => {
    setWidgets(widgets.filter(w => w.id !== widgetId));
    if (selectedWidget === widgetId) {
      setSelectedWidget(null);
    }
  };

  const handleLayoutChange = (layout: any[]) => {
    const updatedWidgets = widgets.map(widget => {
      const layoutItem = layout.find(l => l.i === widget.id);
      if (layoutItem) {
        return {
          ...widget,
          x: layoutItem.x,
          y: layoutItem.y,
          w: layoutItem.w,
          h: layoutItem.h };
      }
      return widget;
    });
    setWidgets(updatedWidgets);
  };

  const handleSaveTemplate = () => {
    const templateData = {
      name: templateName,
      description: templateDescription,
      type: ReportType.CUSTOM,
      widgets: widgets.map(({ data, loading, error, ...widget }) => widget),
      globalFilters,
      dateRange,
      refreshInterval,
      isPublic: false };

    saveTemplate.mutate(templateData);
  };

  const refreshAllWidgets = () => {
    const widgetIds = widgets.map(w => w.id);
    generateReport.mutate(widgetIds);
  };

  const chartTypes = [
    { type: ChartType.LINE, icon: <LineChartIcon />, label: 'Line Chart' },
    { type: ChartType.BAR, icon: <BarChartIcon />, label: 'Bar Chart' },
    { type: ChartType.PIE, icon: <PieChartIcon />, label: 'Pie Chart' },
    { type: ChartType.TABLE, icon: <TableIcon />, label: 'Table' },
    { type: ChartType.METRIC_CARD, icon: <MetricIcon />, label: 'Metric ' },
  ];

  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Left Sidebar */}
      <Drawer
        variant="persistent"
        anchor="left"
        open={drawerOpen}
        sx={{
          width: drawerOpen ? 300 : 0,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 300,
            boxSizing: 'border-box',
            position: 'relative',
            height: '100%' } }}
      >
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="h6">Report Builder</Typography>
        </Box>

        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" gutterBottom>
            Date Range
          </Typography>
          <FormControl fullWidth size="small" sx={{ mb: 2 }}>
            <Select
              value={dateRange.type}
              onChange={(e) => setDateRange({ ...dateRange, type: e.target.value as DateRangeType })}
            >
              <MenuItem value={DateRangeType.TODAY}>Today</MenuItem>
              <MenuItem value={DateRangeType.YESTERDAY}>Yesterday</MenuItem>
              <MenuItem value={DateRangeType.LAST_7_DAYS}>Last 7 Days</MenuItem>
              <MenuItem value={DateRangeType.LAST_30_DAYS}>Last 30 Days</MenuItem>
              <MenuItem value={DateRangeType.LAST_90_DAYS}>Last 90 Days</MenuItem>
              <MenuItem value={DateRangeType.THIS_MONTH}>This Month</MenuItem>
              <MenuItem value={DateRangeType.LAST_MONTH}>Last Month</MenuItem>
              <MenuItem value={DateRangeType.CUSTOM}>Custom</MenuItem>
            </Select>
          </FormControl>

          {dateRange.type === DateRangeType.CUSTOM && (
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <DatePicker
                label="Start Date"
                value={dateRange.startDate ? new Date(dateRange.startDate) : null}
                onChange={(date) => setDateRange({ ...dateRange, startDate: date?.toISOString() })}
                slotProps={{ textField: { size: 'small', fullWidth: true, sx: { mb: 1 } } }}
              />
              <DatePicker
                label="End Date"
                value={dateRange.endDate ? new Date(dateRange.endDate) : null}
                onChange={(date) => setDateRange({ ...dateRange, endDate: date?.toISOString() })}
                slotProps={{ textField: { size: 'small', fullWidth: true } }}
              />
            </LocalizationProvider>
          )}
        </Box>

        <Box sx={{ overflow: 'auto', flexGrow: 1 }}>
          {/* Charts Section */}
          <ListItemButton onClick={() => setChartsOpen(!chartsOpen)}>
            <ListItemIcon>
              <BarChartIcon />
            </ListItemIcon>
            <ListItemText primary="Charts" />
            {chartsOpen ? <ExpandLess /> : <ExpandMore />}
          </ListItemButton>
          <Collapse in={chartsOpen} timeout="auto" unmountOnExit>
            <List component="div" disablePadding>
              {chartTypes.map((chart) => (
                <ListItem
                  key={chart.type}
                  button
                  sx={{ pl: 4 }}
                  onClick={() => addWidget(chart.type)}
                >
                  <ListItemIcon>{chart.icon}</ListItemIcon>
                  <ListItemText primary={chart.label} />
                </ListItem>
              ))}
            </List>
          </Collapse>

          {/* Metrics Section */}
          {builderConfig && (
            <>
              <ListItemButton onClick={() => setMetricsOpen(!metricsOpen)}>
                <ListItemIcon>
                  <MetricIcon />
                </ListItemIcon>
                <ListItemText primary="Metrics" />
                {metricsOpen ? <ExpandLess /> : <ExpandMore />}
              </ListItemButton>
              <Collapse in={metricsOpen} timeout="auto" unmountOnExit>
                <Box sx={{ p: 2 }}>
                  <MetricSelector
                    availableMetrics={builderConfig.metrics}
                    selectedMetrics={selectedWidget ? widgets.find(w => w.id === selectedWidget)?.chartConfig.metrics || [] : []}
                    onChange={(metrics) => {
                      if (selectedWidget) {
                        updateWidget(selectedWidget, {
                          chartConfig: {
                            ...widgets.find(w => w.id === selectedWidget)!.chartConfig,
                            metrics } });
                      }
                    }}
                  />
                </Box>
              </Collapse>

              {/* Dimensions Section */}
              <ListItemButton onClick={() => setDimensionsOpen(!dimensionsOpen)}>
                <ListItemIcon>
                  <FilterIcon />
                </ListItemIcon>
                <ListItemText primary="Dimensions" />
                {dimensionsOpen ? <ExpandLess /> : <ExpandMore />}
              </ListItemButton>
              <Collapse in={dimensionsOpen} timeout="auto" unmountOnExit>
                <Box sx={{ p: 2 }}>
                  <DimensionSelector
                    availableDimensions={builderConfig.dimensions}
                    selectedDimensions={selectedWidget ? widgets.find(w => w.id === selectedWidget)?.chartConfig.dimensions || [] : []}
                    onChange={(dimensions) => {
                      if (selectedWidget) {
                        updateWidget(selectedWidget, {
                          chartConfig: {
                            ...widgets.find(w => w.id === selectedWidget)!.chartConfig,
                            dimensions } });
                      }
                    }}
                  />
                </Box>
              </Collapse>
            </>
          )}
        </Box>

        <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
          <FormControlLabel
            control={
              <Switch
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
            }
            label="Auto Refresh"
          />
          {autoRefresh && (
            <TextField
              type="number"
              label="Interval (seconds)"
              size="small"
              fullWidth
              value={refreshInterval || ''}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              sx={{ mt: 1 }}
            />
          )}
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box sx={{ flexGrow: 1, overflow: 'auto', bgcolor: 'background.default' }}>
        {/* Toolbar */}
        <Box
          sx={{
            p: 2,
            borderBottom: 1,
            borderColor: 'divider',
            bgcolor: 'background.paper',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between' }}
        >
          <Box display="flex" alignItems="center" gap={1}>
            <IconButton onClick={() => setDrawerOpen(!drawerOpen)}>
              <SettingsIcon />
            </IconButton>
            <Typography variant="h6">
              {template?.name || 'New Report'}
            </Typography>
          </Box>

          <Box display="flex" gap={1}>
            <Button
              startIcon={<RefreshIcon />}
              onClick={refreshAllWidgets}
              disabled={widgets.length === 0}
            >
              Refresh
            </Button>
            <Button
              startIcon={<SaveIcon />}
              onClick={() => setSaveDialogOpen(true)}
              disabled={widgets.length === 0}
            >
              Save
            </Button>
            <Button
              startIcon={<ExportIcon />}
              variant="contained"
              disabled={widgets.length === 0}
            >
              Export
            </Button>
          </Box>
        </Box>

        {/* Report Canvas */}
        <Box ref={containerRef} sx={{ p: 2, height: 'calc(100% - 73px)' }}>
          {widgets.length === 0 ? (
            <Box
              sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center' }}
            >
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" gutterBottom>
                  Start Building Your Report
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                  Add charts and metrics from the sidebar to begin
                </Typography>
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={() => addWidget(ChartType.LINE)}
                >
                  Add First Chart
                </Button>
              </Paper>
            </Box>
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
              onLayoutChange={handleLayoutChange}
              draggableHandle=".drag-handle"
            >
              {widgets.map((widget) => (
                <Paper
                  key={widget.id}
                  sx={{
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                    border: selectedWidget === widget.id ? 2 : 1,
                    borderColor: selectedWidget === widget.id ? 'primary.main' : 'divider',
                    cursor: 'pointer' }}
                  onClick={() => setSelectedWidget(widget.id)}
                >
                  <Box
                    sx={{
                      p: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderBottom: 1,
                      borderColor: 'divider',
                      bgcolor: 'background.default' }}
                  >
                    <Box display="flex" alignItems="center" gap={1}>
                      <IconButton size="small" className="drag-handle" sx={{ cursor: 'move' }}>
                        <DragIcon />
                      </IconButton>
                      <Typography variant="subtitle2" noWrap>
                        {widget.chartConfig.title}
                      </Typography>
                    </Box>
                    <Box>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          setFullscreenWidget(widget.id);
                        }}
                      >
                        <FullscreenIcon fontSize="small" />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteWidget(widget.id);
                        }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Box>
                  </Box>
                  <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
                    <ChartWidget
                      widget={widget}
                      onUpdate={(updates) => updateWidget(widget.id, updates)}
                    />
                  </Box>
                </Paper>
              ))}
            </ResponsiveGridLayout>
          )}
        </Box>
      </Box>

      {/* Save Dialog */}
      <Dialog open={saveDialogOpen} onClose={() => setSaveDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Save Report Template</DialogTitle>
        <DialogContent>
          <TextField
            label="Template Name"
            fullWidth
            value={templateName}
            onChange={(e) => setTemplateName(e.target.value)}
            sx={{ mb: 2, mt: 1 }}
          />
          <TextField
            label="Description"
            fullWidth
            multiline
            rows={3}
            value={templateDescription}
            onChange={(e) => setTemplateDescription(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSaveDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleSaveTemplate}
            disabled={!templateName || saveTemplate.isPending}
          >
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Fullscreen Widget Dialog */}
      <Dialog
        open={!!fullscreenWidget}
        onClose={() => setFullscreenWidget(null)}
        maxWidth={false}
        fullWidth
        PaperProps={{ sx: { height: '90vh', m: 2 } }}
      >
        {fullscreenWidget && (
          <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box
              sx={{
                p: 2,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                borderBottom: 1,
                borderColor: 'divider' }}
            >
              <Typography variant="h6">
                {widgets.find(w => w.id === fullscreenWidget)?.chartConfig.title}
              </Typography>
              <IconButton onClick={() => setFullscreenWidget(null)}>
                <ExitFullscreenIcon />
              </IconButton>
            </Box>
            <Box sx={{ flexGrow: 1, p: 2 }}>
              <ChartWidget
                widget={widgets.find(w => w.id === fullscreenWidget)!}
                onUpdate={(updates) => updateWidget(fullscreenWidget, updates)}
                fullscreen
              />
            </Box>
          </Box>
        )}
      </Dialog>
    </Box>
  );
};

export default ReportBuilder;
