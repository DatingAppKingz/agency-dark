import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Chip,
  Tooltip,
  Alert } from '@mui/material';
import {
  Delete,
  Check,
  Add,
  RestartAlt,
  ContentCopy } from '@mui/icons-material';
import { useDashboardCustomization } from '@/hooks/useDashboardCustomization';

export const DashboardSettings: React.FC = () => {
  const {
    preferences,
    currentLayout,
    createLayout,
    deleteLayout,
    switchLayout,
    resetToDefault } = useDashboardCustomization();

  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newLayoutName, setNewLayoutName] = useState('');
  const [newLayoutDescription, setNewLayoutDescription] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const handleCreateLayout = () => {
    if (newLayoutName.trim()) {
      createLayout(newLayoutName, newLayoutDescription);
      setCreateDialogOpen(false);
      setNewLayoutName('');
      setNewLayoutDescription('');
    }
  };

  const handleDeleteLayout = (layoutId: string) => {
    deleteLayout(layoutId);
    setDeleteConfirmId(null);
  };

  const handleDuplicateLayout = (layoutId: string) => {
    const layout = preferences?.customLayouts.find(l => l.id === layoutId);
    if (layout) {
      createLayout(`${layout.name} (Copy)`, layout.description);
    }
  };

  if (!preferences) {
    return <Box>Loading settings...</Box>;
  }

  return (
    <Box>
      <Paper sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5">Dashboard Layouts</Typography>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              startIcon={<Add />}
              variant="contained"
              onClick={() => setCreateDialogOpen(true)}
            >
              Create Layout
            </Button>
            <Button
              startIcon={<RestartAlt />}
              variant="outlined"
              onClick={resetToDefault}
            >
              Reset to Default
            </Button>
          </Box>
        </Box>

        <List>
          {preferences.customLayouts.map((layout) => (
            <ListItem
              key={layout.id}
              sx={{
                border: 1,
                borderColor: layout.id === currentLayout?.id ? 'primary.main' : 'divider',
                borderRadius: 1,
                mb: 1,
                backgroundColor: layout.id === currentLayout?.id ? 'action.selected' : 'transparent' }}
            >
              <ListItemText
                primary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="subtitle1">{layout.name}</Typography>
                    {layout.isDefault && (
                      <Chip label="Default" size="small" color="primary" />
                    )}
                    {layout.id === currentLayout?.id && (
                      <Chip label="Active" size="small" color="success" />
                    )}
                  </Box>
                }
                secondary={
                  <Box>
                    {layout.description && (
                      <Typography variant="body2" color="text.secondary">
                        {layout.description}
                      </Typography>
                    )}
                    <Typography variant="caption" color="text.secondary">
                      {layout.widgets.length} widgets • 
                      Last updated: {new Date(layout.updatedAt).toLocaleDateString()}
                    </Typography>
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                {layout.id !== currentLayout?.id && (
                  <Tooltip title="Use this layout">
                    <IconButton
                      edge="end"
                      onClick={() => switchLayout(layout.id)}
                      color="primary"
                    >
                      <Check />
                    </IconButton>
                  </Tooltip>
                )}
                <Tooltip title="Duplicate layout">
                  <IconButton
                    edge="end"
                    onClick={() => handleDuplicateLayout(layout.id)}
                  >
                    <ContentCopy />
                  </IconButton>
                </Tooltip>
                {!layout.isDefault && (
                  <Tooltip title="Delete layout">
                    <IconButton
                      edge="end"
                      onClick={() => setDeleteConfirmId(layout.id)}
                      color="error"
                    >
                      <Delete />
                    </IconButton>
                  </Tooltip>
                )}
              </ListItemSecondaryAction>
            </ListItem>
          ))}
        </List>
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>
          Layout Information
        </Typography>
        {currentLayout && (
          <Box>
            <Typography variant="body2" paragraph>
              Current layout: <strong>{currentLayout.name}</strong>
            </Typography>
            <Typography variant="body2" paragraph>
              Grid columns: {currentLayout.gridCols}
            </Typography>
            <Typography variant="body2" paragraph>
              Row height: {currentLayout.rowHeight}px
            </Typography>
            <Alert severity="info" sx={{ mt: 2 }}>
              To customize your dashboard, enable Mode from the dashboard view.
              You can drag and drop widgets, resize them, and add new ones.
            </Alert>
          </Box>
        )}
      </Paper>

      {/* Create layout dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create New Layout</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
            <TextField
              label="Layout Name"
              value={newLayoutName}
              onChange={(e) => setNewLayoutName(e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Description (optional)"
              value={newLayoutDescription}
              onChange={(e) => setNewLayoutDescription(e.target.value)}
              fullWidth
              multiline
              rows={2}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleCreateLayout} variant="contained">
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete confirmation dialog */}
      <Dialog
        open={Boolean(deleteConfirmId)}
        onClose={() => setDeleteConfirmId(null)}
      >
        <DialogTitle>Delete Layout?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this layout? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmId(null)}>Cancel</Button>
          <Button
            onClick={() => deleteConfirmId && handleDeleteLayout(deleteConfirmId)}
            color="error"
            variant="contained"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
