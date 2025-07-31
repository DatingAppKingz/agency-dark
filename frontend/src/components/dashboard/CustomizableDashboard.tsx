import React, { useState, useCallback, useMemo } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout';
import {
  Box,
  Paper,
  IconButton,
  Typography,
  Tooltip,
  Fab,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Switch,
  FormControlLabel } from '@mui/material';
import {
  Close,
  Settings,
  Add,
  Lock,
  LockOpen,
  Visibility,
  VisibilityOff,
  DragIndicator } from '@mui/icons-material';
import { useDashboardCustomization } from '@/hooks/useDashboardCustomization';
import { WidgetConfig, WidgetType } from '@/types/dashboard';
import { StatsCard } from './StatsCard';
import { ChartWidget } from './ChartWidget';
import { ActivityFeed } from './ActivityFeed';
import { MetricsGrid } from './MetricsGrid';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const ResponsiveGridLayout = WidthProvider(Responsive);

// Widget registry
const widgetComponents: Record<WidgetType, React.ComponentType<any>> = {
  'stats-card': StatsCard,
  'chart': ChartWidget,
  'activity-feed': ActivityFeed,
  'metrics-grid': MetricsGrid,
  'quick-actions': () => <div>Quick Actions Widget</div>,
  'recent-items': () => <div>Recent Items Widget</div>,
  'calendar': () => <div>Calendar Widget</div>,
  'tasks': () => <div>Tasks Widget</div>,
  'custom': () => <div>Custom Widget</div> };

interface CustomizableDashboardProps {
  editMode?: boolean;
  onEditModeChange?: (editMode: boolean) => void;
}

export const CustomizableDashboard: React.FC<CustomizableDashboardProps> = ({
  editMode = false,
  onEditModeChange }) => {
  const {
    currentLayout,
    updateWidgetPosition,
    toggleWidgetVisibility,
    removeWidget,
    addWidget } = useDashboardCustomization();

  const [settingsAnchor, setSettingsAnchor] = useState<null | HTMLElement>(null);
  const [selectedWidget, setSelectedWidget] = useState<WidgetConfig | null>(null);
  const [addWidgetDialog, setAddWidgetDialog] = useState(false);
  const [newWidgetType, setNewWidgetType] = useState<WidgetType>('stats-card');
  const [newWidgetTitle, setNewWidgetTitle] = useState('');

  // Convert widget configs to react-grid-layout format
  const layouts = useMemo(() => {
    if (!currentLayout) return { lg: [] };

    return {
      lg: currentLayout.widgets
        .filter(widget => widget.visible || editMode)
        .map(widget => ({
          i: widget.id,
          x: widget.position.x,
          y: widget.position.y,
          w: widget.position.w,
          h: widget.position.h,
          static: !editMode })) };
  }, [currentLayout, editMode]);

  const handleLayoutChange = useCallback(
    (layout: any[]) => {
      if (!editMode) return;

      layout.forEach(item => {
        updateWidgetPosition(item.i, {
          x: item.x,
          y: item.y,
          w: item.w,
          h: item.h });
      });
    },
    [editMode, updateWidgetPosition]
  );

  const handleWidgetSettings = (widget: WidgetConfig, event: React.MouseEvent<HTMLElement>) => {
    setSelectedWidget(widget);
    setSettingsAnchor(event.currentTarget);
  };

  const handleCloseSettings = () => {
    setSettingsAnchor(null);
    setSelectedWidget(null);
  };

  const handleAddWidget = () => {
    if (!newWidgetTitle.trim()) return;

    const newWidget: WidgetConfig = {
      id: `widget-${Date.now()}`,
      type: newWidgetType,
      title: newWidgetTitle,
      position: { x: 0, y: 0, w: 4, h: 3 },
      visible: true };

    addWidget(newWidget);
    setAddWidgetDialog(false);
    setNewWidgetTitle('');
  };

  if (!currentLayout) {
    return <Box>Loading dashboard...</Box>;
  }

  return (
    <Box sx={{ position: 'relative', minHeight: '100vh', p: 2 }}>
      {/* Edit mode toggle */}
      {onEditModeChange && (
        <Box sx={{ position: 'absolute', top: 16, right: 16, zIndex: 1000 }}>
          <FormControlLabel
            control={
              <Switch
                checked={editMode}
                onChange={(e) => onEditModeChange(e.target.checked)}
                color="primary"
              />
            }
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {editMode ? <LockOpen /> : <Lock />}
                {editMode ? 'Edit Mode' : 'View Mode'}
              </Box>
            }
          />
        </Box>
      )}

      {/* Dashboard grid */}
      <ResponsiveGridLayout
        className="layout"
        layouts={layouts}
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
        rowHeight={currentLayout.rowHeight}
        onLayoutChange={handleLayoutChange}
        isDraggable={editMode}
        isResizable={editMode}
        compactType="vertical"
        preventCollision={false}
      >
        {currentLayout.widgets
          .filter(widget => widget.visible || editMode)
          .map(widget => {
            const WidgetComponent = widgetComponents[widget.type];
            
            return (
              <Paper
                key={widget.id}
                elevation={2}
                sx={{
                  height: '100%',
                  overflow: 'hidden',
                  opacity: widget.visible ? 1 : 0.5,
                  position: 'relative',
                  '&:hover .widget-controls': {
                    opacity: 1 } }}
              >
                {/* Widget controls */}
                {editMode && (
                  <Box
                    className="widget-controls"
                    sx={{
                      position: 'absolute',
                      top: 0,
                      right: 0,
                      display: 'flex',
                      gap: 0.5,
                      p: 1,
                      opacity: 0,
                      transition: 'opacity 0.2s',
                      zIndex: 10,
                      backgroundColor: 'rgba(255, 255, 255, 0.9)',
                      borderRadius: '0 0 0 8px' }}
                  >
                    <Tooltip title="Drag to reposition">
                      <IconButton size="small" sx={{ cursor: 'move' }}>
                        <DragIndicator fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title={widget.visible ? 'Hide' : 'Show'}>
                      <IconButton
                        size="small"
                        onClick={() => toggleWidgetVisibility(widget.id)}
                      >
                        {widget.visible ? (
                          <Visibility fontSize="small" />
                        ) : (
                          <VisibilityOff fontSize="small" />
                        )}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Settings">
                      <IconButton
                        size="small"
                        onClick={(e) => handleWidgetSettings(widget, e)}
                      >
                        <Settings fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Remove">
                      <IconButton
                        size="small"
                        onClick={() => removeWidget(widget.id)}
                        color="error"
                      >
                        <Close fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                )}

                {/* Widget header */}
                <Box sx={{ p: 2, pb: 1 }}>
                  <Typography variant="h6" component="h3">
                    {widget.title}
                  </Typography>
                  {widget.description && (
                    <Typography variant="caption" color="text.secondary">
                      {widget.description}
                    </Typography>
                  )}
                </Box>

                {/* Widget content */}
                <Box sx={{ p: 2, pt: 0, height: 'calc(100% - 64px)' }}>
                  <WidgetComponent {...(widget.settings || {})} />
                </Box>
              </Paper>
            );
          })}
      </ResponsiveGridLayout>

      {/* Add widget button */}
      {editMode && (
        <Fab
          color="primary"
          sx={{ position: 'fixed', bottom: 24, right: 24 }}
          onClick={() => setAddWidgetDialog(true)}
        >
          <Add />
        </Fab>
      )}

      {/* Widget settings menu */}
      <Menu
        anchorEl={settingsAnchor}
        open={Boolean(settingsAnchor)}
        onClose={handleCloseSettings}
      >
        <MenuItem onClick={handleCloseSettings}>
          Configure Widget
        </MenuItem>
        <MenuItem onClick={handleCloseSettings}>
          Export Data
        </MenuItem>
      </Menu>

      {/* Add widget dialog */}
      <Dialog
        open={addWidgetDialog}
        onClose={() => setAddWidgetDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Widget</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Widget Title"
              value={newWidgetTitle}
              onChange={(e) => setNewWidgetTitle(e.target.value)}
              fullWidth
            />
            <TextField
              select
              label="Widget Type"
              value={newWidgetType}
              onChange={(e) => setNewWidgetType(e.target.value as WidgetType)}
              fullWidth
            >
              <MenuItem value="stats-card">Stats Card</MenuItem>
              <MenuItem value="chart">Chart</MenuItem>
              <MenuItem value="activity-feed">Activity Feed</MenuItem>
              <MenuItem value="metrics-grid">Metrics Grid</MenuItem>
              <MenuItem value="quick-actions">Quick Actions</MenuItem>
              <MenuItem value="recent-items">Recent Items</MenuItem>
              <MenuItem value="calendar">Calendar</MenuItem>
              <MenuItem value="tasks">Tasks</MenuItem>
              <MenuItem value="custom">Custom</MenuItem>
            </TextField>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAddWidgetDialog(false)}>Cancel</Button>
          <Button onClick={handleAddWidget} variant="contained">
            Add Widget
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
