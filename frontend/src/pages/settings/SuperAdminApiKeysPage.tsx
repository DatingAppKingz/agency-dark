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
  Grid,
  Snackbar,
  Card,
  CardContent,
} from '@mui/material';
import {
  Add,
  ContentCopy,
  Delete,
  Edit,
  Key,
  Visibility,
  VisibilityOff,
  Warning,
  CheckCircle,
  Cancel,
  Security,
  Email,
  Payment,
  Storage,
  CloudQueue,
  Analytics,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useAuth } from '@/hooks/useAuth';

interface PlatformApiKey {
  id: string;
  name: string;
  key: string;
  service: 'email' | 'payment' | 'storage' | 'analytics' | 'sms' | 'monitoring';
  created: Date;
  lastUsed: Date | null;
  status: 'active' | 'inactive';
  description: string;
}

const SuperAdminApiKeysPage = () => {
  const { user } = useAuth();
  const [keys, setKeys] = useState<PlatformApiKey[]>([
    {
      id: '1',
      name: 'SendGrid Email Service',
      key: 'SG.4eC39HqLyjWDarjtT1zdp7dc',
      service: 'email',
      created: new Date('2024-01-01'),
      lastUsed: new Date('2024-03-20'),
      status: 'active',
      description: 'Platform-wide email notifications and transactional emails',
    },
    {
      id: '2',
      name: 'Stripe Platform Account',
      key: 'sk_live_platform_8xK2mNpLqRsTuVwXyZ',
      service: 'payment',
      created: new Date('2024-01-01'),
      lastUsed: new Date('2024-03-20'),
      status: 'active',
      description: 'Master Stripe account for platform fees and payouts',
    },
    {
      id: '3',
      name: 'AWS S3 Storage',
      key: 'AKIAIOSFODNN7EXAMPLE',
      service: 'storage',
      created: new Date('2024-01-05'),
      lastUsed: new Date('2024-03-19'),
      status: 'active',
      description: 'Media storage for all agencies',
    },
    {
      id: '4',
      name: 'Mixpanel Analytics',
      key: 'mp_prod_9bC4dEfGhIjKlMnOpQ',
      service: 'analytics',
      created: new Date('2024-02-01'),
      lastUsed: null,
      status: 'inactive',
      description: 'Platform usage analytics and metrics',
    },
  ]);

  const [showKey, setShowKey] = useState<{ [key: string]: boolean }>({});
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' as any });

  const [formData, setFormData] = useState({
    name: '',
    service: 'email' as any,
    key: '',
    description: '',
  });

  const handleCreateKey = () => {
    const newKey: PlatformApiKey = {
      id: Date.now().toString(),
      name: formData.name,
      key: formData.key,
      service: formData.service,
      created: new Date(),
      lastUsed: null,
      status: 'active',
      description: formData.description,
    };

    setKeys([...keys, newKey]);
    setCreateDialogOpen(false);
    setFormData({ name: '', service: 'email', key: '', description: '' });
    setSnackbar({ open: true, message: 'Platform API key added successfully', severity: 'success' });
  };

  const handleDeleteKey = (id: string) => {
    if (window.confirm('Are you sure you want to delete this platform API key? This may affect all agencies.')) {
      setKeys(keys.filter(k => k.id !== id));
      setSnackbar({ open: true, message: 'Platform API key deleted successfully', severity: 'success' });
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
    return key.substring(0, 8) + '...' + key.substring(key.length - 4);
  };

  const getServiceIcon = (service: string) => {
    switch (service) {
      case 'email':
        return <Email />;
      case 'payment':
        return <Payment />;
      case 'storage':
        return <Storage />;
      case 'analytics':
        return <Analytics />;
      case 'sms':
        return <CloudQueue />;
      default:
        return <Key />;
    }
  };

  const getServiceColor = (service: string) => {
    switch (service) {
      case 'email':
        return '#EA4335';
      case 'payment':
        return '#635BFF';
      case 'storage':
        return '#FF9900';
      case 'analytics':
        return '#4285F4';
      case 'sms':
        return '#25D366';
      default:
        return '#6B7280';
    }
  };

  if (user?.role !== 'super_admin') {
    return (
      <Box p={3}>
        <Alert severity="error">
          <Typography>Access Denied: This page is only accessible to super administrators.</Typography>
        </Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Platform API Keys
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage platform-wide API keys for core services
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => setCreateDialogOpen(true)}
        >
          Add Platform Key
        </Button>
      </Box>

      {/* Warning Alert */}
      <Alert 
        severity="error" 
        icon={<Warning />}
        sx={{ mb: 3 }}
      >
        <Typography variant="body2">
          <strong>Critical:</strong> These API keys affect the entire platform. 
          Changes here will impact all agencies and users. Handle with extreme care.
        </Typography>
      </Alert>

      {/* Service Summary Cards */}
      <Grid container spacing={2} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <Email color="error" />
                <Typography variant="h6">Email Service</Typography>
              </Box>
              <Typography variant="h3">{keys.filter(k => k.service === 'email' && k.status === 'active').length}</Typography>
              <Typography variant="body2" color="text.secondary">Active Keys</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <Payment color="primary" />
                <Typography variant="h6">Payment Gateway</Typography>
              </Box>
              <Typography variant="h3">{keys.filter(k => k.service === 'payment' && k.status === 'active').length}</Typography>
              <Typography variant="body2" color="text.secondary">Active Keys</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <Storage sx={{ color: '#FF9900' }} />
                <Typography variant="h6">Storage Service</Typography>
              </Box>
              <Typography variant="h3">{keys.filter(k => k.service === 'storage' && k.status === 'active').length}</Typography>
              <Typography variant="body2" color="text.secondary">Active Keys</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" gap={1} mb={1}>
                <Analytics color="info" />
                <Typography variant="h6">Analytics</Typography>
              </Box>
              <Typography variant="h3">{keys.filter(k => k.service === 'analytics' && k.status === 'active').length}</Typography>
              <Typography variant="body2" color="text.secondary">Active Keys</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* API Keys Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Service</TableCell>
              <TableCell>Name & Description</TableCell>
              <TableCell>API Key</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Last Used</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {keys.map((apiKey) => (
              <TableRow key={apiKey.id} hover>
                <TableCell>
                  <Box display="flex" alignItems="center" gap={1}>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 40,
                        height: 40,
                        borderRadius: 1,
                        backgroundColor: getServiceColor(apiKey.service) + '20',
                        color: getServiceColor(apiKey.service),
                      }}
                    >
                      {getServiceIcon(apiKey.service)}
                    </Box>
                    <Typography variant="body2" textTransform="capitalize">
                      {apiKey.service}
                    </Typography>
                  </Box>
                </TableCell>
                <TableCell>
                  <Box>
                    <Typography variant="subtitle2">{apiKey.name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {apiKey.description}
                    </Typography>
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
                    label={apiKey.status}
                    color={apiKey.status === 'active' ? 'success' : 'default'}
                    size="small"
                    icon={apiKey.status === 'active' ? <CheckCircle /> : <Cancel />}
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="body2">
                    {format(apiKey.created, 'MMM d, yyyy')}
                  </Typography>
                </TableCell>
                <TableCell>
                  {apiKey.lastUsed ? (
                    <Typography variant="body2">
                      {format(apiKey.lastUsed, 'MMM d, yyyy')}
                    </Typography>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      Never
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
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

      {/* Create Platform Key Dialog */}
      <Dialog 
        open={createDialogOpen} 
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Add Platform API Key</DialogTitle>
        <DialogContent>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Key Name"
                placeholder="e.g., SendGrid Production"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </Grid>
            <Grid item xs={12}>
              <FormControl fullWidth>
                <InputLabel>Service Type</InputLabel>
                <Select
                  value={formData.service}
                  label="Service Type"
                  onChange={(e) => setFormData({ ...formData, service: e.target.value as any })}
                >
                  <MenuItem value="email">Email Service</MenuItem>
                  <MenuItem value="payment">Payment Gateway</MenuItem>
                  <MenuItem value="storage">Storage Service</MenuItem>
                  <MenuItem value="analytics">Analytics Platform</MenuItem>
                  <MenuItem value="sms">SMS Service</MenuItem>
                  <MenuItem value="monitoring">Monitoring Service</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="API Key"
                placeholder="Enter the API key"
                value={formData.key}
                onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                type={showKey['new'] ? 'text' : 'password'}
                InputProps={{
                  endAdornment: (
                    <IconButton
                      size="small"
                      onClick={() => toggleKeyVisibility('new')}
                    >
                      {showKey['new'] ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth
                multiline
                rows={2}
                label="Description"
                placeholder="What is this key used for?"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleCreateKey} 
            variant="contained"
            disabled={!formData.name || !formData.key}
          >
            Add Key
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

export default SuperAdminApiKeysPage;