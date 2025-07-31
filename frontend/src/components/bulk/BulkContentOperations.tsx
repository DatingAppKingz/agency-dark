import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Checkbox,
  Avatar,
  FormGroup,
  FormControlLabel,
  Switch,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress,
  Tooltip } from '@mui/material';
import {
  Upload as UploadIcon,
  Download as DeleteIcon,
  Edit as EditIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  Lock as LockIcon,
  LockOpen as UnlockIcon,
  Image as ImageIcon,
  VideoLibrary as VideoIcon,
  Description as FileIcon } from '@mui/icons-material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { bulkOperationsService } from '@/services/api/bulkOperations';
import { BulkOperationType, BulkOperationCreate } from '@/types/bulkOperations';
import MediaUploader from '@/components/media/MediaUploader';
import { useModels } from '@/hooks/useModels';
import { ModelProfile } from '@/types/models';

const BulkContentOperations: React.FC = () => {
  const [selectedContent, setSelectedContent] = useState<string[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [bulkEditData, setBulkEditData] = useState({
    price: '',
    is_locked: false,
    is_visible: true,
    scheduled_at: null as Date | null,
    tags: [] as string[] });
  const [uploadData, setUploadData] = useState({
    files: [] as File[],
    modelId: '',
    price: '',
    is_locked: true,
    is_visible: true,
    scheduled_at: null as Date | null,
    auto_generate_thumbnails: true,
    watermark: true });

  const queryClient = useQueryClient();
  const { data: models } = useModels();

  // Mock content data - replace with actual API call
  const { data: content, isPending } = useQuery({
    queryKey: ['content'],
    queryFn: async () => {
      // This would be replaced with actual API call
      return {
        items: [
          {
            id: '1',
            type: 'image' as const,
            title: 'Beach Photoshoot',
            description: 'Summer collection',
            url: '/content/image1.jpg',
            thumbnail: '/content/thumb1.jpg',
            price: 9.99,
            is_locked: true,
            is_visible: true,
            created_at: new Date().toISOString(),
            views: 1234,
            purchases: 56 },
          {
            id: '2',
            type: 'video' as const,
            title: 'Behind the Scenes',
            description: 'Exclusive BTS content',
            url: '/content/video1.mp4',
            thumbnail: '/content/thumb2.jpg',
            price: 19.99,
            is_locked: true,
            is_visible: true,
            created_at: new Date().toISOString(),
            views: 890,
            purchases: 23 },
        ],
        total: 2 };
    } });

  // Create bulk operation
  const createBulkOperation = useMutation({
    mutationFn: (data: BulkOperationCreate) => bulkOperationsService.createBulkOperation(data),
    onSuccess: () => {
      toast.success('Bulk operation started');
      queryClient.invalidateQueries({ queryKey: ['bulk-operations'] });
      queryClient.invalidateQueries({ queryKey: ['content'] });
      resetSelection();
      setShowEditDialog(false);
      setShowUploadDialog(false);
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      toast.error(error.response?.data?.detail || 'Failed to start bulk operation');
    } });

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const allContentIds = content?.items.map(item => item.id) || [];
      setSelectedContent(allContentIds);
      setSelectAll(true);
    } else {
      setSelectedContent([]);
      setSelectAll(false);
    }
  };

  const handleSelectContent = (contentId: string) => {
    setSelectedContent(prev => {
      if (prev.includes(contentId)) {
        return prev.filter(id => id !== contentId);
      } else {
        return [...prev, contentId];
      }
    });
  };

  const resetSelection = () => {
    setSelectedContent([]);
    setSelectAll(false);
  };

  const handleBulkEdit = () => {
    if (selectedContent.length === 0) {
      toast.error('Please select content to edit');
      return;
    }
    setShowEditDialog(true);
  };

  const handleBulkDelete = () => {
    if (selectedContent.length === 0) {
      toast.error('Please select content to delete');
      return;
    }

    if (window.confirm(`Are you sure you want to delete ${selectedContent.length} items?`)) {
      const operationData = {
        operation_type: BulkOperationType.DATA_EXPORT, // Would be CONTENT_DELETE
        entity_type: 'content',
        entity_ids: selectedContent,
        operation_params: {
          permanent: false },
        notes: `Bulk delete ${selectedContent.length} content items` };

      createBulkOperation.mutate(operationData);
    }
  };

  const executeBulkEdit = () => {
    const operationData = {
      operation_type: BulkOperationType.DATA_EXPORT, // Would be CONTENT_UPDATE
      entity_type: 'content',
      entity_ids: selectedContent,
      operation_params: {
        ...bulkEditData,
        price: bulkEditData.price ? parseFloat(bulkEditData.price) : undefined },
      notes: `Bulk update ${selectedContent.length} content items` };

    createBulkOperation.mutate(operationData);
  };

  const handleBulkUpload = () => {
    if (uploadData.files.length === 0) {
      toast.error('Please select files to upload');
      return;
    }

    const operationData = {
      operation_type: BulkOperationType.DATA_IMPORT, // Would be CONTENT_UPLOAD
      entity_type: 'content',
      entity_ids: [], // Files would be uploaded separately
      operation_params: {
        model_id: uploadData.modelId,
        price: uploadData.price ? parseFloat(uploadData.price) : 0,
        is_locked: uploadData.is_locked,
        is_visible: uploadData.is_visible,
        scheduled_at: uploadData.scheduled_at,
        auto_generate_thumbnails: uploadData.auto_generate_thumbnails,
        watermark: uploadData.watermark,
        file_count: uploadData.files.length },
      notes: `Bulk upload ${uploadData.files.length} files` };

    createBulkOperation.mutate(operationData);
  };

  const getContentIcon = (type: string) => {
    switch (type) {
      case 'image':
        return <ImageIcon />;
      case 'video':
        return <VideoIcon />;
      default:
        return <FileIcon />;
    }
  };

  return (
    <Box>
      {/* Upload Section */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">Bulk Content Upload</Typography>
            <Button
              variant="contained"
              startIcon={<UploadIcon />}
              onClick={() => setShowUploadDialog(true)}
            >
              Upload Content
            </Button>
          </Box>
          <Alert severity="info">
            Upload multiple images, videos, or documents at once. Files will be processed in the background.
          </Alert>
        </CardContent>
      </Card>

      {/* Content Management */}
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h6">Content Management</Typography>
            {selectedContent.length > 0 && (
              <Box display="flex" gap={1}>
                <Chip
                  label={`${selectedContent.length} selected`}
                  onDelete={resetSelection}
                  color="primary"
                />
                <Button
                  size="small"
                  startIcon={<EditIcon />}
                  onClick={handleBulkEdit}
                >
                  Edit
                </Button>
                <Button
                  size="small"
                  startIcon={<VisibilityIcon />}
                  onClick={() => {
                    // Handle visibility toggle
                  }}
                >
                  Toggle Visibility
                </Button>
                <Button
                  size="small"
                  startIcon={<DeleteIcon />}
                  color="error"
                  onClick={handleBulkDelete}
                >
                  Delete
                </Button>
              </Box>
            )}
          </Box>

          <TableContainer component={Paper} variant="outlined">
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell padding="checkbox">
                    <Checkbox
                      checked={selectAll}
                      indeterminate={selectedContent.length > 0 && selectedContent.length < (content?.items.length || 0)}
                      onChange={handleSelectAll}
                    />
                  </TableCell>
                  <TableCell>Content</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Price</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Performance</TableCell>
                  <TableCell>Created</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isPending ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <LinearProgress />
                    </TableCell>
                  </TableRow>
                ) : content?.items.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography variant="body2" color="text.secondary">
                        No content found
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  content?.items.map((item) => (
                    <TableRow key={item.id} selected={selectedContent.includes(item.id)}>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selectedContent.includes(item.id)}
                          onChange={() => handleSelectContent(item.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          <Avatar
                            variant="rounded"
                            src={item.thumbnail}
                            sx={{ width: 48, height: 48 }}
                          >
                            {getContentIcon(item.type)}
                          </Avatar>
                          <Box>
                            <Typography variant="body2">{item.title}</Typography>
                            {item.description && (
                              <Typography variant="caption" color="text.secondary">
                                {item.description}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          icon={getContentIcon(item.type)}
                          label={item.type}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {item.price ? (
                          <Typography variant="body2">${item.price}</Typography>
                        ) : (
                          <Chip label="Free" size="small" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Box display="flex" gap={0.5}>
                          {item.is_locked ? (
                            <Tooltip title="Locked">
                              <LockIcon fontSize="small" />
                            </Tooltip>
                          ) : (
                            <Tooltip title="Unlocked">
                              <UnlockIcon fontSize="small" />
                            </Tooltip>
                          )}
                          {item.is_visible ? (
                            <Tooltip title="Visible">
                              <VisibilityIcon fontSize="small" />
                            </Tooltip>
                          ) : (
                            <Tooltip title="Hidden">
                              <VisibilityOffIcon fontSize="small" />
                            </Tooltip>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Box>
                          <Typography variant="caption" display="block">
                            {item.views} views
                          </Typography>
                          <Typography variant="caption" color="success.main">
                            {item.purchases} purchases
                          </Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {new Date(item.created_at).toLocaleDateString()}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Bulk Upload Dialog */}
      <Dialog open={showUploadDialog} onClose={() => setShowUploadDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>Bulk Content Upload</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ pt: 2 }}>
            <Grid item xs={12}>
              <MediaUploader
                onUpload={(files) => setUploadData({ ...uploadData, files })}
                accept={{
                  'image/*': ['.png', '.jpg', '.jpeg', '.gif'],
                  'video/*': ['.mp4', '.mov', '.avi'] }}
                maxFiles={100}
                multiple
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Upload to Model</InputLabel>
                <Select
                  value={uploadData.modelId}
                  onChange={(e) => setUploadData({ ...uploadData, modelId: e.target.value })}
                  label="Upload to Model"
                >
                  {models?.map((model: ModelProfile) => (
                    <MenuItem key={model.id} value={model.id}>
                      {model.stage_name || model.user?.full_name || 'Unknown Model'}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <TextField
                label="Default Price"
                type="number"
                fullWidth
                value={uploadData.price}
                onChange={(e) => setUploadData({ ...uploadData, price: e.target.value })}
                InputProps={{
                  startAdornment: '$' }}
              />
            </Grid>
            <Grid item xs={12}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DateTimePicker
                  label="Schedule Publication"
                  value={uploadData.scheduled_at}
                  onChange={(newValue) => setUploadData({ ...uploadData, scheduled_at: newValue })}
                  slotProps={{
                    textField: {
                      fullWidth: true }
                  }}
                />
              </LocalizationProvider>
            </Grid>
            <Grid item xs={12}>
              <FormGroup>
                <FormControlLabel
                  control={
                    <Switch
                      checked={uploadData.is_locked}
                      onChange={(e) => setUploadData({ ...uploadData, is_locked: e.target.checked })}
                    />
                  }
                  label="Lock content (requires purchase)"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={uploadData.is_visible}
                      onChange={(e) => setUploadData({ ...uploadData, is_visible: e.target.checked })}
                    />
                  }
                  label="Make visible immediately"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={uploadData.auto_generate_thumbnails}
                      onChange={(e) => setUploadData({ ...uploadData, auto_generate_thumbnails: e.target.checked })}
                    />
                  }
                  label="Auto-generate thumbnails"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={uploadData.watermark}
                      onChange={(e) => setUploadData({ ...uploadData, watermark: e.target.checked })}
                    />
                  }
                  label="Add watermark"
                />
              </FormGroup>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowUploadDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleBulkUpload}
            disabled={uploadData.files.length === 0 || !uploadData.modelId}
            startIcon={<UploadIcon />}
          >
            Upload {uploadData.files.length} Files
          </Button>
        </DialogActions>
      </Dialog>

      {/* Bulk Edit Dialog */}
      <Dialog open={showEditDialog} onClose={() => setShowEditDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Bulk Edit Content</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ pt: 2 }}>
            <Grid item xs={12}>
              <Alert severity="info">
                Editing {selectedContent.length} selected items. Leave fields empty to keep current values.
              </Alert>
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Update Price"
                type="number"
                fullWidth
                value={bulkEditData.price}
                onChange={(e) => setBulkEditData({ ...bulkEditData, price: e.target.value })}
                InputProps={{
                  startAdornment: '$' }}
              />
            </Grid>
            <Grid item xs={12}>
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DateTimePicker
                  label="Schedule Changes"
                  value={bulkEditData.scheduled_at}
                  onChange={(newValue) => setBulkEditData({ ...bulkEditData, scheduled_at: newValue })}
                  slotProps={{
                    textField: {
                      fullWidth: true }
                  }}
                />
              </LocalizationProvider>
            </Grid>
            <Grid item xs={12}>
              <FormGroup>
                <FormControlLabel
                  control={
                    <Switch
                      checked={bulkEditData.is_locked}
                      onChange={(e) => setBulkEditData({ ...bulkEditData, is_locked: e.target.checked })}
                    />
                  }
                  label="Lock content"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={bulkEditData.is_visible}
                      onChange={(e) => setBulkEditData({ ...bulkEditData, is_visible: e.target.checked })}
                    />
                  }
                  label="Make visible"
                />
              </FormGroup>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowEditDialog(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={executeBulkEdit}
            disabled={createBulkOperation.isPending}
          >
            Update Content
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default BulkContentOperations;
