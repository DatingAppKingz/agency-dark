import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stepper,
  Step,
  StepLabel,
  FormGroup,
  FormControlLabel,
  Switch,
  Grid } from '@mui/material';
import {
  Send as SendIcon,
  Delete as DeleteIcon,
  Schedule as PreviewIcon,
  AttachFile as AttachIcon,
  Image as ImageIcon,
  VideoLibrary as VideoIcon,
} from '@mui/icons-material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { bulkOperationsService } from '@/services/api/bulkOperations';
import { useModels } from '@/hooks/useModels';
import { ModelProfile } from '@/types/models';
import { BulkOperationType } from '@/types/bulkOperations';
import MediaUploader from '@/components/media/MediaUploader';

interface BulkMessageFormData {
  subject: string;
  message: string;
  recipientType: 'all' | 'active' | 'selected' | 'filter';
  selectedUsers: string[];
  filters: {
    minSpend?: number;
    lastActiveWithinDays?: number;
    subscriptionStatus?: string[];
    location?: string[];
  };
  attachments: {
    images: string[];
    videos: string[];
    documents: string[];
  };
  sendAs: 'model' | 'agency';
  modelId?: string;
  scheduledAt?: Date;
  priority: 'low' | 'normal' | 'high';
  trackOpens: boolean;
  trackClicks: boolean;
}

const BulkMessageOperations: React.FC = () => {
  const [activeStep, setActiveStep] = useState(0);
  const [showPreview, setShowPreview] = useState(false);
  const [selectedOperation, setSelectedOperation] = useState<'send' | 'delete'>('send');
  const [formData, setFormData] = useState<BulkMessageFormData>({
    subject: '',
    message: '',
    recipientType: 'all',
    selectedUsers: [],
    filters: {},
    attachments: {
      images: [],
      videos: [],
      documents: [] },
    sendAs: 'model',
    scheduledAt: undefined,
    priority: 'normal',
    trackOpens: true,
    trackClicks: true });
  const [selectedMessages, setSelectedMessages] = useState<string[]>([]);
  const [recipientCount, setRecipientCount] = useState(0);

  const queryClient = useQueryClient();
  const { data: models } = useModels();

  // Get recipient count based on filters
  const { data: recipients, isPending: loadingRecipients } = useQuery({
    queryKey: ['bulk-recipients', formData.recipientType, formData.filters],
    queryFn: () => bulkOperationsService.getRecipientCount({
      type: formData.recipientType,
      filters: formData.filters }),
    enabled: selectedOperation === 'send' });

  // Create bulk operation
  const createBulkOperation = useMutation({
    mutationFn: (data: any) => bulkOperationsService.createBulkOperation(data),
    onSuccess: () => {
      toast.success('Bulk operation created successfully');
      queryClient.invalidateQueries({ queryKey: ['bulk-operations'] });
      resetForm();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create bulk operation');
    } });

  useEffect(() => {
    if (recipients) {
      setRecipientCount(recipients.count);
    }
  }, [recipients]);

  const steps = ['Select Recipients', 'Compose Message', 'Review & Send'];

  const resetForm = () => {
    setFormData({
      subject: '',
      message: '',
      recipientType: 'all',
      selectedUsers: [],
      filters: {},
      attachments: {
        images: [],
        videos: [],
        documents: [] },
      sendAs: 'model',
      scheduledAt: undefined,
      priority: 'normal',
      trackOpens: true,
      trackClicks: true });
    setActiveStep(0);
    setSelectedMessages([]);
  };

  const handleNext = () => {
    if (activeStep === 0 && recipientCount === 0) {
      toast.error('Please select at least one recipient');
      return;
    }
    if (activeStep === 1 && !formData.message.trim()) {
      toast.error('Please enter a message');
      return;
    }
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  const handleSendBulkMessage = () => {
    const operationData = {
      operation_type: BulkOperationType.MESSAGE_SEND,
      entity_type: 'messages',
      entity_ids: formData.selectedUsers.length > 0 ? formData.selectedUsers : [],
      operation_params: {
        subject: formData.subject,
        message: formData.message,
        recipient_type: formData.recipientType,
        filters: formData.filters,
        attachments: formData.attachments,
        send_as: formData.sendAs,
        model_id: formData.modelId,
        priority: formData.priority,
        tracking: {
          track_opens: formData.trackOpens,
          track_clicks: formData.trackClicks } },
      scheduled_at: formData.scheduledAt,
      notes: `Bulk message to ${recipientCount} recipients` };

    createBulkOperation.mutate(operationData);
  };

  const handleDeleteMessages = () => {
    if (selectedMessages.length === 0) {
      toast.error('Please select messages to delete');
      return;
    }

    const operationData = {
      operation_type: BulkOperationType.MESSAGE_DELETE,
      entity_type: 'messages',
      entity_ids: selectedMessages,
      operation_params: {
        permanent: false, // Soft delete by default
      },
      notes: `Bulk delete ${selectedMessages.length} messages` };

    createBulkOperation.mutate(operationData);
  };

  const renderRecipientSelection = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        Select Recipients
      </Typography>
      
      <FormControl fullWidth sx={{ mb: 3 }}>
        <InputLabel>Recipient Type</InputLabel>
        <Select
          value={formData.recipientType}
          onChange={(e) => setFormData({ ...formData, recipientType: e.target.value as any })}
          label="Recipient Type"
        >
          <MenuItem value="all">All Subscribers</MenuItem>
          <MenuItem value="active">Active Subscribers Only</MenuItem>
          <MenuItem value="selected">Select Specific Users</MenuItem>
          <MenuItem value="filter">Apply Filters</MenuItem>
        </Select>
      </FormControl>

      {formData.recipientType === 'filter' && (
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Minimum Spend ($)"
              type="number"
              fullWidth
              value={formData.filters.minSpend || ''}
              onChange={(e) => setFormData({
                ...formData,
                filters: { ...formData.filters, minSpend: Number(e.target.value) }
              })}
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <TextField
              label="Active Within (Days)"
              type="number"
              fullWidth
              value={formData.filters.lastActiveWithinDays || ''}
              onChange={(e) => setFormData({
                ...formData,
                filters: { ...formData.filters, lastActiveWithinDays: Number(e.target.value) }
              })}
            />
          </Grid>
        </Grid>
      )}

      {formData.recipientType === 'selected' && (
        <Alert severity="info" sx={{ mt: 2 }}>
          User selection interface would be implemented here
        </Alert>
      )}

      <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
        <Typography variant="body2" color="text.secondary">
          Estimated Recipients
        </Typography>
        <Typography variant="h4">
          {loadingRecipients ? '...' : recipientCount.toLocaleString()}
        </Typography>
      </Box>
    </Box>
  );

  const renderMessageComposer = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        Compose Message
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <TextField
            label="Subject (Optional)"
            fullWidth
            value={formData.subject}
            onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
            sx={{ mb: 2 }}
          />

          <TextField
            label="Message"
            multiline
            rows={10}
            fullWidth
            required
            value={formData.message}
            onChange={(e) => setFormData({ ...formData, message: e.target.value })}
            placeholder="Type your message here..."
            sx={{ mb: 2 }}
          />

          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" gutterBottom>
              Attachments
            </Typography>
            <MediaUploader
              onUpload={() => {
                // Handle uploads
                toast.success('Files uploaded successfully');
              }}
              accept={{
                'image/*': ['.png', '.jpg', '.jpeg', '.gif'],
                'video/*': ['.mp4', '.mov', '.avi'] }}
              maxFiles={10}
            />
          </Box>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Message Settings
              </Typography>

              <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                <InputLabel>Send As</InputLabel>
                <Select
                  value={formData.sendAs}
                  onChange={(e) => setFormData({ ...formData, sendAs: e.target.value as any })}
                  label="Send As"
                >
                  <MenuItem value="model">Model</MenuItem>
                  <MenuItem value="agency">Agency</MenuItem>
                </Select>
              </FormControl>

              {formData.sendAs === 'model' && (
                <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                  <InputLabel>Select Model</InputLabel>
                  <Select
                    value={formData.modelId || ''}
                    onChange={(e) => setFormData({ ...formData, modelId: e.target.value })}
                    label="Select Model"
                  >
                    {models?.map((model: ModelProfile) => (
                      <MenuItem key={model.id} value={model.id}>
                        {model.stage_name || model.user?.full_name || 'Unknown Model'}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}

              <FormControl fullWidth size="small" sx={{ mb: 2 }}>
                <InputLabel>Priority</InputLabel>
                <Select
                  value={formData.priority}
                  onChange={(e) => setFormData({ ...formData, priority: e.target.value as any })}
                  label="Priority"
                >
                  <MenuItem value="low">Low</MenuItem>
                  <MenuItem value="normal">Normal</MenuItem>
                  <MenuItem value="high">High</MenuItem>
                </Select>
              </FormControl>

              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <DateTimePicker
                  label="Schedule For"
                  value={formData.scheduledAt || null}
                  onChange={(newValue) => setFormData({ ...formData, scheduledAt: newValue || undefined })}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      size: 'small',
                      sx: { mb: 2 }
                    }
                  }}
                />
              </LocalizationProvider>

              <FormGroup>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.trackOpens}
                      onChange={(e) => setFormData({ ...formData, trackOpens: e.target.checked })}
                    />
                  }
                  label="Track Opens"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.trackClicks}
                      onChange={(e) => setFormData({ ...formData, trackClicks: e.target.checked })}
                    />
                  }
                  label="Track Clicks"
                />
              </FormGroup>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  const renderReview = () => (
    <Box>
      <Typography variant="h6" gutterBottom>
        Review & Send
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Message Preview
              </Typography>
              
              {formData.subject && (
                <Typography variant="h6" gutterBottom>
                  {formData.subject}
                </Typography>
              )}
              
              <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
                {formData.message}
              </Typography>

              {(formData.attachments.images.length > 0 || 
                formData.attachments.videos.length > 0 || 
                formData.attachments.documents.length > 0) && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Attachments
                  </Typography>
                  <Box display="flex" gap={1} flexWrap="wrap">
                    {formData.attachments.images.map((idx) => (
                      <Chip key={idx} icon={<ImageIcon />} label={`Image ${idx + 1}`} size="small" />
                    ))}
                    {formData.attachments.videos.map((idx) => (
                      <Chip key={idx} icon={<VideoIcon />} label={`Video ${idx + 1}`} size="small" />
                    ))}
                    {formData.attachments.documents.map((_, idx) => (
                      <Chip key={idx} icon={<AttachIcon />} label={`Document ${idx + 1}`} size="small" />
                    ))}
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="subtitle2" gutterBottom>
                Send Summary
              </Typography>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Recipients
                </Typography>
                <Typography variant="h5">
                  {recipientCount.toLocaleString()}
                </Typography>
              </Box>

              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Send As
                </Typography>
                <Typography>
                  {formData.sendAs === 'model' ? 
                    models?.find((m: ModelProfile) => m.id === formData.modelId)?.stage_name || 'Model' : 
                    'Agency'}
                </Typography>
              </Box>

              {formData.scheduledAt && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    Scheduled For
                  </Typography>
                  <Typography>
                    {formData.scheduledAt.toLocaleString()}
                  </Typography>
                </Box>
              )}

              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Estimated Cost
                </Typography>
                <Typography variant="h6">
                  ${(recipientCount * 0.01).toFixed(2)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ($0.01 per message)
                </Typography>
              </Box>

              <Alert severity="warning" sx={{ mt: 2 }}>
                <Typography variant="body2">
                  This action cannot be undone. Messages will be sent to all selected recipients.
                </Typography>
              </Alert>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );

  if (selectedOperation === 'delete') {
    return (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Bulk Delete Messages
          </Typography>
          <Alert severity="info" sx={{ mb: 2 }}>
            Select messages from the message list to delete them in bulk.
          </Alert>
          <Typography variant="body2" color="text.secondary">
            {selectedMessages.length} messages selected
          </Typography>
          <Box sx={{ mt: 2 }}>
            <Button
              variant="contained"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={handleDeleteMessages}
              disabled={selectedMessages.length === 0}
            >
              Delete Selected Messages
            </Button>
          </Box>
        </CardContent>
      </Card>
    );
  }

  return (
    <Box>
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
            <Typography variant="h5">Bulk Message Operations</Typography>
            <Box display="flex" gap={1}>
              <Button
                variant={selectedOperation === 'send' ? 'contained' : 'outlined'}
                startIcon={<SendIcon />}
                onClick={() => setSelectedOperation('send')}
              >
                Send Messages
              </Button>
              <Button
                variant="outlined"
                startIcon={<DeleteIcon />}
                onClick={() => setSelectedOperation('delete')}
              >
                Delete Messages
              </Button>
            </Box>
          </Box>

          <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>

          {activeStep === 0 && renderRecipientSelection()}
          {activeStep === 1 && renderMessageComposer()}
          {activeStep === 2 && renderReview()}

          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
            <Button
              disabled={activeStep === 0}
              onClick={handleBack}
            >
              Back
            </Button>
            <Box display="flex" gap={2}>
              {activeStep === 2 && (
                <Button
                  variant="outlined"
                  startIcon={<PreviewIcon />}
                  onClick={() => setShowPreview(true)}
                >
                  Preview
                </Button>
              )}
              <Button
                variant="contained"
                onClick={activeStep === 2 ? handleSendBulkMessage : handleNext}
                disabled={createBulkOperation.isPending}
              >
                {activeStep === 2 ? (formData.scheduledAt ? 'Schedule' : 'Send Now') : 'Next'}
              </Button>
            </Box>
          </Box>
        </CardContent>
      </Card>

      {/* Message Preview Dialog */}
      <Dialog open={showPreview} onClose={() => setShowPreview(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Message Preview</DialogTitle>
        <DialogContent>
          <Box sx={{ p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
            {formData.subject && (
              <Typography variant="h6" gutterBottom>
                {formData.subject}
              </Typography>
            )}
            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>
              {formData.message}
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowPreview(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default BulkMessageOperations;
