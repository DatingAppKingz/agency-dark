import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Tabs,
  Tab,
  Box,
  Typography,
  Grid,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  TextField,
  Alert,
  Divider,
  Card,
  CardContent,
  Switch,
  FormControlLabel,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  ContentCopy as CopyIcon,
  Edit as EditIcon,
  VpnKey as KeyIcon,
  Security as SecurityIcon,
  AccessTime as AccessTimeIcon,
  Link as LinkIcon,
  VerifiedUser as VerifiedIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { OAuthClient, ClientScope, ClientRestriction } from '../../types/oauth';
import { CodeBlock } from '../common/CodeBlock';

interface ClientDetailsDialogProps {
  client: OAuthClient;
  open: boolean;
  onClose: () => void;
  onEdit: () => void;
  onRotateSecret: () => void;
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
      id={`client-tabpanel-${index}`}
      aria-labelledby={`client-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

export const ClientDetailsDialog: React.FC<ClientDetailsDialogProps> = ({
  client,
  open,
  onClose,
  onEdit,
  onRotateSecret,
}) => {
  const [activeTab, setActiveTab] = useState(0);
  const [showSecret, setShowSecret] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'suspended':
        return 'error';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SecurityIcon />
            <Typography variant="h6">{client.name}</Typography>
            <Chip
              label={client.status}
              size="small"
              color={getStatusColor(client.status)}
            />
          </Box>
          <Box>
            <IconButton onClick={onEdit} size="small">
              <EditIcon />
            </IconButton>
          </Box>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Tabs value={activeTab} onChange={handleTabChange} sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tab label="Overview" />
          <Tab label="Credentials" />
          <Tab label="Configuration" />
          <Tab label="Security" />
          <Tab label="Usage" />
        </Tabs>

        {/* Overview Tab */}
        <TabPanel value={activeTab} index={0}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="textSecondary">
                Client ID
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                <Typography variant="body1" fontFamily="monospace">
                  {client.clientId}
                </Typography>
                <IconButton
                  size="small"
                  onClick={() => handleCopy(client.clientId, 'clientId')}
                >
                  <CopyIcon fontSize="small" />
                </IconButton>
                {copiedField === 'clientId' && (
                  <Typography variant="caption" color="success.main">
                    Copied!
                  </Typography>
                )}
              </Box>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="textSecondary">
                Client Type
              </Typography>
              <Typography variant="body1" sx={{ mt: 1 }}>
                {client.type === 'confidential' ? 'Confidential' : 'Public'}
              </Typography>
              <Typography variant="caption" color="textSecondary">
                {client.type === 'confidential' 
                  ? 'Can securely store credentials'
                  : 'Cannot store credentials securely (SPA, mobile)'}
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="textSecondary">
                Created
              </Typography>
              <Typography variant="body1" sx={{ mt: 1 }}>
                {format(new Date(client.createdAt), 'PPpp')}
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" color="textSecondary">
                Last Used
              </Typography>
              <Typography variant="body1" sx={{ mt: 1 }}>
                {client.lastUsedAt 
                  ? format(new Date(client.lastUsedAt), 'PPpp')
                  : 'Never used'}
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Description
              </Typography>
              <Typography variant="body1" sx={{ mt: 1 }}>
                {client.description || 'No description provided'}
              </Typography>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Credentials Tab */}
        <TabPanel value={activeTab} index={1}>
          <Alert severity="warning" sx={{ mb: 3 }}>
            <Typography variant="body2">
              Keep your client credentials secure. Never expose them in client-side code or public repositories.
            </Typography>
          </Alert>

          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Client Secret
              </Typography>
              {client.type === 'confidential' ? (
                <Box sx={{ mt: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TextField
                      fullWidth
                      type={showSecret ? 'text' : 'password'}
                      value={client.clientSecret || '••••••••••••••••'}
                      InputProps={{
                        readOnly: true,
                        sx: { fontFamily: 'monospace' },
                      }}
                    />
                    <FormControlLabel
                      control={
                        <Switch
                          checked={showSecret}
                          onChange={(e) => setShowSecret(e.target.checked)}
                        />
                      }
                      label="Show"
                    />
                    <Button
                      variant="outlined"
                      startIcon={<KeyIcon />}
                      onClick={onRotateSecret}
                    >
                      Rotate
                    </Button>
                  </Box>
                  <Typography variant="caption" color="textSecondary">
                    Last rotated: {client.secretRotatedAt 
                      ? format(new Date(client.secretRotatedAt), 'PP')
                      : 'Never'}
                  </Typography>
                </Box>
              ) : (
                <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                  Public clients do not have a client secret
                </Typography>
              )}
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Authentication Method
              </Typography>
              <Typography variant="body1" sx={{ mt: 1 }}>
                {client.tokenEndpointAuthMethod || 'client_secret_basic'}
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                PKCE Required
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                {client.requirePkce ? (
                  <>
                    <VerifiedIcon color="success" fontSize="small" />
                    <Typography variant="body1">Yes (Required)</Typography>
                  </>
                ) : (
                  <>
                    <InfoIcon color="action" fontSize="small" />
                    <Typography variant="body1">No (Optional)</Typography>
                  </>
                )}
              </Box>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Configuration Tab */}
        <TabPanel value={activeTab} index={2}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Redirect URIs
              </Typography>
              <List dense sx={{ mt: 1, bgcolor: 'background.paper', borderRadius: 1 }}>
                {client.redirectUris.map((uri, index) => (
                  <ListItem key={index}>
                    <LinkIcon fontSize="small" sx={{ mr: 1 }} />
                    <ListItemText
                      primary={uri}
                      primaryTypographyProps={{ fontFamily: 'monospace', fontSize: '0.875rem' }}
                    />
                    <ListItemSecondaryAction>
                      <IconButton
                        edge="end"
                        size="small"
                        onClick={() => handleCopy(uri, `uri-${index}`)}
                      >
                        <CopyIcon fontSize="small" />
                      </IconButton>
                    </ListItemSecondaryAction>
                  </ListItem>
                ))}
              </List>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Allowed Scopes
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                {client.allowedScopes.map((scope) => (
                  <Chip
                    key={scope}
                    label={scope}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Grant Types
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                {client.grantTypes.map((grant) => (
                  <Chip
                    key={grant}
                    label={grant}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Response Types
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                {client.responseTypes.map((type) => (
                  <Chip
                    key={type}
                    label={type}
                    size="small"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Grid>
          </Grid>
        </TabPanel>

        {/* Security Tab */}
        <TabPanel value={activeTab} index={3}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Token Configuration
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="textSecondary">
                        Access Token Lifetime
                      </Typography>
                      <Typography variant="body1">
                        {client.accessTokenLifetime || 3600} seconds
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="textSecondary">
                        Refresh Token Lifetime
                      </Typography>
                      <Typography variant="body1">
                        {client.refreshTokenLifetime || 2592000} seconds
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="textSecondary">
                        ID Token Lifetime
                      </Typography>
                      <Typography variant="body1">
                        {client.idTokenLifetime || 3600} seconds
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Typography variant="body2" color="textSecondary">
                        Refresh Token Rotation
                      </Typography>
                      <Typography variant="body1">
                        {client.rotateRefreshToken ? 'Enabled' : 'Disabled'}
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Security Settings
                  </Typography>
                  <List dense>
                    <ListItem>
                      <ListItemText
                        primary="Require Consent"
                        secondary={client.requireConsent ? 'Users must approve access' : 'Auto-approve access'}
                      />
                      <Chip
                        label={client.requireConsent ? 'ON' : 'OFF'}
                        size="small"
                        color={client.requireConsent ? 'success' : 'default'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Skip Consent for First-Party"
                        secondary="Skip consent for trusted first-party apps"
                      />
                      <Chip
                        label={client.skipConsentForFirstParty ? 'ON' : 'OFF'}
                        size="small"
                        color={client.skipConsentForFirstParty ? 'success' : 'default'}
                      />
                    </ListItem>
                    <ListItem>
                      <ListItemText
                        primary="Allow Wildcard Redirects"
                        secondary="Allow wildcard patterns in redirect URIs"
                      />
                      <Chip
                        label={client.allowWildcardRedirect ? 'ON' : 'OFF'}
                        size="small"
                        color={client.allowWildcardRedirect ? 'warning' : 'success'}
                      />
                    </ListItem>
                  </List>
                </CardContent>
              </Card>
            </Grid>

            {client.restrictions && (
              <Grid item xs={12}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle1" gutterBottom>
                      Access Restrictions
                    </Typography>
                    {client.restrictions.ipWhitelist && (
                      <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" color="textSecondary">
                          IP Whitelist
                        </Typography>
                        <Typography variant="body2" fontFamily="monospace">
                          {client.restrictions.ipWhitelist.join(', ')}
                        </Typography>
                      </Box>
                    )}
                    {client.restrictions.userWhitelist && (
                      <Box>
                        <Typography variant="body2" color="textSecondary">
                          User Whitelist
                        </Typography>
                        <Typography variant="body2">
                          {client.restrictions.userWhitelist.length} users
                        </Typography>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        </TabPanel>

        {/* Usage Tab */}
        <TabPanel value={activeTab} index={4}>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card variant="outlined">
                <CardContent>
                  <Typography variant="subtitle1" gutterBottom>
                    Usage Statistics
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={4}>
                      <Typography variant="h4" color="primary">
                        {client.stats?.totalTokensIssued || 0}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Total Tokens Issued
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <Typography variant="h4" color="primary">
                        {client.stats?.activeTokens || 0}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Active Tokens
                      </Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                      <Typography variant="h4" color="primary">
                        {client.stats?.uniqueUsers || 0}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Unique Users
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Rate Limits
              </Typography>
              <Card variant="outlined" sx={{ mt: 1 }}>
                <CardContent>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <Box sx={{ mb: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2">Token Endpoint</Typography>
                          <Typography variant="body2">
                            {client.rateLimits?.token || 60}/min
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={(client.stats?.currentTokenRate || 0) / (client.rateLimits?.token || 60) * 100}
                        />
                      </Box>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Box sx={{ mb: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2">Introspection Endpoint</Typography>
                          <Typography variant="body2">
                            {client.rateLimits?.introspect || 300}/min
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={(client.stats?.currentIntrospectRate || 0) / (client.rateLimits?.introspect || 300) * 100}
                        />
                      </Box>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="subtitle2" color="textSecondary">
                Integration Example
              </Typography>
              <Box sx={{ mt: 1 }}>
                <CodeBlock
                  language="javascript"
                  code={`// OAuth Configuration
const config = {
  clientId: '${client.clientId}',
  authorizationEndpoint: '${window.location.origin}/oauth/authorize',
  tokenEndpoint: '${window.location.origin}/oauth/token',
  redirectUri: '${client.redirectUris[0] || 'https://your-app.com/callback'}',
  scopes: ${JSON.stringify(client.allowedScopes.slice(0, 3), null, 2)},
  responseType: 'code',
  ${client.requirePkce ? 'usePKCE: true,' : ''}
};

// Initiate OAuth flow
const authUrl = new URL(config.authorizationEndpoint);
authUrl.searchParams.append('client_id', config.clientId);
authUrl.searchParams.append('redirect_uri', config.redirectUri);
authUrl.searchParams.append('response_type', config.responseType);
authUrl.searchParams.append('scope', config.scopes.join(' '));
${client.requirePkce ? `
// PKCE Challenge
const codeVerifier = generateCodeVerifier();
const codeChallenge = await generateCodeChallenge(codeVerifier);
authUrl.searchParams.append('code_challenge', codeChallenge);
authUrl.searchParams.append('code_challenge_method', 'S256');` : ''}

window.location.href = authUrl.toString();`}
                />
              </Box>
            </Grid>
          </Grid>
        </TabPanel>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button onClick={onEdit} variant="contained">
          Edit Client
        </Button>
      </DialogActions>
    </Dialog>
  );
};