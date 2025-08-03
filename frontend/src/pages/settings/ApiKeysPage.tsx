import React, { useState } from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Alert,
  Tooltip,
  Divider,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  FormControlLabel,
  Checkbox,
  Grid,
  Collapse,
  Snackbar,
} from '@mui/material';
import {
  Add,
  ContentCopy,
  Delete,
  Edit,
  Key,
  Visibility,
  VisibilityOff,
  RotateLeft,
  Warning,
  CheckCircle,
  Cancel,
  AccessTime,
  Security,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useAuth } from '@/hooks/useAuth';

interface ApiKey {
  id: string;
  name: string;
  key: string;
  provider: 'inflow' | 'onlyfans' | 'stripe' | 'paypal' | 'custom';
  created: Date;
  lastUsed: Date | null;
  expiresAt: Date | null;
  status: 'active' | 'expired' | 'revoked';
  scopes: string[];
  usage: number;
}

const ApiKeysPage = () => {
  const { user } = useAuth();
  const [keys, setKeys] = useState<ApiKey[]>([
    {
      id: '1',
      name: 'Production API Key',
      key: 'sk_live_4eC39HqLyjWDarjtT1zdp7dc',
      provider: 'stripe',
      created: new Date('2024-01-15'),
      lastUsed: new Date('2024-03-20'),
      expiresAt: new Date('2025-01-15'),
      status: 'active',
      scopes: ['read', 'write'],
      usage: 15234,
    },
    {
      id: '2',
      name: 'OnlyFans Integration',
      key: 'of_prod_8xK2mNpLqRsTuVwXyZ',
      provider: 'onlyfans',
      created: new Date('2024-02-01'),
      lastUsed: new Date('2024-03-19'),
      expiresAt: null,
      status: 'active',
      scopes: ['subscribers.read', 'messages.read', 'messages.write', 'analytics.read'],
      usage: 8756,
    },
    {
      id: '3',
      name: 'Test Environment Key',
      key: 'sk_test_9bC4dEfGhIjKlMnOpQ',
      provider: 'stripe',
      created: new Date('2023-12-01'),
      lastUsed: null,
      expiresAt: new Date('2024-01-01'),
      status: 'expired',
      scopes: ['read'],
      usage: 0,
    },
  ]);

  const [showKey, setShowKey] = useState<{ [key: string]: boolean }>({});
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editingKey, setEditingKey] = useState<ApiKey | null>(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as any });

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    provider: 'custom' as any,
    expiresIn: 'never',
    scopes: {
      read: true,
      write: false,
      delete: false,
      analytics: false,
      messages: false,
      subscribers: false,
    },
  });

  const handleCreateKey = () => {
    // Mock creating a new key
    const newKey: ApiKey = {
      id: Date.now().toString(),
      name: formData.name,
      key: `${formData.provider}_${Math.random().toString(36).substring(2, 15)}`,
      provider: formData.provider,
      created: new Date(),
      lastUsed: null,
      expiresAt: formData.expiresIn === 'never' ? null : new Date(Date.now() + parseInt(formData.expiresIn) * 24 * 60 * 60 * 1000),
      status: 'active',
      scopes: Object.entries(formData.scopes).filter(([_, v]) => v).map(([k]) => k),
      usage: 0,
    };

    setKeys([...keys, newKey]);
    setCreateDialogOpen(false);
    setFormData({
      name: '',
      provider: 'custom',
      expiresIn: 'never',
      scopes: {
        read: true,
        write: false,
        delete: false,
        analytics: false,
        messages: false,
        subscribers: false,
      },
    });
    setSnackbar({ open: true, message: 'API key created successfully', severity: 'success' });
  };

  const handleDeleteKey = (id: string) => {
    if (window.confirm('Are you sure you want to delete this API key? This action cannot be undone.')) {
      setKeys(keys.filter(k => k.id !== id));
      setSnackbar({ open: true, message: 'API key deleted successfully', severity: 'success' });
    }
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setSnackbar({ open: true, message: 'API key copied to clipboard', severity: 'success' });
  };

  const toggleKeyVisibility = (id: string) => {
    setShowKey(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const maskKey = (key: string) => {
    return key.substring(0, 10) + '...' + key.substring(key.length - 4);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'expired':
        return 'error';
      case 'revoked':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getProviderColor = (provider: string) => {
    switch (provider) {
      case 'stripe':
        return '#635BFF';
      case 'onlyfans':
        return '#00AFF0';
      case 'inflow':
        return '#4F46E5';
      case 'paypal':
        return '#0070BA';
      default:
        return '#6B7280';
    }
  };

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            API Keys
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage your API keys for external integrations
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => setCreateDialogOpen(true)}
        >
          Create API Key
        </Button>
      </Box>

      {/* Security Notice */}
      <Alert 
        severity="warning" 
        icon={<Security />}
        sx={{ mb: 3 }}
      >
        <Typography variant="body2">
          <strong>Security Notice:</strong> Keep your API keys secure and never share them publicly. 
          Rotate keys regularly and delete any that are no longer needed.
        </Typography>
      </Alert>

      {/* API Keys Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>API Key</TableCell>
              <TableCell>Provider</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Last Used</TableCell>
              <TableCell>Usage</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {keys.map((apiKey) => (
              <TableRow key={apiKey.id} hover>
                <TableCell>
                  <Box>
                    <Typography variant="subtitle2">{apiKey.name}</Typography>
                    <Box display="flex" gap={0.5} mt={0.5}>
                      {apiKey.scopes.map((scope) => (
                        <Chip 
                          key={scope}
                          label={scope}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                </TableCell>
                <TableCell>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Typography 
                      variant="body2" 
                      sx={{ fontFamily: 'monospace' }}
                    >
                      {showKey[apiKey.id] ? apiKey.key : maskKey(apiKey.key)}
                    </Typography>
                    <IconButton 
                      size="small" 
                      onClick={() => toggleKeyVisibility(apiKey.id)}
                    >
                      {showKey[apiKey.id] ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                    <IconButton 
                      size="small" 
                      onClick={() => handleCopyKey(apiKey.key)}
                    >
                      <ContentCopy />
                    </IconButton>
                  </Box>
                </TableCell>
                <TableCell>
                  <Chip
                    label={apiKey.provider.toUpperCase()}
                    size="small"
                    sx={{
                      backgroundColor: getProviderColor(apiKey.provider),
                      color: 'white',
                    }}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={apiKey.status}
                    color={getStatusColor(apiKey.status)}
                    size="small"
                    icon={
                      apiKey.status === 'active' ? <CheckCircle /> :
                      apiKey.status === 'expired' ? <Cancel /> :
                      <Warning />
                    }
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="body2">
                    {format(apiKey.created, 'MMM d, yyyy')}
                  </Typography>
                  {apiKey.expiresAt && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      Expires: {format(apiKey.expiresAt, 'MMM d, yyyy')}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  {apiKey.lastUsed ? (
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <AccessTime fontSize="small" color="action" />
                      <Typography variant="body2">
                        {format(apiKey.lastUsed, 'MMM d, yyyy')}
                      </Typography>
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Never
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  <Typography variant="body2">
                    {apiKey.usage.toLocaleString()} requests
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Tooltip title="Rotate Key">
                    <IconButton size="small">
                      <RotateLeft />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Edit">
                    <IconButton size="small">
                      <Edit />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton 
                      size="small" 
                      onClick={() => handleDeleteKey(apiKey.id)}
                      color="error"
                    >
                      <Delete />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Create API Key Dialog */}
      <Dialog 
        open={createDialogOpen} 
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Create New API Key</DialogTitle>
        <DialogContent>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Key Name"
                placeholder="e.g., Production API Key"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Provider</InputLabel>
                <Select
                  value={formData.provider}
                  label="Provider"
                  onChange={(e) => setFormData({ ...formData, provider: e.target.value as any })}
                >
                  <MenuItem value="custom">Custom</MenuItem>
                  <MenuItem value="inflow">Inflow</MenuItem>
                  <MenuItem value="onlyfans">OnlyFans</MenuItem>
                  <MenuItem value="stripe">Stripe</MenuItem>
                  <MenuItem value="paypal">PayPal</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Expires In</InputLabel>
                <Select
                  value={formData.expiresIn}
                  label="Expires In"
                  onChange={(e) => setFormData({ ...formData, expiresIn: e.target.value })}
                >
                  <MenuItem value="never">Never</MenuItem>
                  <MenuItem value="30">30 days</MenuItem>
                  <MenuItem value="90">90 days</MenuItem>
                  <MenuItem value="180">180 days</MenuItem>
                  <MenuItem value="365">1 year</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Permissions
              </Typography>
              <Box>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.scopes.read}
                      onChange={(e) => setFormData({
                        ...formData,
                        scopes: { ...formData.scopes, read: e.target.checked }
                      })}
                    />
                  }
                  label="Read"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.scopes.write}
                      onChange={(e) => setFormData({
                        ...formData,
                        scopes: { ...formData.scopes, write: e.target.checked }
                      })}
                    />
                  }
                  label="Write"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={formData.scopes.delete}
                      onChange={(e) => setFormData({
                        ...formData,
                        scopes: { ...formData.scopes, delete: e.target.checked }
                      })}
                    />
                  }
                  label="Delete"
                />
                {(formData.provider === 'onlyfans' || formData.provider === 'inflow') && (
                  <>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={formData.scopes.analytics}
                          onChange={(e) => setFormData({
                            ...formData,
                            scopes: { ...formData.scopes, analytics: e.target.checked }
                          })}
                        />
                      }
                      label="Analytics"
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={formData.scopes.messages}
                          onChange={(e) => setFormData({
                            ...formData,
                            scopes: { ...formData.scopes, messages: e.target.checked }
                          })}
                        />
                      }
                      label="Messages"
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={formData.scopes.subscribers}
                          onChange={(e) => setFormData({
                            ...formData,
                            scopes: { ...formData.scopes, subscribers: e.target.checked }
                          })}
                        />
                      }
                      label="Subscribers"
                    />
                  </>
                )}
              </Box>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleCreateKey} 
            variant="contained"
            disabled={!formData.name}
          >
            Create Key
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        message={snackbar.message}
      />
    </Box>
  );
};

export default ApiKeysPage;