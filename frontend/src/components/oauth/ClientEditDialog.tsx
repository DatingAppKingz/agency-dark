import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  FormLabel,
  FormControlLabel,
  Switch,
  Select,
  MenuItem,
  Box,
  Typography,
  Alert,
  Chip,
  IconButton,
  InputAdornment,
  Grid,
  Card,
  CardContent,
  Divider,
  List,
  ListItem,
  ListItemText,
  Checkbox,
  FormHelperText,
  Tabs,
  Tab,
} from '@mui/material';
import {
  Save as SaveIcon,
  Cancel as CancelIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Link as LinkIcon,
  Security as SecurityIcon,
  Warning as WarningIcon,
  RestartAlt as RestartIcon,
} from '@mui/icons-material';
import { OAuthClient } from '../../types/oauth';
import { useOAuthClients } from '../../hooks/useOAuthClients';

interface ClientEditDialogProps {
  client: OAuthClient;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`edit-tabpanel-${index}`}
      aria-labelledby={`edit-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

const availableScopes = [
  { value: 'openid', label: 'OpenID', description: 'User identity verification' },
  { value: 'profile', label: 'Profile', description: 'Basic profile information' },
  { value: 'email', label: 'Email', description: 'Email address access' },
  { value: 'phone', label: 'Phone', description: 'Phone number access' },
  { value: 'address', label: 'Address', description: 'Physical address access' },
  { value: 'offline_access', label: 'Offline Access', description: 'Refresh token access' },
  { value: 'api:read', label: 'API Read', description: 'Read access to API resources' },
  { value: 'api:write', label: 'API Write', description: 'Write access to API resources' },
  { value: 'api:delete', label: 'API Delete', description: 'Delete access to API resources' },
];

const grantTypesOptions = [
  { value: 'authorization_code', label: 'Authorization Code', recommended: true },
  { value: 'implicit', label: 'Implicit', deprecated: true },
  { value: 'client_credentials', label: 'Client Credentials' },
  { value: 'password', label: 'Resource Owner Password', deprecated: true },
  { value: 'refresh_token', label: 'Refresh Token' },
  { value: 'urn:ietf:params:oauth:grant-type:device_code', label: 'Device Code' },
];

export const ClientEditDialog: React.FC<ClientEditDialogProps> = ({
  client,
  open,
  onClose,
  onSuccess,
}) => {
  const { updateClient } = useOAuthClients();
  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [showResetWarning, setShowResetWarning] = useState(false);
  
  const [formData, setFormData] = useState({
    name: client.name,
    description: client.description || '',
    status: client.status,
    redirectUris: client.redirectUris,
    postLogoutRedirectUris: client.postLogoutRedirectUris || [],
    allowedOrigins: client.allowedOrigins || [],
    allowedScopes: client.allowedScopes,
    grantTypes: client.grantTypes,
    responseTypes: client.responseTypes,
    tokenEndpointAuthMethod: client.tokenEndpointAuthMethod || 'client_secret_basic',
    requirePkce: client.requirePkce,
    requireConsent: client.requireConsent,
    skipConsentForFirstParty: client.skipConsentForFirstParty || false,
    allowWildcardRedirect: client.allowWildcardRedirect || false,
    accessTokenLifetime: client.accessTokenLifetime || 3600,
    refreshTokenLifetime: client.refreshTokenLifetime || 2592000,
    idTokenLifetime: client.idTokenLifetime || 3600,
    rotateRefreshToken: client.rotateRefreshToken || true,
    rateLimits: client.rateLimits || {
      token: 60,
      introspect: 300,
      revoke: 60,
    },
    ipWhitelist: client.restrictions?.ipWhitelist || [],
    userWhitelist: client.restrictions?.userWhitelist || [],
  });

  useEffect(() => {
    // Reset form when client changes
    setFormData({
      name: client.name,
      description: client.description || '',
      status: client.status,
      redirectUris: client.redirectUris,
      postLogoutRedirectUris: client.postLogoutRedirectUris || [],
      allowedOrigins: client.allowedOrigins || [],
      allowedScopes: client.allowedScopes,
      grantTypes: client.grantTypes,
      responseTypes: client.responseTypes,
      tokenEndpointAuthMethod: client.tokenEndpointAuthMethod || 'client_secret_basic',
      requirePkce: client.requirePkce,
      requireConsent: client.requireConsent,
      skipConsentForFirstParty: client.skipConsentForFirstParty || false,
      allowWildcardRedirect: client.allowWildcardRedirect || false,
      accessTokenLifetime: client.accessTokenLifetime || 3600,
      refreshTokenLifetime: client.refreshTokenLifetime || 2592000,
      idTokenLifetime: client.idTokenLifetime || 3600,
      rotateRefreshToken: client.rotateRefreshToken || true,
      rateLimits: client.rateLimits || {
        token: 60,
        introspect: 300,
        revoke: 60,
      },
      ipWhitelist: client.restrictions?.ipWhitelist || [],
      userWhitelist: client.restrictions?.userWhitelist || [],
    });
    setHasChanges(false);
    setErrors({});
  }, [client]);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleFieldChange = (field: string, value: any) => {
    setFormData({ ...formData, [field]: value });
    setHasChanges(true);
  };

  const addRedirectUri = () => {
    handleFieldChange('redirectUris', [...formData.redirectUris, '']);
  };

  const removeRedirectUri = (index: number) => {
    handleFieldChange(
      'redirectUris',
      formData.redirectUris.filter((_, i) => i !== index)
    );
  };

  const updateRedirectUri = (index: number, value: string) => {
    const newUris = [...formData.redirectUris];
    newUris[index] = value;
    handleFieldChange('redirectUris', newUris);
  };

  const addIpWhitelist = () => {
    handleFieldChange('ipWhitelist', [...formData.ipWhitelist, '']);
  };

  const removeIpWhitelist = (index: number) => {
    handleFieldChange(
      'ipWhitelist',
      formData.ipWhitelist.filter((_, i) => i !== index)
    );
  };

  const updateIpWhitelist = (index: number, value: string) => {
    const newIps = [...formData.ipWhitelist];
    newIps[index] = value;
    handleFieldChange('ipWhitelist', newIps);
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name || formData.name.length < 3) {
      newErrors.name = 'Client name must be at least 3 characters';
    }

    if (formData.redirectUris.filter(uri => uri).length === 0) {
      newErrors.redirectUris = 'At least one redirect URI is required';
    }

    formData.redirectUris.forEach((uri) => {
      if (uri && !isValidUrl(uri) && uri !== 'urn:ietf:wg:oauth:2.0:oob') {
        newErrors.redirectUris = 'Invalid URL format';
      }
    });

    if (formData.allowedScopes.length === 0) {
      newErrors.scopes = 'At least one scope is required';
    }

    if (formData.grantTypes.length === 0) {
      newErrors.grantTypes = 'At least one grant type is required';
    }

    formData.ipWhitelist.forEach((ip) => {
      if (ip && !isValidIp(ip)) {
        newErrors.ipWhitelist = 'Invalid IP address format';
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const isValidUrl = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  const isValidIp = (ip: string): boolean => {
    const ipv4Regex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
    const ipv6Regex = /^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}(\/\d{1,3})?$/;
    return ipv4Regex.test(ip) || ipv6Regex.test(ip);
  };

  const handleSave = async () => {
    if (!validateForm()) {
      return;
    }

    setLoading(true);
    try {
      await updateClient(client.id, {
        ...formData,
        restrictions: {
          ipWhitelist: formData.ipWhitelist.filter(ip => ip),
          userWhitelist: formData.userWhitelist,
        },
      });
      onSuccess();
      onClose();
    } catch (error) {
      console.error('Failed to update client:', error);
      setErrors({ general: 'Failed to update client. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setFormData({
      name: client.name,
      description: client.description || '',
      status: client.status,
      redirectUris: client.redirectUris,
      postLogoutRedirectUris: client.postLogoutRedirectUris || [],
      allowedOrigins: client.allowedOrigins || [],
      allowedScopes: client.allowedScopes,
      grantTypes: client.grantTypes,
      responseTypes: client.responseTypes,
      tokenEndpointAuthMethod: client.tokenEndpointAuthMethod || 'client_secret_basic',
      requirePkce: client.requirePkce,
      requireConsent: client.requireConsent,
      skipConsentForFirstParty: client.skipConsentForFirstParty || false,
      allowWildcardRedirect: client.allowWildcardRedirect || false,
      accessTokenLifetime: client.accessTokenLifetime || 3600,
      refreshTokenLifetime: client.refreshTokenLifetime || 2592000,
      idTokenLifetime: client.idTokenLifetime || 3600,
      rotateRefreshToken: client.rotateRefreshToken || true,
      rateLimits: client.rateLimits || {
        token: 60,
        introspect: 300,
        revoke: 60,
      },
      ipWhitelist: client.restrictions?.ipWhitelist || [],
      userWhitelist: client.restrictions?.userWhitelist || [],
    });
    setHasChanges(false);
    setErrors({});
    setShowResetWarning(false);
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      disableEscapeKeyDown={loading}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SecurityIcon />
            <Typography variant="h6">Edit OAuth Client</Typography>
            {hasChanges && (
              <Chip label="Unsaved Changes" size="small" color="warning" />
            )}
          </Box>
          <Typography variant="caption" color="textSecondary">
            Client ID: {client.clientId}
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        {errors.general && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {errors.general}
          </Alert>
        )}

        <Tabs value={activeTab} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Basic" />
          <Tab label="URLs" />
          <Tab label="Permissions" />
          <Tab label="Security" />
          <Tab label="Advanced" />
        </Tabs>

        {/* Basic Tab */}
        <TabPanel value={activeTab} index={0}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Client Name"
                value={formData.name}
                onChange={(e) => handleFieldChange('name', e.target.value)}
                error={!!errors.name}
                helperText={errors.name}
                required
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Description"
                value={formData.description}
                onChange={(e) => handleFieldChange('description', e.target.value)}
                multiline
                rows={3}
                helperText="Describe the purpose of this client"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth>
                <FormLabel>Status</FormLabel>
                <Select
                  value={formData.status}
                  onChange={(e) => handleFieldChange('status', e.target.value)}
                >
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="suspended">Suspended</MenuItem>
                  <MenuItem value="pending">Pending</MenuItem>
                </Select>
              </FormControl>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControl fullWidth disabled>
                <FormLabel>Client Type</FormLabel>
                <Select value={client.type}>
                  <MenuItem value="confidential">Confidential</MenuItem>
                  <MenuItem value="public">Public</MenuItem>
                </Select>
                <FormHelperText>Client type cannot be changed</FormHelperText>
              </FormControl>
            </Grid>

            {client.type === 'confidential' && (
              <Grid item xs={12}>
                <FormControl fullWidth>
                  <FormLabel>Authentication Method</FormLabel>
                  <Select
                    value={formData.tokenEndpointAuthMethod}
                    onChange={(e) => handleFieldChange('tokenEndpointAuthMethod', e.target.value)}
                  >
                    <MenuItem value="client_secret_basic">Client Secret Basic</MenuItem>
                    <MenuItem value="client_secret_post">Client Secret Post</MenuItem>
                    <MenuItem value="client_secret_jwt">Client Secret JWT</MenuItem>
                    <MenuItem value="private_key_jwt">Private Key JWT</MenuItem>
                    <MenuItem value="none">None</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
            )}
          </Grid>
        </TabPanel>

        {/* URLs Tab */}
        <TabPanel value={activeTab} index={1}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>
              Redirect URIs
            </Typography>
            <Typography variant="caption" color="textSecondary" display="block" sx={{ mb: 2 }}>
              URLs where users will be redirected after authorization
            </Typography>
            
            {formData.redirectUris.map((uri, index) => (
              <Box key={index} sx={{ display: 'flex', mb: 1 }}>
                <TextField
                  fullWidth
                  value={uri}
                  onChange={(e) => updateRedirectUri(index, e.target.value)}
                  placeholder="https://your-app.com/callback"
                  error={!!errors.redirectUris && !!uri && !isValidUrl(uri)}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <LinkIcon />
                      </InputAdornment>
                    ),
                  }}
                />
                <IconButton
                  onClick={() => removeRedirectUri(index)}
                  disabled={formData.redirectUris.length === 1}
                  sx={{ ml: 1 }}
                >
                  <DeleteIcon />
                </IconButton>
              </Box>
            ))}
            
            <Button
              startIcon={<AddIcon />}
              onClick={addRedirectUri}
              size="small"
              sx={{ mt: 1 }}
            >
              Add Redirect URI
            </Button>
            
            {errors.redirectUris && (
              <Typography variant="caption" color="error" display="block" sx={{ mt: 1 }}>
                {errors.redirectUris}
              </Typography>
            )}
          </Box>

          <FormControlLabel
            control={
              <Switch
                checked={formData.allowWildcardRedirect}
                onChange={(e) => handleFieldChange('allowWildcardRedirect', e.target.checked)}
              />
            }
            label={
              <Box>
                <Typography variant="body1">Allow Wildcard Redirects</Typography>
                <Typography variant="caption" color="textSecondary">
                  Allow pattern matching in redirect URIs (less secure)
                </Typography>
              </Box>
            }
          />
        </TabPanel>

        {/* Permissions Tab */}
        <TabPanel value={activeTab} index={2}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle1" gutterBottom>
              Allowed Scopes
            </Typography>
            <Grid container spacing={1}>
              {availableScopes.map((scope) => (
                <Grid item xs={12} sm={6} key={scope.value}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={formData.allowedScopes.includes(scope.value)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            handleFieldChange('allowedScopes', [...formData.allowedScopes, scope.value]);
                          } else {
                            handleFieldChange(
                              'allowedScopes',
                              formData.allowedScopes.filter(s => s !== scope.value)
                            );
                          }
                        }}
                      />
                    }
                    label={
                      <Box>
                        <Typography variant="body2">{scope.label}</Typography>
                        <Typography variant="caption" color="textSecondary">
                          {scope.description}
                        </Typography>
                      </Box>
                    }
                  />
                </Grid>
              ))}
            </Grid>
            {errors.scopes && (
              <Typography variant="caption" color="error" display="block" sx={{ mt: 1 }}>
                {errors.scopes}
              </Typography>
            )}
          </Box>

          <Divider sx={{ my: 3 }} />

          <Box>
            <Typography variant="subtitle1" gutterBottom>
              Grant Types
            </Typography>
            {grantTypesOptions.map((grant) => (
              <FormControlLabel
                key={grant.value}
                control={
                  <Checkbox
                    checked={formData.grantTypes.includes(grant.value)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        handleFieldChange('grantTypes', [...formData.grantTypes, grant.value]);
                      } else {
                        handleFieldChange(
                          'grantTypes',
                          formData.grantTypes.filter(g => g !== grant.value)
                        );
                      }
                    }}
                  />
                }
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <Typography variant="body2">{grant.label}</Typography>
                    {grant.recommended && (
                      <Chip label="Recommended" size="small" color="success" sx={{ ml: 1 }} />
                    )}
                    {grant.deprecated && (
                      <Chip label="Deprecated" size="small" color="warning" sx={{ ml: 1 }} />
                    )}
                  </Box>
                }
              />
            ))}
            {errors.grantTypes && (
              <Typography variant="caption" color="error" display="block" sx={{ mt: 1 }}>
                {errors.grantTypes}
              </Typography>
            )}
          </Box>
        </TabPanel>

        {/* Security Tab */}
        <TabPanel value={activeTab} index={3}>
          <Card variant="outlined" sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Token Configuration
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Access Token Lifetime"
                    value={formData.accessTokenLifetime}
                    onChange={(e) => handleFieldChange('accessTokenLifetime', parseInt(e.target.value))}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">seconds</InputAdornment>,
                    }}
                  />
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Refresh Token Lifetime"
                    value={formData.refreshTokenLifetime}
                    onChange={(e) => handleFieldChange('refreshTokenLifetime', parseInt(e.target.value))}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">seconds</InputAdornment>,
                    }}
                  />
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="ID Token Lifetime"
                    value={formData.idTokenLifetime}
                    onChange={(e) => handleFieldChange('idTokenLifetime', parseInt(e.target.value))}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">seconds</InputAdornment>,
                    }}
                  />
                </Grid>
              </Grid>
              
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.rotateRefreshToken}
                    onChange={(e) => handleFieldChange('rotateRefreshToken', e.target.checked)}
                  />
                }
                label="Rotate refresh tokens on use"
                sx={{ mt: 2 }}
              />
            </CardContent>
          </Card>

          <Card variant="outlined" sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Consent Settings
              </Typography>
              
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.requireConsent}
                    onChange={(e) => handleFieldChange('requireConsent', e.target.checked)}
                  />
                }
                label="Require User Consent"
              />
              
              {formData.requireConsent && (
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.skipConsentForFirstParty}
                      onChange={(e) => handleFieldChange('skipConsentForFirstParty', e.target.checked)}
                    />
                  }
                  label="Skip Consent for First-Party Apps"
                  sx={{ ml: 3, display: 'block' }}
                />
              )}
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <FormControlLabel
                control={
                  <Switch
                    checked={formData.requirePkce}
                    onChange={(e) => handleFieldChange('requirePkce', e.target.checked)}
                  />
                }
                label={
                  <Box>
                    <Typography variant="body1">Require PKCE</Typography>
                    <Typography variant="caption" color="textSecondary">
                      Proof Key for Code Exchange adds additional security
                    </Typography>
                  </Box>
                }
              />
            </CardContent>
          </Card>
        </TabPanel>

        {/* Advanced Tab */}
        <TabPanel value={activeTab} index={4}>
          <Card variant="outlined" sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Rate Limiting
              </Typography>
              
              <Grid container spacing={2}>
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Token Endpoint"
                    value={formData.rateLimits.token}
                    onChange={(e) => handleFieldChange('rateLimits', {
                      ...formData.rateLimits,
                      token: parseInt(e.target.value)
                    })}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">req/min</InputAdornment>,
                    }}
                  />
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Introspection Endpoint"
                    value={formData.rateLimits.introspect}
                    onChange={(e) => handleFieldChange('rateLimits', {
                      ...formData.rateLimits,
                      introspect: parseInt(e.target.value)
                    })}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">req/min</InputAdornment>,
                    }}
                  />
                </Grid>
                
                <Grid item xs={12} sm={4}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Revocation Endpoint"
                    value={formData.rateLimits.revoke}
                    onChange={(e) => handleFieldChange('rateLimits', {
                      ...formData.rateLimits,
                      revoke: parseInt(e.target.value)
                    })}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">req/min</InputAdornment>,
                    }}
                  />
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                IP Whitelist
              </Typography>
              <Typography variant="caption" color="textSecondary" display="block" sx={{ mb: 2 }}>
                Restrict access to specific IP addresses or ranges (optional)
              </Typography>
              
              {formData.ipWhitelist.map((ip, index) => (
                <Box key={index} sx={{ display: 'flex', mb: 1 }}>
                  <TextField
                    fullWidth
                    value={ip}
                    onChange={(e) => updateIpWhitelist(index, e.target.value)}
                    placeholder="192.168.1.1 or 192.168.1.0/24"
                    error={!!errors.ipWhitelist && !!ip && !isValidIp(ip)}
                  />
                  <IconButton
                    onClick={() => removeIpWhitelist(index)}
                    sx={{ ml: 1 }}
                  >
                    <DeleteIcon />
                  </IconButton>
                </Box>
              ))}
              
              {formData.ipWhitelist.length === 0 && (
                <Typography variant="body2" color="textSecondary" sx={{ mb: 1 }}>
                  No IP restrictions (accessible from any IP)
                </Typography>
              )}
              
              <Button
                startIcon={<AddIcon />}
                onClick={addIpWhitelist}
                size="small"
                sx={{ mt: 1 }}
              >
                Add IP Address
              </Button>
              
              {errors.ipWhitelist && (
                <Typography variant="caption" color="error" display="block" sx={{ mt: 1 }}>
                  {errors.ipWhitelist}
                </Typography>
              )}
            </CardContent>
          </Card>
        </TabPanel>

        {/* Reset Warning Dialog */}
        <Dialog open={showResetWarning} onClose={() => setShowResetWarning(false)}>
          <DialogTitle>Reset Changes?</DialogTitle>
          <DialogContent>
            <Alert severity="warning" sx={{ mb: 2 }}>
              <Typography variant="body2">
                This will discard all unsaved changes and restore the original values.
              </Typography>
            </Alert>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setShowResetWarning(false)}>Cancel</Button>
            <Button onClick={handleReset} color="warning" variant="contained">
              Reset Changes
            </Button>
          </DialogActions>
        </Dialog>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        {hasChanges && (
          <Button
            onClick={() => setShowResetWarning(true)}
            startIcon={<RestartIcon />}
            disabled={loading}
          >
            Reset
          </Button>
        )}
        <Box sx={{ flex: '1 1 auto' }} />
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={loading || !hasChanges}
          startIcon={loading ? null : <SaveIcon />}
        >
          {loading ? 'Saving...' : 'Save Changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};