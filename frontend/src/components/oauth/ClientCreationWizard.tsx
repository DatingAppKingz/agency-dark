import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Stepper,
  Step,
  StepLabel,
  Box,
  TextField,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Checkbox,
  Typography,
  Alert,
  Chip,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  InputAdornment,
  Switch,
  Grid,
  Collapse,
  FormHelperText,
  Select,
  MenuItem,
  Divider,
  Card,
  CardContent,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Info as InfoIcon,
  Security as SecurityIcon,
  Link as LinkIcon,
  Key as KeyIcon,
  Settings as SettingsIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  ContentCopy as CopyIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import { useOAuthClients } from '../../hooks/useOAuthClients';
import { CodeBlock } from '../common/CodeBlock';

interface ClientCreationWizardProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (clientId: string) => void;
}

interface ClientFormData {
  // Basic Information
  name: string;
  description: string;
  type: 'confidential' | 'public';
  
  // Authentication
  tokenEndpointAuthMethod: string;
  requirePkce: boolean;
  
  // URLs
  redirectUris: string[];
  postLogoutRedirectUris: string[];
  allowedOrigins: string[];
  
  // Scopes & Grants
  allowedScopes: string[];
  grantTypes: string[];
  responseTypes: string[];
  
  // Token Settings
  accessTokenLifetime: number;
  refreshTokenLifetime: number;
  idTokenLifetime: number;
  rotateRefreshToken: boolean;
  
  // Security Settings
  requireConsent: boolean;
  skipConsentForFirstParty: boolean;
  allowWildcardRedirect: boolean;
  
  // Advanced
  enableRateLimiting: boolean;
  rateLimit: number;
  enableIpRestriction: boolean;
  ipWhitelist: string[];
}

const defaultFormData: ClientFormData = {
  name: '',
  description: '',
  type: 'confidential',
  tokenEndpointAuthMethod: 'client_secret_basic',
  requirePkce: true,
  redirectUris: [''],
  postLogoutRedirectUris: [],
  allowedOrigins: [],
  allowedScopes: ['openid', 'profile', 'email'],
  grantTypes: ['authorization_code'],
  responseTypes: ['code'],
  accessTokenLifetime: 3600,
  refreshTokenLifetime: 2592000,
  idTokenLifetime: 3600,
  rotateRefreshToken: true,
  requireConsent: true,
  skipConsentForFirstParty: false,
  allowWildcardRedirect: false,
  enableRateLimiting: true,
  rateLimit: 60,
  enableIpRestriction: false,
  ipWhitelist: [],
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

const steps = ['Basic Information', 'URLs & Redirects', 'Scopes & Permissions', 'Security Settings', 'Review & Create'];

export const ClientCreationWizard: React.FC<ClientCreationWizardProps> = ({
  open,
  onClose,
  onSuccess,
}) => {
  const { createClient } = useOAuthClients();
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<ClientFormData>(defaultFormData);
  const [errors, setErrors] = useState<Partial<Record<keyof ClientFormData, string>>>({});
  const [loading, setLoading] = useState(false);
  const [createdClient, setCreatedClient] = useState<any>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleNext = () => {
    if (validateStep(activeStep)) {
      setActiveStep((prev) => prev + 1);
    }
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  const handleReset = () => {
    setActiveStep(0);
    setFormData(defaultFormData);
    setErrors({});
    setCreatedClient(null);
  };

  const validateStep = (step: number): boolean => {
    const newErrors: Partial<Record<keyof ClientFormData, string>> = {};
    
    switch (step) {
      case 0: // Basic Information
        if (!formData.name) newErrors.name = 'Client name is required';
        if (formData.name.length < 3) newErrors.name = 'Client name must be at least 3 characters';
        break;
      
      case 1: // URLs & Redirects
        if (formData.redirectUris.filter(uri => uri).length === 0) {
          newErrors.redirectUris = 'At least one redirect URI is required';
        }
        formData.redirectUris.forEach((uri) => {
          if (uri && !isValidUrl(uri) && uri !== 'urn:ietf:wg:oauth:2.0:oob') {
            newErrors.redirectUris = 'Invalid URL format';
          }
        });
        break;
      
      case 2: // Scopes & Permissions
        if (formData.allowedScopes.length === 0) {
          newErrors.allowedScopes = 'At least one scope is required';
        }
        if (formData.grantTypes.length === 0) {
          newErrors.grantTypes = 'At least one grant type is required';
        }
        break;
    }
    
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

  const handleCreate = async () => {
    setLoading(true);
    try {
      const response = await createClient(formData);
      setCreatedClient(response);
      setActiveStep(steps.length);
    } catch (error) {
      console.error('Failed to create client:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const addRedirectUri = () => {
    setFormData({
      ...formData,
      redirectUris: [...formData.redirectUris, ''],
    });
  };

  const removeRedirectUri = (index: number) => {
    setFormData({
      ...formData,
      redirectUris: formData.redirectUris.filter((_, i) => i !== index),
    });
  };

  const updateRedirectUri = (index: number, value: string) => {
    const newUris = [...formData.redirectUris];
    newUris[index] = value;
    setFormData({ ...formData, redirectUris: newUris });
  };

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0: // Basic Information
        return (
          <Box sx={{ mt: 2 }}>
            <TextField
              fullWidth
              label="Client Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              error={!!errors.name}
              helperText={errors.name || 'A unique name for your OAuth client'}
              required
              sx={{ mb: 3 }}
            />

            <TextField
              fullWidth
              label="Description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              multiline
              rows={3}
              helperText="Describe the purpose of this client"
              sx={{ mb: 3 }}
            />

            <FormControl component="fieldset" sx={{ mb: 3 }}>
              <FormLabel component="legend">Client Type</FormLabel>
              <RadioGroup
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value as 'confidential' | 'public' })}
              >
                <FormControlLabel
                  value="confidential"
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography variant="body1">Confidential</Typography>
                      <Typography variant="caption" color="textSecondary">
                        Server-side applications that can securely store credentials
                      </Typography>
                    </Box>
                  }
                />
                <FormControlLabel
                  value="public"
                  control={<Radio />}
                  label={
                    <Box>
                      <Typography variant="body1">Public</Typography>
                      <Typography variant="caption" color="textSecondary">
                        Client-side apps (SPA, mobile) that cannot store secrets securely
                      </Typography>
                    </Box>
                  }
                />
              </RadioGroup>
            </FormControl>

            {formData.type === 'confidential' && (
              <FormControl fullWidth sx={{ mb: 3 }}>
                <FormLabel>Authentication Method</FormLabel>
                <Select
                  value={formData.tokenEndpointAuthMethod}
                  onChange={(e) => setFormData({ ...formData, tokenEndpointAuthMethod: e.target.value })}
                >
                  <MenuItem value="client_secret_basic">Client Secret Basic</MenuItem>
                  <MenuItem value="client_secret_post">Client Secret Post</MenuItem>
                  <MenuItem value="client_secret_jwt">Client Secret JWT</MenuItem>
                  <MenuItem value="private_key_jwt">Private Key JWT</MenuItem>
                  <MenuItem value="none">None</MenuItem>
                </Select>
                <FormHelperText>How the client authenticates with the token endpoint</FormHelperText>
              </FormControl>
            )}

            <FormControlLabel
              control={
                <Switch
                  checked={formData.requirePkce}
                  onChange={(e) => setFormData({ ...formData, requirePkce: e.target.checked })}
                />
              }
              label={
                <Box>
                  <Typography variant="body1">Require PKCE</Typography>
                  <Typography variant="caption" color="textSecondary">
                    Proof Key for Code Exchange adds additional security (recommended for all clients)
                  </Typography>
                </Box>
              }
            />
          </Box>
        );

      case 1: // URLs & Redirects
        return (
          <Box sx={{ mt: 2 }}>
            <Box sx={{ mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Typography variant="subtitle1">Redirect URIs</Typography>
                <Typography variant="caption" color="error" sx={{ ml: 1 }}>*Required</Typography>
              </Box>
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

            <Alert severity="info" sx={{ mb: 3 }}>
              <Typography variant="body2">
                For local development, you can use <code>http://localhost:PORT/callback</code>
              </Typography>
              <Typography variant="body2">
                For mobile apps, use <code>urn:ietf:wg:oauth:2.0:oob</code> or custom scheme URIs
              </Typography>
            </Alert>

            <FormControlLabel
              control={
                <Switch
                  checked={formData.allowWildcardRedirect}
                  onChange={(e) => setFormData({ ...formData, allowWildcardRedirect: e.target.checked })}
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
          </Box>
        );

      case 2: // Scopes & Permissions
        return (
          <Box sx={{ mt: 2 }}>
            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle1" gutterBottom>
                Allowed Scopes
              </Typography>
              <Typography variant="caption" color="textSecondary" display="block" sx={{ mb: 2 }}>
                Select the scopes this client can request
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
                              setFormData({
                                ...formData,
                                allowedScopes: [...formData.allowedScopes, scope.value],
                              });
                            } else {
                              setFormData({
                                ...formData,
                                allowedScopes: formData.allowedScopes.filter(s => s !== scope.value),
                              });
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
              
              {errors.allowedScopes && (
                <Typography variant="caption" color="error" display="block" sx={{ mt: 1 }}>
                  {errors.allowedScopes}
                </Typography>
              )}
            </Box>

            <Divider sx={{ my: 3 }} />

            <Box sx={{ mb: 3 }}>
              <Typography variant="subtitle1" gutterBottom>
                Grant Types
              </Typography>
              <Typography variant="caption" color="textSecondary" display="block" sx={{ mb: 2 }}>
                OAuth 2.0 flows this client can use
              </Typography>
              
              {grantTypesOptions.map((grant) => (
                <FormControlLabel
                  key={grant.value}
                  control={
                    <Checkbox
                      checked={formData.grantTypes.includes(grant.value)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setFormData({
                            ...formData,
                            grantTypes: [...formData.grantTypes, grant.value],
                          });
                        } else {
                          setFormData({
                            ...formData,
                            grantTypes: formData.grantTypes.filter(g => g !== grant.value),
                          });
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
          </Box>
        );

      case 3: // Security Settings
        return (
          <Box sx={{ mt: 2 }}>
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
                      onChange={(e) => setFormData({ ...formData, accessTokenLifetime: parseInt(e.target.value) })}
                      InputProps={{
                        endAdornment: <InputAdornment position="end">seconds</InputAdornment>,
                      }}
                      helperText="Default: 3600 (1 hour)"
                    />
                  </Grid>
                  
                  <Grid item xs={12} sm={4}>
                    <TextField
                      fullWidth
                      type="number"
                      label="Refresh Token Lifetime"
                      value={formData.refreshTokenLifetime}
                      onChange={(e) => setFormData({ ...formData, refreshTokenLifetime: parseInt(e.target.value) })}
                      InputProps={{
                        endAdornment: <InputAdornment position="end">seconds</InputAdornment>,
                      }}
                      helperText="Default: 2592000 (30 days)"
                    />
                  </Grid>
                  
                  <Grid item xs={12} sm={4}>
                    <TextField
                      fullWidth
                      type="number"
                      label="ID Token Lifetime"
                      value={formData.idTokenLifetime}
                      onChange={(e) => setFormData({ ...formData, idTokenLifetime: parseInt(e.target.value) })}
                      InputProps={{
                        endAdornment: <InputAdornment position="end">seconds</InputAdornment>,
                      }}
                      helperText="Default: 3600 (1 hour)"
                    />
                  </Grid>
                </Grid>
                
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.rotateRefreshToken}
                      onChange={(e) => setFormData({ ...formData, rotateRefreshToken: e.target.checked })}
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
                      onChange={(e) => setFormData({ ...formData, requireConsent: e.target.checked })}
                    />
                  }
                  label={
                    <Box>
                      <Typography variant="body1">Require User Consent</Typography>
                      <Typography variant="caption" color="textSecondary">
                        Users must explicitly approve access to their data
                      </Typography>
                    </Box>
                  }
                />
                
                {formData.requireConsent && (
                  <FormControlLabel
                    control={
                      <Switch
                        checked={formData.skipConsentForFirstParty}
                        onChange={(e) => setFormData({ ...formData, skipConsentForFirstParty: e.target.checked })}
                      />
                    }
                    label={
                      <Box>
                        <Typography variant="body1">Skip Consent for First-Party Apps</Typography>
                        <Typography variant="caption" color="textSecondary">
                          Auto-approve consent for trusted first-party applications
                        </Typography>
                      </Box>
                    }
                    sx={{ ml: 3, mt: 1 }}
                  />
                )}
              </CardContent>
            </Card>

            <Card variant="outlined">
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>
                  Rate Limiting
                </Typography>
                
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.enableRateLimiting}
                      onChange={(e) => setFormData({ ...formData, enableRateLimiting: e.target.checked })}
                    />
                  }
                  label="Enable rate limiting"
                />
                
                {formData.enableRateLimiting && (
                  <TextField
                    fullWidth
                    type="number"
                    label="Rate Limit"
                    value={formData.rateLimit}
                    onChange={(e) => setFormData({ ...formData, rateLimit: parseInt(e.target.value) })}
                    InputProps={{
                      endAdornment: <InputAdornment position="end">requests/minute</InputAdornment>,
                    }}
                    sx={{ mt: 2 }}
                  />
                )}
              </CardContent>
            </Card>
          </Box>
        );

      case 4: // Review & Create
        return (
          <Box sx={{ mt: 2 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              Review your client configuration before creating
            </Alert>

            <Grid container spacing={3}>
              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="textSecondary">Basic Information</Typography>
                    <Typography variant="body1" fontWeight="medium">{formData.name}</Typography>
                    {formData.description && (
                      <Typography variant="body2" color="textSecondary">{formData.description}</Typography>
                    )}
                    <Box sx={{ mt: 1 }}>
                      <Chip label={formData.type} size="small" color="primary" />
                      {formData.requirePkce && <Chip label="PKCE Required" size="small" sx={{ ml: 1 }} />}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                      Redirect URIs
                    </Typography>
                    {formData.redirectUris.filter(uri => uri).map((uri, index) => (
                      <Typography key={index} variant="body2" fontFamily="monospace">
                        {uri}
                      </Typography>
                    ))}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                      Allowed Scopes
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {formData.allowedScopes.map((scope) => (
                        <Chip key={scope} label={scope} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                      Grant Types
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {formData.grantTypes.map((grant) => (
                        <Chip key={grant} label={grant} size="small" variant="outlined" />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={12} md={6}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" color="textSecondary" gutterBottom>
                      Security Settings
                    </Typography>
                    <List dense>
                      <ListItem disableGutters>
                        <ListItemText 
                          primary="User Consent"
                          secondary={formData.requireConsent ? 'Required' : 'Not required'}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText 
                          primary="Rate Limiting"
                          secondary={formData.enableRateLimiting ? `${formData.rateLimit} req/min` : 'Disabled'}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText 
                          primary="Token Rotation"
                          secondary={formData.rotateRefreshToken ? 'Enabled' : 'Disabled'}
                        />
                      </ListItem>
                    </List>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        );

      default:
        return null;
    }
  };

  const renderSuccess = () => (
    <Box sx={{ mt: 2 }}>
      <Box sx={{ textAlign: 'center', mb: 3 }}>
        <CheckCircleIcon sx={{ fontSize: 64, color: 'success.main' }} />
        <Typography variant="h5" sx={{ mt: 2 }}>
          Client Created Successfully!
        </Typography>
        <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
          Your OAuth client has been created. Save the credentials below.
        </Typography>
      </Box>

      <Alert severity="warning" sx={{ mb: 3 }}>
        <Typography variant="body2">
          Save these credentials now. The client secret will not be shown again!
        </Typography>
      </Alert>

      <Card variant="outlined" sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" color="textSecondary">
              Client ID
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
              <TextField
                fullWidth
                value={createdClient?.clientId || ''}
                InputProps={{
                  readOnly: true,
                  sx: { fontFamily: 'monospace' },
                }}
              />
              <IconButton
                onClick={() => handleCopy(createdClient?.clientId || '', 'clientId')}
              >
                <CopyIcon />
              </IconButton>
              {copiedField === 'clientId' && (
                <Typography variant="caption" color="success.main">
                  Copied!
                </Typography>
              )}
            </Box>
          </Box>

          {createdClient?.clientSecret && (
            <Box>
              <Typography variant="subtitle2" color="textSecondary">
                Client Secret
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                <TextField
                  fullWidth
                  type={showSecret ? 'text' : 'password'}
                  value={createdClient.clientSecret}
                  InputProps={{
                    readOnly: true,
                    sx: { fontFamily: 'monospace' },
                    endAdornment: (
                      <InputAdornment position="end">
                        <IconButton
                          onClick={() => setShowSecret(!showSecret)}
                          edge="end"
                        >
                          {showSecret ? <VisibilityOffIcon /> : <VisibilityIcon />}
                        </IconButton>
                      </InputAdornment>
                    ),
                  }}
                />
                <IconButton
                  onClick={() => handleCopy(createdClient.clientSecret, 'clientSecret')}
                >
                  <CopyIcon />
                </IconButton>
                {copiedField === 'clientSecret' && (
                  <Typography variant="caption" color="success.main">
                    Copied!
                  </Typography>
                )}
              </Box>
            </Box>
          )}
        </CardContent>
      </Card>

      <Typography variant="subtitle2" gutterBottom>
        Quick Start Code
      </Typography>
      <CodeBlock
        language="javascript"
        code={`// OAuth Client Configuration
const config = {
  clientId: '${createdClient?.clientId || 'YOUR_CLIENT_ID'}',
  clientSecret: '${createdClient?.clientSecret || 'YOUR_CLIENT_SECRET'}', // Keep secure!
  authorizationUrl: '${window.location.origin}/oauth/authorize',
  tokenUrl: '${window.location.origin}/oauth/token',
  redirectUri: '${formData.redirectUris[0] || 'YOUR_REDIRECT_URI'}',
  scopes: ${JSON.stringify(formData.allowedScopes.slice(0, 3))},
  usePKCE: ${formData.requirePkce}
};

// Example: Initiate OAuth flow
const params = new URLSearchParams({
  client_id: config.clientId,
  redirect_uri: config.redirectUri,
  response_type: 'code',
  scope: config.scopes.join(' '),
  state: generateRandomState()
});

${formData.requirePkce ? `// Add PKCE challenge
params.append('code_challenge', codeChallenge);
params.append('code_challenge_method', 'S256');

` : ''}window.location.href = \`\${config.authorizationUrl}?\${params}\`;`}
      />
    </Box>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
      fullWidth
      disableEscapeKeyDown={loading}
    >
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <SecurityIcon />
          <Typography variant="h6">Create OAuth Client</Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        {activeStep < steps.length ? (
          <>
            <Stepper activeStep={activeStep} sx={{ mb: 3 }}>
              {steps.map((label) => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
            {renderStepContent(activeStep)}
          </>
        ) : (
          renderSuccess()
        )}
      </DialogContent>

      <DialogActions>
        {activeStep < steps.length ? (
          <>
            <Button onClick={onClose} disabled={loading}>
              Cancel
            </Button>
            <Box sx={{ flex: '1 1 auto' }} />
            <Button
              disabled={activeStep === 0}
              onClick={handleBack}
            >
              Back
            </Button>
            {activeStep === steps.length - 1 ? (
              <Button
                variant="contained"
                onClick={handleCreate}
                disabled={loading}
                startIcon={loading ? null : <CheckCircleIcon />}
              >
                {loading ? 'Creating...' : 'Create Client'}
              </Button>
            ) : (
              <Button
                variant="contained"
                onClick={handleNext}
              >
                Next
              </Button>
            )}
          </>
        ) : (
          <>
            <Button onClick={handleReset} startIcon={<AddIcon />}>
              Create Another
            </Button>
            <Box sx={{ flex: '1 1 auto' }} />
            <Button
              variant="contained"
              onClick={() => {
                onSuccess(createdClient?.clientId || '');
                onClose();
              }}
            >
              Done
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
};