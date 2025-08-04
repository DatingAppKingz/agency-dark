import React, { useState } from 'react';
import {
  Box,
  Button,
  Menu,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  TextField,
  Chip,
  Stack,
  Alert,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import {
  ArrowDropDown,
  Edit,
  Delete,
  Block,
  CheckCircle,
  Label,
  Category,
} from '@mui/icons-material';
import { ModelStatus } from '@/types/models';
import { useBulkUpdateModels, useBulkDeleteModels } from '@/hooks/useModels';

interface ModelBulkActionsProps {
  selectedIds: string[];
  onComplete?: () => void;
}

export const ModelBulkActions: React.FC<ModelBulkActionsProps> = ({
  selectedIds,
  onComplete,
}) => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogType, setDialogType] = useState<
    'status' | 'tags' | 'categories' | 'commission' | 'delete' | null
  >(null);

  // Form states
  const [status, setStatus] = useState<ModelStatus>(ModelStatus.ACTIVE);
  const [tags, setTags] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [commission, setCommission] = useState<number>(20);
  const [action, setAction] = useState<'add' | 'remove' | 'replace'>('replace');
  const [permanent, setPermanent] = useState(false);

  const bulkUpdate = useBulkUpdateModels();
  const bulkDelete = useBulkDeleteModels();

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const openDialog = (type: typeof dialogType) => {
    setDialogType(type);
    setDialogOpen(true);
    handleClose();
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setDialogType(null);
    // Reset form
    setStatus(ModelStatus.ACTIVE);
    setTags([]);
    setCategories([]);
    setCommission(20);
    setAction('replace');
    setPermanent(false);
  };

  const handleBulkUpdate = async () => {
    const updateData: any = {
      model_ids: selectedIds.map((id) => parseInt(id)),
    };

    switch (dialogType) {
      case 'status':
        updateData.status = status;
        break;
      case 'tags':
        updateData.tags = tags;
        updateData.action = action;
        break;
      case 'categories':
        updateData.categories = categories;
        updateData.action = action;
        break;
      case 'commission':
        updateData.commission_rate = commission;
        break;
    }

    await bulkUpdate.mutateAsync(updateData);
    closeDialog();
    onComplete?.();
  };

  const handleBulkDelete = async () => {
    await bulkDelete.mutateAsync({
      model_ids: selectedIds.map((id) => parseInt(id)),
      permanent,
    });
    closeDialog();
    onComplete?.();
  };

  const isDisabled = selectedIds.length === 0;

  return (
    <>
      <Button
        variant="contained"
        onClick={handleClick}
        disabled={isDisabled}
        endIcon={<ArrowDropDown />}
      >
        Bulk Actions ({selectedIds.length})
      </Button>

      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleClose}>
        <MenuItem onClick={() => openDialog('status')}>
          <CheckCircle sx={{ mr: 1 }} fontSize="small" />
          Change Status
        </MenuItem>
        <MenuItem onClick={() => openDialog('tags')}>
          <Label sx={{ mr: 1 }} fontSize="small" />
          Manage Tags
        </MenuItem>
        <MenuItem onClick={() => openDialog('categories')}>
          <Category sx={{ mr: 1 }} fontSize="small" />
          Manage Categories
        </MenuItem>
        <MenuItem onClick={() => openDialog('commission')}>
          <Edit sx={{ mr: 1 }} fontSize="small" />
          Update Commission
        </MenuItem>
        <MenuItem onClick={() => openDialog('delete')} sx={{ color: 'error.main' }}>
          <Delete sx={{ mr: 1 }} fontSize="small" />
          Delete Models
        </MenuItem>
      </Menu>

      <Dialog open={dialogOpen} onClose={closeDialog} maxWidth="sm" fullWidth>
        {dialogType === 'status' && (
          <>
            <DialogTitle>Change Status for {selectedIds.length} Models</DialogTitle>
            <DialogContent>
              <FormControl fullWidth sx={{ mt: 2 }}>
                <InputLabel>New Status</InputLabel>
                <Select
                  value={status}
                  label="New Status"
                  onChange={(e) => setStatus(e.target.value as ModelStatus)}
                >
                  <MenuItem value={ModelStatus.ACTIVE}>Active</MenuItem>
                  <MenuItem value={ModelStatus.PAUSED}>Paused</MenuItem>
                  <MenuItem value={ModelStatus.INACTIVE}>Inactive</MenuItem>
                  <MenuItem value={ModelStatus.BANNED}>Banned</MenuItem>
                </Select>
              </FormControl>
            </DialogContent>
          </>
        )}

        {dialogType === 'tags' && (
          <>
            <DialogTitle>Manage Tags for {selectedIds.length} Models</DialogTitle>
            <DialogContent>
              <FormControl fullWidth sx={{ mt: 2, mb: 2 }}>
                <InputLabel>Action</InputLabel>
                <Select
                  value={action}
                  label="Action"
                  onChange={(e) => setAction(e.target.value as typeof action)}
                >
                  <MenuItem value="add">Add Tags</MenuItem>
                  <MenuItem value="remove">Remove Tags</MenuItem>
                  <MenuItem value="replace">Replace All Tags</MenuItem>
                </Select>
              </FormControl>
              <TextField
                fullWidth
                label="Tags (comma separated)"
                value={tags.join(', ')}
                onChange={(e) =>
                  setTags(
                    e.target.value
                      .split(',')
                      .map((t) => t.trim())
                      .filter((t) => t)
                  )
                }
                helperText="Enter tags separated by commas"
              />
              <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                {tags.map((tag) => (
                  <Chip key={tag} label={tag} size="small" />
                ))}
              </Stack>
            </DialogContent>
          </>
        )}

        {dialogType === 'categories' && (
          <>
            <DialogTitle>Manage Categories for {selectedIds.length} Models</DialogTitle>
            <DialogContent>
              <FormControl fullWidth sx={{ mt: 2, mb: 2 }}>
                <InputLabel>Action</InputLabel>
                <Select
                  value={action}
                  label="Action"
                  onChange={(e) => setAction(e.target.value as typeof action)}
                >
                  <MenuItem value="add">Add Categories</MenuItem>
                  <MenuItem value="remove">Remove Categories</MenuItem>
                  <MenuItem value="replace">Replace All Categories</MenuItem>
                </Select>
              </FormControl>
              <TextField
                fullWidth
                label="Categories (comma separated)"
                value={categories.join(', ')}
                onChange={(e) =>
                  setCategories(
                    e.target.value
                      .split(',')
                      .map((c) => c.trim())
                      .filter((c) => c)
                  )
                }
                helperText="Enter categories separated by commas"
              />
              <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
                {categories.map((category) => (
                  <Chip key={category} label={category} size="small" />
                ))}
              </Stack>
            </DialogContent>
          </>
        )}

        {dialogType === 'commission' && (
          <>
            <DialogTitle>Update Commission for {selectedIds.length} Models</DialogTitle>
            <DialogContent>
              <TextField
                fullWidth
                type="number"
                label="Commission Rate (%)"
                value={commission}
                onChange={(e) => setCommission(parseFloat(e.target.value))}
                inputProps={{ min: 0, max: 100, step: 0.1 }}
                sx={{ mt: 2 }}
                helperText="Enter the commission rate as a percentage"
              />
            </DialogContent>
          </>
        )}

        {dialogType === 'delete' && (
          <>
            <DialogTitle>Delete {selectedIds.length} Models</DialogTitle>
            <DialogContent>
              <Alert severity="warning" sx={{ mb: 2 }}>
                This action cannot be undone. Models will be marked as deleted and their
                user accounts will be deactivated.
              </Alert>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={permanent}
                    onChange={(e) => setPermanent(e.target.checked)}
                  />
                }
                label="Permanently delete (cannot be recovered)"
                sx={{ mt: 1 }}
              />
            </DialogContent>
          </>
        )}

        <DialogActions>
          <Button onClick={closeDialog}>Cancel</Button>
          <Button
            variant="contained"
            color={dialogType === 'delete' ? 'error' : 'primary'}
            onClick={dialogType === 'delete' ? handleBulkDelete : handleBulkUpdate}
            disabled={
              bulkUpdate.isPending ||
              bulkDelete.isPending ||
              (dialogType === 'tags' && tags.length === 0) ||
              (dialogType === 'categories' && categories.length === 0)
            }
          >
            {dialogType === 'delete' ? 'Delete' : 'Apply Changes'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};