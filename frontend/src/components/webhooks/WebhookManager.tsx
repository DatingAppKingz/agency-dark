import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormGroup,
  FormControlLabel,
  Checkbox,
  Switch,
  Alert,
  Tabs,
  Tab,
  Badge,
  Tooltip,
  Skeleton,
  Menu,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Settings as SettingsIcon,
  Send as SendIcon,
  History as HistoryIcon,
  Warning as WarningIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  MoreVert as MoreIcon,
  Refresh as RefreshIcon,
  BugReport as DebugIcon,
  PlayArrow as TestIcon,
  Storage as DeadLetterIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { format } from 'date-fns';
import { webhookService } from '@/services/api/webhooks';
import { WebhookEvent, WebhookResponse, WebhookDelivery } from '@/types/webhooks';
import WebhookDeliveryHistory from './WebhookDeliveryHistory';
import WebhookDeadLetters from './WebhookDeadLetters';
import WebhookTester from './WebhookTester';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const WebhookManager: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [editingWebhook, setEditingWebhook] = useState<WebhookResponse | null>(null);
  const [selectedWebhook, setSelectedWebhook] = useState<string | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuWebhookId, setMenuWebhookId] = useState<string | null>(null);

  const queryClient = useQueryClient();

  // Webhook form state
  const [webhookForm, setWebhookForm] = useState({
    url: '',
    description: '',
    events: [] as WebhookEvent[],
    is_active: true,
    retry_enabled: true,
    max_retries: 3,
    timeout_seconds: 30,
    custom_headers: {} as Record<string, string>,
  });

  // Fetch webhooks
  const { data: webhooks, isLoading } = useQuery({
    queryKey: ['webhooks'],
    queryFn: webhookService.listWebhooks,
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  // Create webhook mutation
  const createWebhook = useMutation({
    mutationFn: webhookService.createWebhook,
    onSuccess: () => {
      toast.success('Webhook created successfully');
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      setShowCreateDialog(false);
      resetForm();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create webhook');
    },
  });

  // Update webhook mutation
  const updateWebhook = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      webhookService.updateWebhook(id, data),
    onSuccess: () => {
      toast.success('Webhook updated successfully');
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
      setEditingWebhook(null);
      resetForm();
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to update webhook');
    },
  });

  // Delete webhook mutation
  const deleteWebhook = useMutation({
    mutationFn: webhookService.deleteWebhook,
    onSuccess: () => {
      toast.success('Webhook deleted successfully');
      queryClient.invalidateQueries({ queryKey: ['webhooks'] });
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete webhook');
    },
  });

  // Test webhook mutation
  const testWebhook = useMutation({
    mutationFn: webhookService.testWebhook,
    onSuccess: () => {
      toast.success('Test webhook sent successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to send test webhook');
    },
  });

  const resetForm = () => {
    setWebhookForm({
      url: '',
      description: '',
      events: [],
      is_active: true,
      retry_enabled: true,
      max_retries: 3,
      timeout_seconds: 30,
      custom_headers: {},
    });
  };

  const handleCreateOrUpdate = () => {
    if (editingWebhook) {
      updateWebhook.mutate({
        id: editingWebhook.id,
        data: webhookForm,
      });
    } else {
      createWebhook.mutate(webhookForm);
    }
  };

  const handleEdit = (webhook: WebhookResponse) => {
    setWebhookForm({
      url: webhook.url,
      description: webhook.description || '',
      events: webhook.events as WebhookEvent[],
      is_active: webhook.is_active,
      retry_enabled: webhook.retry_enabled,
      max_retries: webhook.max_retries,
      timeout_seconds: webhook.timeout_seconds,
      custom_headers: webhook.custom_headers,
    });
    setEditingWebhook(webhook);
    setShowCreateDialog(true);
  };

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, webhookId: string) => {
    setAnchorEl(event.currentTarget);
    setMenuWebhookId(webhookId);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setMenuWebhookId(null);
  };

  const getStatusIcon = (webhook: WebhookResponse) => {
    if (!webhook.is_active) {
      return <Chip label="Inactive" size="small" color="default" />;
    }
    if (webhook.failed_deliveries > webhook.successful_deliveries) {
      return <Chip label="Failing" size="small" color="error" icon={<ErrorIcon />} />;
    }
    if (webhook.successful_deliveries > 0) {
      return <Chip label="Healthy" size="small" color="success" icon={<SuccessIcon />} />;
    }
    return <Chip label="New" size="small" color="primary" />;
  };

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Webhook Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setShowCreateDialog(true)}
        >
          Create Webhook
        </Button>
      </Box>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)}>
          <Tab label="Webhooks" />
          <Tab 
            label={
              <Badge badgeContent={webhooks?.filter(w => !w.is_active).length || 0} color="warning">
                Dead Letters
              </Badge>
            } 
          />
          <Tab label="Testing" />
        </Tabs>
      </Paper>

      {/* Tab Panels */}
      <TabPanel value={activeTab} index={0}>
        {/* Webhooks List */}
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>URL</TableCell>
                <TableCell>Events</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Success Rate</TableCell>
                <TableCell>Last Delivery</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                [...Array(3)].map((_, i) => (
                  <TableRow key={i}>
                    <TableCell><Skeleton /></TableCell>
                    <TableCell><Skeleton /></TableCell>
                    <TableCell><Skeleton /></TableCell>
                    <TableCell><Skeleton /></TableCell>
                    <TableCell><Skeleton /></TableCell>
                    <TableCell><Skeleton /></TableCell>
                  </TableRow>
                ))
              ) : webhooks && webhooks.length > 0 ? (
                webhooks.map((webhook) => (
                  <TableRow key={webhook.id}>
                    <TableCell>
                      <Box>
                        <Typography variant="body2">{webhook.url}</Typography>
                        {webhook.description && (
                          <Typography variant="caption" color="text.secondary">
                            {webhook.description}
                          </Typography>
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box display="flex" gap={0.5} flexWrap="wrap">
                        {webhook.events.slice(0, 3).map((event) => (
                          <Chip key={event} label={event} size="small" />
                        ))}
                        {webhook.events.length > 3 && (
                          <Chip label={`+${webhook.events.length - 3}`} size="small" />
                        )}
                      </Box>
                    </TableCell>
                    <TableCell>{getStatusIcon(webhook)}</TableCell>
                    <TableCell>
                      {webhook.total_deliveries > 0 ? (
                        <Typography variant="body2">
                          {webhook.success_rate.toFixed(1)}%
                        </Typography>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          No deliveries
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell>
                      {webhook.last_delivery_at ? (
                        <Tooltip title={format(new Date(webhook.last_delivery_at), 'PPpp')}>
                          <Typography variant="body2">
                            {format(new Date(webhook.last_delivery_at), 'MMM d, HH:mm')}
                          </Typography>
                        </Tooltip>
                      ) : (
                        <Typography variant="body2" color="text.secondary">
                          Never
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={(e) => handleMenuClick(e, webhook.id)}
                      >
                        <MoreIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} align="center">
                    <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                      No webhooks configured
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Selected webhook details */}
        {selectedWebhook && (
          <Box mt={3}>
            <WebhookDeliveryHistory webhookId={selectedWebhook} />
          </Box>
        )}
      </TabPanel>

      <TabPanel value={activeTab} index={1}>
        <WebhookDeadLetters />
      </TabPanel>

      <TabPanel value={activeTab} index={2}>
        <WebhookTester webhooks={webhooks || []} />
      </TabPanel>

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem
          onClick={() => {
            const webhook = webhooks?.find(w => w.id === menuWebhookId);
            if (webhook) {
              handleEdit(webhook);
            }
            handleMenuClose();
          }}
        >
          <ListItemIcon><EditIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Edit</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (menuWebhookId) {
              testWebhook.mutate(menuWebhookId);
            }
            handleMenuClose();
          }}
        >
          <ListItemIcon><TestIcon fontSize="small" /></ListItemIcon>
          <ListItemText>Send Test</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            setSelectedWebhook(menuWebhookId);
            handleMenuClose();
          }}
        >
          <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
          <ListItemText>View History</ListItemText>
        </MenuItem>
        <MenuItem
          onClick={() => {
            if (menuWebhookId && window.confirm('Are you sure you want to delete this webhook?')) {
              deleteWebhook.mutate(menuWebhookId);
            }
            handleMenuClose();
          }}
          sx={{ color: 'error.main' }}
        >
          <ListItemIcon><DeleteIcon fontSize="small" color="error" /></ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Create/Edit Dialog */}
      <Dialog
        open={showCreateDialog || Boolean(editingWebhook)}
        onClose={() => {
          setShowCreateDialog(false);
          setEditingWebhook(null);
          resetForm();
        }}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {editingWebhook ? 'Edit Webhook' : 'Create Webhook'}
        </DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" gap={2} sx={{ pt: 1 }}>
            <TextField
              label="Webhook URL"
              value={webhookForm.url}
              onChange={(e) => setWebhookForm({ ...webhookForm, url: e.target.value })}
              fullWidth
              required
              helperText="The URL to send webhook events to"
            />
            
            <TextField
              label="Description"
              value={webhookForm.description}
              onChange={(e) => setWebhookForm({ ...webhookForm, description: e.target.value })}
              fullWidth
              multiline
              rows={2}
              helperText="Optional description for this webhook"
            />
            
            <FormControl fullWidth required>
              <InputLabel>Events</InputLabel>
              <Select
                multiple
                value={webhookForm.events}
                onChange={(e) => setWebhookForm({ ...webhookForm, events: e.target.value as WebhookEvent[] })}
                label="Events"
              >
                {Object.values(WebhookEvent).map((event) => (
                  <MenuItem key={event} value={event}>
                    {event}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <Box display="flex" gap={2}>
              <FormControlLabel
                control={
                  <Switch
                    checked={webhookForm.is_active}
                    onChange={(e) => setWebhookForm({ ...webhookForm, is_active: e.target.checked })}
                  />
                }
                label="Active"
              />
              
              <FormControlLabel
                control={
                  <Switch
                    checked={webhookForm.retry_enabled}
                    onChange={(e) => setWebhookForm({ ...webhookForm, retry_enabled: e.target.checked })}
                  />
                }
                label="Enable Retries"
              />
            </Box>
            
            {webhookForm.retry_enabled && (
              <Box display="flex" gap={2}>
                <TextField
                  label="Max Retries"
                  type="number"
                  value={webhookForm.max_retries}
                  onChange={(e) => setWebhookForm({ ...webhookForm, max_retries: parseInt(e.target.value) })}
                  inputProps={{ min: 0, max: 10 }}
                  fullWidth
                />
                
                <TextField
                  label="Timeout (seconds)"
                  type="number"
                  value={webhookForm.timeout_seconds}
                  onChange={(e) => setWebhookForm({ ...webhookForm, timeout_seconds: parseInt(e.target.value) })}
                  inputProps={{ min: 5, max: 60 }}
                  fullWidth
                />
              </Box>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => {
            setShowCreateDialog(false);
            setEditingWebhook(null);
            resetForm();
          }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleCreateOrUpdate}
            disabled={!webhookForm.url || webhookForm.events.length === 0}
          >
            {editingWebhook ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default WebhookManager;