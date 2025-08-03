import React, { useState } from 'react';
import {
  Box,
  Button,
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
  FormControl,
  InputLabel,
  Select,
  FormControlLabel,
  Checkbox,
  Grid,
  Snackbar,
  Card,
  CardContent,
  FormGroup,
} from '@mui/material';
import {
  Add,
  ContentCopy,
  Delete,
  Edit,
  Visibility,
  VisibilityOff,
  RotateLeft,
  Warning,
  CheckCircle,
  Cancel,
  AccessTime,
  Security,
  Instagram,
  CreditCard,
  Analytics,
  Link,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useAuth } from '@/hooks/useAuth';

interface AgencyApiKey {
  id: string;
  name: string;
  key: string;
  provider: 'onlyfans' | 'stripe' | 'inflow' | 'custom';
  modelId?: string; // For OnlyFans keys tied to specific models
  modelName?: string;
  created: Date;
  lastUsed: Date | null;
  expiresAt: Date | null;
  status: 'active' | 'expired' | 'revoked';
  scopes: string[];
  usage: number;
}

const AgencyApiKeysPage = () => {
  const { user } = useAuth();
  const [keys, setKeys] = useState<AgencyApiKey[]>([
    {
      id: '1',
      name: 'OnlyFans - Sarah Model',
      key: 'of_prod_sarah_8xK2mNpLqRsTuVwXyZ',
      provider: 'onlyfans',
      modelId: 'model_1',
      modelName: 'Sarah Johnson',
      created: new Date('2024-02-01'),
      lastUsed: new Date('2024-03-20'),
      expiresAt: null,
      status: 'active',
      scopes: ['profile.read', 'messages.read', 'messages.write', 'subscribers.read', 'transactions.read'],
      usage: 12543,
    },
    {
      id: '2',
      name: 'OnlyFans - Emma Model',
      key: 'of_prod_emma_7yL3nOpQrStUvWxZ',
      provider: 'onlyfans',
      modelId: 'model_2',
      modelName: 'Emma Davis',
      created: new Date('2024-02-15'),
      lastUsed: new Date('2024-03-19'),
      expiresAt: null,
      status: 'active',
      scopes: ['profile.read', 'messages.read', 'messages.write', 'subscribers.read'],
      usage: 8234,
    },
    {
      id: '3',
      name: 'Stripe Agency Account',
      key: 'sk_live_agency_4eC39HqLyjWDarjtT1zdp7dc',
      provider: 'stripe',
      created: new Date('2024-01-15'),
      lastUsed: new Date('2024-03-20'),
      expiresAt: new Date('2025-01-15'),
      status: 'active',
      scopes: ['charges.create', 'customers.read', 'invoices.read', 'payouts.read'],
      usage: 5234,
    },
    {
      id: '4',
      name: 'Inflow Analytics',
      key: 'inflow_prod_9bC4dEfGhIjKlMnOpQ',
      provider: 'inflow',
      created: new Date('2024-03-01'),
      lastUsed: new Date('2024-03-20'),
      expiresAt: null,
      status: 'active',
      scopes: ['analytics.read', 'reports.create'],
      usage: 1523,
    },
  ]);

  const [showKey, setShowKey] = useState<{ [key: string]: boolean }>({});
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as any });

  const [formData, setFormData] = useState({
    name: '',
    provider: 'onlyfans' as any,
    modelId: '',
    expiresIn: 'never',
    scopes: {
      // OnlyFans scopes
      'profile.read': true,
      'messages.read': false,
      'messages.write': false,
      'subscribers.read': false,
      'transactions.read': false,
      'content.read': false,
      'content.write': false,
      // Stripe scopes
      'charges.create': false,
      'customers.read': false,
      'invoices.read': false,
      'payouts.read': false,
      // Inflow scopes
      'analytics.read': false,
      'reports.create': false,
    },
  });

  // Mock models data
  const models = [
    { id: 'model_1', name: 'Sarah Johnson' },
    { id: 'model_2', name: 'Emma Davis' },
    { id: 'model_3', name: 'Jessica Wilson' },
    { id: 'model_4', name: 'Ashley Brown' },
  ];

  const handleCreateKey = () => {
    const selectedModel = models.find(m => m.id === formData.modelId);
    const newKey: AgencyApiKey = {
      id: Date.now().toString(),
      name: formData.name,
      key: `${formData.provider}_prod_${Math.random().toString(36).substring(2, 15)}`,
      provider: formData.provider,
      modelId: formData.modelId,
      modelName: selectedModel?.name,
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
      provider: 'onlyfans',
      modelId: '',
      expiresIn: 'never',
      scopes: {
        'profile.read': true,
        'messages.read': false,
        'messages.write': false,
        'subscribers.read': false,
        'transactions.read': false,
        'content.read': false,
        'content.write': false,
        'charges.create': false,
        'customers.read': false,
        'invoices.read': false,
        'payouts.read': false,
        'analytics.read': false,
        'reports.create': false,
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
    return key.substring(0, 12) + '...' + key.substring(key.length - 4);
  };

  const getProviderIcon = (provider: string) => {
    switch (provider) {
      case 'onlyfans':
        return <Instagram />;
      case 'stripe':
        return <CreditCard />;
      case 'inflow':
        return <Analytics />;
      default:
        return <Link />;
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
      default:
        return '#6B7280';
    }
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

  const getScopesByProvider = (provider: string) => {
    switch (provider) {
      case 'onlyfans':
        return ['profile.read', 'messages.read', 'messages.write', 'subscribers.read', 'transactions.read', 'content.read', 'content.write'];
      case 'stripe':
        return ['charges.create', 'customers.read', 'invoices.read', 'payouts.read'];
      case 'inflow':
        return ['analytics.read', 'reports.create'];
      default:
        return [];
    }
  };

  // Check if user has permission
  const canManageApiKeys = ['agency_owner', 'agency_admin'].includes(user?.role || '');

  if (!canManageApiKeys) {
    return (
      <Box p={3}>
        <Alert severity="error">
          <Typography>Access Denied: Only agency owners and administrators can manage API keys.</Typography>
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Agency API Keys
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage API keys for your agency's integrations
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
          Each model should have their own OnlyFans API key for proper isolation.
        </Typography>
      </Alert>

      {/* Provider Summary Cards */}
      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <Instagram sx={{ color: '#00AFF0' }} />
                <Typography variant="h6">OnlyFans</Typography>
              </Box>
              <Typography variant="h3">{keys.filter(k => k.provider === 'onlyfans').length}</Typography>
              <Typography variant="body2" color="text.secondary">
                {models.length} models connected
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <CreditCard sx={{ color: '#635BFF' }} />
                <Typography variant="h6">Stripe</Typography>
              </Box>
              <Typography variant="h3">{keys.filter(k => k.provider === 'stripe').length}</Typography>
              <Typography variant="body2" color="text.secondary">Payment processing</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <Analytics sx={{ color: '#4F46E5' }} />
                <Typography variant="h6">Inflow</Typography>
              </Box>
              <Typography variant="h3">{keys.filter(k => k.provider === 'inflow').length}</Typography>
              <Typography variant="body2" color="text.secondary">Analytics platform</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <AccessTime color="action" />
                <Typography variant="h6">Total Usage</Typography>
              </Box>
              <Typography variant="h3">{keys.reduce((sum, k) => sum + k.usage, 0).toLocaleString()}</Typography>
              <Typography variant="body2" color="text.secondary">API requests</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* API Keys Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>API Key</TableCell>
              <TableCell>Provider</TableCell>
              <TableCell>Model</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
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
                    <Box display="flex" gap={0.5} mt={0.5} flexWrap="wrap">
                      {apiKey.scopes.slice(0, 3).map((scope) => (
                        <Chip 
                          key={scope}
                          label={scope}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                      {apiKey.scopes.length > 3 && (
                        <Chip 
                          label={`+${apiKey.scopes.length - 3} more`}
                          size="small"
                          variant="outlined"
                        />
                      )}
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
                  <Box display="flex" alignItems="center" gap={1}>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 32,
                        height: 32,
                        borderRadius: 1,
                        backgroundColor: getProviderColor(apiKey.provider) + '20',
                        color: getProviderColor(apiKey.provider),
                      }}
                    >
                      {getProviderIcon(apiKey.provider)}
                    </Box>
                    <Typography variant="body2">
                      {apiKey.provider.charAt(0).toUpperCase() + apiKey.provider.slice(1)}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  {apiKey.modelName ? (
                    <Typography variant="body2">{apiKey.modelName}</Typography>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Agency-wide
                    </Typography>
                  )}
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
                  <Box>
                    <Typography variant="body2">
                      {apiKey.usage.toLocaleString()} requests
                    </Typography>
                    {apiKey.lastUsed && (
                      <Typography variant="caption" color="text.secondary" display="block">
                        Last: {format(apiKey.lastUsed, 'MMM d')}
                      </Typography>
                    )}
                  </Box>
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
                placeholder="e.g., OnlyFans - Model Name"
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
                  <MenuItem value="onlyfans">OnlyFans</MenuItem>
                  <MenuItem value="stripe">Stripe</MenuItem>
                  <MenuItem value="inflow">Inflow</MenuItem>
                  <MenuItem value="custom">Custom</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            {formData.provider === 'onlyfans' && (
              <Grid item xs={12}>
                <FormControl fullWidth>
                  <InputLabel>Model</InputLabel>
                  <Select
                    value={formData.modelId}
                    label="Model"
                    onChange={(e) => setFormData({ ...formData, modelId: e.target.value })}
                  >
                    <MenuItem value="">Agency-wide</MenuItem>
                    {models.map((model) => (
                      <MenuItem key={model.id} value={model.id}>
                        {model.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Grid>
            )}
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
              <FormGroup>
                {getScopesByProvider(formData.provider).map((scope) => (
                  <FormControlLabel
                    key={scope}
                    control={
                      <Checkbox
                        checked={formData.scopes[scope as keyof typeof formData.scopes] || false}
                        onChange={(e) => setFormData({
                          ...formData,
                          scopes: { ...formData.scopes, [scope]: e.target.checked }
                        })}
                      />
                    }
                    label={scope.replace('.', ' ').replace(/_/g, ' ').charAt(0).toUpperCase() + scope.slice(1)}
                  />
                ))}
              </FormGroup>
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

export default AgencyApiKeysPage;