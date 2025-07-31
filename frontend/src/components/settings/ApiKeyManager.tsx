import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  IconButton,
  Chip,
  Button,
  Dialog,
  Tooltip,
  Menu,
  MenuItem,
  Alert,
  Skeleton,
  Divider } from '@mui/material';
import {
  Key as KeyIcon,
  MoreVert as MoreIcon,
  Visibility as ViewIcon,
  VisibilityOff as HideIcon,
  RotateRight as RotateIcon,
  Delete as DeleteIcon,
  PlayArrow as TestIcon,
  History as HistoryIcon,
  TrendingUp as StatsIcon,
  Warning as WarningIcon } from '@mui/icons-material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { format } from 'date-fns';
import { ApiKey, ApiKeyProvider } from '@/types/apiKeys';
import { useApiKeys, useDeleteApiKey, useTestApiKey } from '@/hooks/useApiKeys';
import ApiKeyForm from './ApiKeyForm';
import ApiKeyRotateDialog from './ApiKeyRotateDialog';
import ApiKeyStatsDialog from './ApiKeyStatsDialog';
import ApiKeyAuditDialog from './ApiKeyAuditDialog';

interface ApiKeyManagerProps {
  provider?: ApiKeyProvider;
}

const ApiKeyManager: React.FC<ApiKeyManagerProps> = ({ provider }) => {
  const [showForm, setShowForm] = useState(false);
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [selectedKey, setSelectedKey] = useState<ApiKey | null>(null);
  const [showRotateDialog, setShowRotateDialog] = useState(false);
  const [showStatsDialog, setShowStatsDialog] = useState(false);
  const [showAuditDialog, setShowAuditDialog] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set());

  const { data, isPending, error } = useApiKeys({ provider });
  const deleteKey = useDeleteApiKey();
  const testKey = useTestApiKey();

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, key: ApiKey) => {
    setAnchorEl(event.currentTarget);
    setSelectedKey(key);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleToggleVisibility = (keyId: string) => {
    setVisibleKeys(prev => {
      const newSet = new Set(prev);
      if (newSet.has(keyId)) {
        newSet.delete(keyId);
      } else {
        newSet.add(keyId);
      }
      return newSet;
    });
  };

  const handleDelete = async () => {
    if (selectedKey && window.confirm(`Are you sure you want to delete the API key "${selectedKey.name}"?`)) {
      await deleteKey.mutateAsync(selectedKey.id);
    }
    handleMenuClose();
  };

  const handleTest = async () => {
    if (selectedKey) {
      await testKey.mutateAsync(selectedKey.id);
    }
    handleMenuClose();
  };

  const handleRotate = () => {
    setShowRotateDialog(true);
    handleMenuClose();
  };

  const handleStats = () => {
    setShowStatsDialog(true);
    handleMenuClose();
  };

  const handleAudit = () => {
    setShowAuditDialog(true);
    handleMenuClose();
  };

  const getProviderColor = (provider: ApiKeyProvider): 'primary' | 'secondary' | 'success' | 'warning' | 'error' => {
    switch (provider) {
      case ApiKeyProvider.INFLOW:
        return 'primary';
      case ApiKeyProvider.ONLYFANS:
        return 'secondary';
      case ApiKeyProvider.STRIPE:
        return 'success';
      case ApiKeyProvider.PAYPAL:
        return 'warning';
      default:
        return 'error';
    }
  };

  const columns: GridColDef[] = [
    {
      field: 'name',
      headerName: 'Name',
      flex: 1,
      minWidth: 200 },
    {
      field: 'provider',
      headerName: 'Provider',
      width: 120,
      renderCell: (params) => (
        <Chip
          label={params.value}
          size="small"
          color={getProviderColor(params.value)}
        />
      ) },
    {
      field: 'key_prefix',
      headerName: 'API Key',
      width: 200,
      renderCell: (params) => {
        const isVisible = visibleKeys.has(params.row.id);
        return (
          <Box display="flex" alignItems="center" gap={1}>
            <Typography variant="body2" fontFamily="monospace">
              {isVisible ? params.row.key_prefix + '...' : '••••••••'}
            </Typography>
            <IconButton
              size="small"
              onClick={() => handleToggleVisibility(params.row.id)}
            >
              {isVisible ? <HideIcon fontSize="small" /> : <ViewIcon fontSize="small" />}
            </IconButton>
          </Box>
        );
      } },
    {
      field: 'last_used',
      headerName: 'Last Used',
      width: 180,
      renderCell: (params) => (
        params.value ? format(new Date(params.value), 'MMM dd, yyyy HH:mm') : 'Never'
      ) },
    {
      field: 'usage_count',
      headerName: 'Usage',
      width: 100,
      align: 'center',
      headerAlign: 'center' },
    {
      field: 'is_active',
      headerName: 'Status',
      width: 100,
      renderCell: (params) => (
        <Chip
          label={params.value ? 'Active' : 'Inactive'}
          size="small"
          color={params.value ? 'success' : 'default'}
        />
      ) },
    {
      field: 'expires_at',
      headerName: 'Expires',
      width: 180,
      renderCell: (params) => {
        if (!params.value) return 'Never';
        const expiryDate = new Date(params.value);
        const isExpired = expiryDate < new Date();
        const isExpiringSoon = expiryDate < new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
        
        return (
          <Box display="flex" alignItems="center" gap={0.5}>
            {(isExpired || isExpiringSoon) && (
              <Tooltip title={isExpired ? 'Expired' : 'Expiring soon'}>
                <WarningIcon 
                  fontSize="small" 
                  color={isExpired ? 'error' : 'warning'}
                />
              </Tooltip>
            )}
            <Typography 
              variant="body2" 
              color={isExpired ? 'error' : isExpiringSoon ? 'warning.main' : 'text.primary'}
            >
              {format(expiryDate, 'MMM dd, yyyy')}
            </Typography>
          </Box>
        );
      } },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 100,
      sortable: false,
      renderCell: (params) => (
        <>
          <IconButton
            size="small"
            onClick={(e) => handleMenuOpen(e, params.row)}
          >
            <MoreIcon />
          </IconButton>
        </>
      ) },
  ];

  if (isPending) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={400} />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error">
        Failed to load API keys. Please try again later.
      </Alert>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h6">API Keys</Typography>
        <Button
          variant="contained"
          startIcon={<KeyIcon />}
          onClick={() => setShowForm(true)}
        >
          Add API Key
        </Button>
      </Box>

      {data?.keys.length === 0 ? (
        <Card>
          <CardContent>
            <Box textAlign="center" py={4}>
              <KeyIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                No API Keys
              </Typography>
              <Typography variant="body2" color="text.secondary" mb={3}>
                Add your first API key to start integrating with external services.
              </Typography>
              <Button
                variant="contained"
                startIcon={<KeyIcon />}
                onClick={() => setShowForm(true)}
              >
                Add API Key
              </Button>
            </Box>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Box sx={{ height: 400, width: '100%' }}>
            <DataGrid
              rows={data?.keys || []}
              columns={columns}
              pageSizeOptions={[10, 25, 50]}
              initialState={{
                pagination: {
                  paginationModel: {
                    pageSize: 10,
                  },
                },
              }}
              density="comfortable"
            />
          </Box>
        </Card>
      )}

      {/* Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleTest}>
          <TestIcon fontSize="small" sx={{ mr: 1 }} />
          Test Connection
        </MenuItem>
        <MenuItem onClick={handleRotate}>
          <RotateIcon fontSize="small" sx={{ mr: 1 }} />
          Rotate Key
        </MenuItem>
        <MenuItem onClick={handleStats}>
          <StatsIcon fontSize="small" sx={{ mr: 1 }} />
          View Stats
        </MenuItem>
        <MenuItem onClick={handleAudit}>
          <HistoryIcon fontSize="small" sx={{ mr: 1 }} />
          Audit Logs
        </MenuItem>
        <Divider />
        <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}>
          <DeleteIcon fontSize="small" sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>

      {/* Dialogs */}
      <Dialog
        open={showForm}
        onClose={() => {
          setShowForm(false);
          setEditingKey(null);
        }}
        maxWidth="sm"
        fullWidth
      >
        <ApiKeyForm
          onClose={() => {
            setShowForm(false);
            setEditingKey(null);
          }}
          editingKey={editingKey}
        />
      </Dialog>

      {selectedKey && (
        <>
          <ApiKeyRotateDialog
            open={showRotateDialog}
            onClose={() => setShowRotateDialog(false)}
            apiKey={selectedKey}
          />
          <ApiKeyStatsDialog
            open={showStatsDialog}
            onClose={() => setShowStatsDialog(false)}
            apiKey={selectedKey}
          />
          <ApiKeyAuditDialog
            open={showAuditDialog}
            onClose={() => setShowAuditDialog(false)}
            apiKey={selectedKey}
          />
        </>
      )}
    </Box>
  );
};

export default ApiKeyManager;
