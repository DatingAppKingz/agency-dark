import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Button,
  Checkbox,
  FormControlLabel,
  Alert,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Avatar,
  Chip,
  Link,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  LinearProgress,
  IconButton,
  Tooltip,
  Grid,
  Paper,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Security as SecurityIcon,
  Person as PersonIcon,
  Email as EmailIcon,
  Phone as PhoneIcon,
  LocationOn as LocationIcon,
  Folder as FolderIcon,
  Event as EventIcon,
  Contacts as ContactsIcon,
  ExpandMore as ExpandMoreIcon,
  VerifiedUser as VerifiedIcon,
  Block as BlockIcon,
  Help as HelpIcon,
  Launch as LaunchIcon,
  Lock as LockIcon,
  LockOpen as LockOpenIcon,
  Shield as ShieldIcon,
  Report as ReportIcon,
} from '@mui/icons-material';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useOAuthConsent } from '../../hooks/useOAuthConsent';

interface ConsentRequest {
  client: {
    id: string;
    name: string;
    description?: string;
    logo?: string;
    website?: string;
    developer?: string;
    verified: boolean;
    privacyPolicy?: string;
    termsOfService?: string;
    trustScore?: number;
  };
  requestedScopes: {
    scope: string;
    required: boolean;
    description: string;
    icon?: React.ReactNode;
    dataTypes?: string[];
    risk?: 'low' | 'medium' | 'high';
  }[];
  user: {
    id: string;
    name: string;
    email: string;
    avatar?: string;
  };
  redirectUri: string;
  state?: string;
  codeChallenge?: string;
  responseType: string;
  previousConsent?: {
    grantedAt: string;
    scopes: string[];
  };
}

const scopeIcons: Record<string, React.ReactNode> = {
  openid: <LockOpenIcon />,
  profile: <PersonIcon />,
  email: <EmailIcon />,
  phone: <PhoneIcon />,
  address: <LocationIcon />,
  'api:read': <FolderIcon />,
  'api:write': <FolderIcon />,
  'api:delete': <FolderIcon />,
  calendar: <EventIcon />,
  contacts: <ContactsIcon />,
  files: <FolderIcon />,
};

const scopeDescriptions: Record<string, string> = {
  openid: 'Authenticate your identity',
  profile: 'Your public profile information (name, photo)',
  email: 'Your email address',
  phone: 'Your phone number',
  address: 'Your physical address',
  'api:read': 'Read access to your data',
  'api:write': 'Create and modify your data',
  'api:delete': 'Delete your data',
  calendar: 'Access your calendar events',
  contacts: 'Access your contacts',
  files: 'Access your files and documents',
};

const scopeDataTypes: Record<string, string[]> = {
  profile: ['Name', 'Profile photo', 'Username', 'Bio'],
  email: ['Primary email', 'Email verification status'],
  phone: ['Phone number', 'Phone verification status'],
  address: ['Street address', 'City', 'State', 'Postal code', 'Country'],
  'api:read': ['All accessible data'],
  'api:write': ['Create new records', 'Update existing data'],
  'api:delete': ['Permanently remove data'],
  calendar: ['Events', 'Reminders', 'Availability'],
  contacts: ['Contact names', 'Email addresses', 'Phone numbers'],
  files: ['Documents', 'Images', 'Spreadsheets'],
};

const scopeRiskLevels: Record<string, 'low' | 'medium' | 'high'> = {
  openid: 'low',
  profile: 'low',
  email: 'low',
  phone: 'medium',
  address: 'medium',
  'api:read': 'medium',
  'api:write': 'high',
  'api:delete': 'high',
  calendar: 'medium',
  contacts: 'high',
  files: 'high',
};

const ConsentScreen: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getConsentRequest, approveConsent, denyConsent } = useOAuthConsent();
  
  const [consentRequest, setConsentRequest] = useState<ConsentRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [selectedScopes, setSelectedScopes] = useState<Set<string>>(new Set());
  const [rememberDecision, setRememberDecision] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [expandedScope, setExpandedScope] = useState<string | false>(false);

  useEffect(() => {
    fetchConsentRequest();
  }, []);

  const fetchConsentRequest = async () => {
    setLoading(true);
    try {
      const clientId = searchParams.get('client_id');
      const scope = searchParams.get('scope');
      const redirectUri = searchParams.get('redirect_uri');
      const state = searchParams.get('state');
      const codeChallenge = searchParams.get('code_challenge');
      const responseType = searchParams.get('response_type');

      if (!clientId || !scope || !redirectUri) {
        throw new Error('Missing required parameters');
      }

      const request = await getConsentRequest({
        clientId,
        scope,
        redirectUri,
        state,
        codeChallenge,
        responseType: responseType || 'code',
      });

      setConsentRequest(request);
      
      // Pre-select required scopes
      const required = new Set<string>();
      request.requestedScopes.forEach(s => {
        if (s.required) required.add(s.scope);
      });
      setSelectedScopes(required);
    } catch (error) {
      console.error('Failed to fetch consent request:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleScopeToggle = (scope: string, required: boolean) => {
    if (required) return; // Can't uncheck required scopes
    
    const newSelected = new Set(selectedScopes);
    if (newSelected.has(scope)) {
      newSelected.delete(scope);
    } else {
      newSelected.add(scope);
    }
    setSelectedScopes(newSelected);
  };

  const handleApprove = async () => {
    if (!consentRequest) return;
    
    setProcessing(true);
    try {
      const result = await approveConsent({
        clientId: consentRequest.client.id,
        scopes: Array.from(selectedScopes),
        rememberDecision,
        redirectUri: consentRequest.redirectUri,
        state: consentRequest.state,
      });
      
      // Redirect to the client with the authorization code
      window.location.href = result.redirectUrl;
    } catch (error) {
      console.error('Failed to approve consent:', error);
    } finally {
      setProcessing(false);
    }
  };

  const handleDeny = async () => {
    if (!consentRequest) return;
    
    setProcessing(true);
    try {
      const result = await denyConsent({
        clientId: consentRequest.client.id,
        redirectUri: consentRequest.redirectUri,
        state: consentRequest.state,
      });
      
      // Redirect to the client with error
      window.location.href = result.redirectUrl;
    } catch (error) {
      console.error('Failed to deny consent:', error);
    } finally {
      setProcessing(false);
    }
  };

  const getRiskColor = (risk?: string) => {
    switch (risk) {
      case 'high': return 'error';
      case 'medium': return 'warning';
      case 'low': return 'success';
      default: return 'default';
    }
  };

  const getTrustBadge = (client: ConsentRequest['client']) => {
    if (client.verified) {
      return <Chip label="Verified" size="small" color="success" icon={<VerifiedIcon />} />;
    }
    if (client.trustScore && client.trustScore >= 80) {
      return <Chip label="Trusted" size="small" color="primary" icon={<ShieldIcon />} />;
    }
    if (client.trustScore && client.trustScore < 50) {
      return <Chip label="Unverified" size="small" color="warning" icon={<WarningIcon />} />;
    }
    return null;
  };

  // Mock data for demonstration
  const mockRequest: ConsentRequest = {
    client: {
      id: 'client_123',
      name: 'Analytics Dashboard',
      description: 'Advanced analytics and reporting for your business',
      logo: '📊',
      website: 'https://analytics.example.com',
      developer: 'Data Insights Inc.',
      verified: true,
      privacyPolicy: 'https://analytics.example.com/privacy',
      termsOfService: 'https://analytics.example.com/terms',
      trustScore: 85,
    },
    requestedScopes: [
      {
        scope: 'openid',
        required: true,
        description: scopeDescriptions.openid,
        icon: scopeIcons.openid,
        dataTypes: scopeDataTypes.openid,
        risk: scopeRiskLevels.openid,
      },
      {
        scope: 'profile',
        required: true,
        description: scopeDescriptions.profile,
        icon: scopeIcons.profile,
        dataTypes: scopeDataTypes.profile,
        risk: scopeRiskLevels.profile,
      },
      {
        scope: 'email',
        required: false,
        description: scopeDescriptions.email,
        icon: scopeIcons.email,
        dataTypes: scopeDataTypes.email,
        risk: scopeRiskLevels.email,
      },
      {
        scope: 'api:read',
        required: false,
        description: scopeDescriptions['api:read'],
        icon: scopeIcons['api:read'],
        dataTypes: scopeDataTypes['api:read'],
        risk: scopeRiskLevels['api:read'],
      },
    ],
    user: {
      id: 'user_123',
      name: 'John Doe',
      email: 'john.doe@example.com',
      avatar: '👤',
    },
    redirectUri: 'https://analytics.example.com/callback',
    state: 'random_state_123',
    responseType: 'code',
    previousConsent: {
      grantedAt: new Date(Date.now() - 30 * 86400000).toISOString(),
      scopes: ['openid', 'profile'],
    },
  };

  const displayRequest = consentRequest || mockRequest;

  if (loading) {
    return (
      <Container maxWidth="sm" sx={{ mt: 8 }}>
        <Card>
          <CardContent sx={{ textAlign: 'center', py: 4 }}>
            <CircularProgress />
            <Typography variant="body1" sx={{ mt: 2 }}>
              Loading consent request...
            </Typography>
          </CardContent>
        </Card>
      </Container>
    );
  }

  return (
    <Container maxWidth="sm" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ textAlign: 'center' }}>
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', mb: 2 }}>
              <Avatar sx={{ width: 64, height: 64, bgcolor: 'primary.light', fontSize: '2rem' }}>
                {displayRequest.client.logo || <AppsIcon />}
              </Avatar>
              <Box sx={{ mx: 2 }}>
                <SecurityIcon sx={{ fontSize: 32, color: 'text.secondary' }} />
              </Box>
              <Avatar sx={{ width: 64, height: 64, bgcolor: 'secondary.light', fontSize: '2rem' }}>
                {displayRequest.user.avatar || <PersonIcon />}
              </Avatar>
            </Box>
            
            <Typography variant="h5" gutterBottom>
              {displayRequest.client.name} wants to access your account
            </Typography>
            
            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, mb: 2 }}>
              {getTrustBadge(displayRequest.client)}
              {displayRequest.client.developer && (
                <Chip label={`by ${displayRequest.client.developer}`} size="small" variant="outlined" />
              )}
            </Box>
            
            {displayRequest.client.description && (
              <Typography variant="body2" color="textSecondary">
                {displayRequest.client.description}
              </Typography>
            )}
          </Box>
        </CardContent>
      </Card>

      {/* Previous Consent Notice */}
      {displayRequest.previousConsent && (
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            You previously granted access to this application. The app is requesting additional permissions.
          </Typography>
        </Alert>
      )}

      {/* Permissions Request */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            This app will be able to:
          </Typography>
          
          <List>
            {displayRequest.requestedScopes.map((scopeItem, index) => (
              <React.Fragment key={scopeItem.scope}>
                {index > 0 && <Divider />}
                <ListItem disablePadding>
                  <Accordion
                    expanded={expandedScope === scopeItem.scope}
                    onChange={(_, isExpanded) => setExpandedScope(isExpanded ? scopeItem.scope : false)}
                    elevation={0}
                    sx={{ width: '100%', bgcolor: 'transparent' }}
                  >
                    <AccordionSummary
                      expandIcon={<ExpandMoreIcon />}
                      sx={{ px: 0 }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={selectedScopes.has(scopeItem.scope)}
                              onChange={() => handleScopeToggle(scopeItem.scope, scopeItem.required)}
                              disabled={scopeItem.required}
                              onClick={(e) => e.stopPropagation()}
                            />
                          }
                          label=""
                          sx={{ mr: 1 }}
                        />
                        <ListItemIcon sx={{ minWidth: 40 }}>
                          {scopeItem.icon}
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                              <Typography variant="body1">
                                {scopeItem.description}
                              </Typography>
                              {scopeItem.required && (
                                <Chip label="Required" size="small" color="primary" />
                              )}
                              <Chip
                                label={scopeItem.risk}
                                size="small"
                                color={getRiskColor(scopeItem.risk)}
                              />
                            </Box>
                          }
                        />
                      </Box>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box sx={{ pl: 7 }}>
                        <Typography variant="body2" color="textSecondary" gutterBottom>
                          This permission gives access to:
                        </Typography>
                        <List dense>
                          {scopeItem.dataTypes?.map((dataType) => (
                            <ListItem key={dataType} disableGutters>
                              <ListItemIcon sx={{ minWidth: 30 }}>
                                <CheckCircleIcon fontSize="small" color="action" />
                              </ListItemIcon>
                              <ListItemText primary={dataType} />
                            </ListItem>
                          ))}
                        </List>
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                </ListItem>
              </React.Fragment>
            ))}
          </List>
          
          <FormControlLabel
            control={
              <Checkbox
                checked={rememberDecision}
                onChange={(e) => setRememberDecision(e.target.checked)}
              />
            }
            label={
              <Typography variant="body2">
                Remember my decision for this app
              </Typography>
            }
            sx={{ mt: 2 }}
          />
        </CardContent>
      </Card>

      {/* Security Information */}
      <Accordion sx={{ mb: 3 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <InfoIcon />
            <Typography>Security & Privacy Information</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                About this app
              </Typography>
              <List dense>
                {displayRequest.client.website && (
                  <ListItem disableGutters>
                    <ListItemIcon sx={{ minWidth: 30 }}>
                      <LaunchIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Link href={displayRequest.client.website} target="_blank" rel="noopener">
                          {displayRequest.client.website}
                        </Link>
                      }
                    />
                  </ListItem>
                )}
                {displayRequest.client.privacyPolicy && (
                  <ListItem disableGutters>
                    <ListItemIcon sx={{ minWidth: 30 }}>
                      <SecurityIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Link href={displayRequest.client.privacyPolicy} target="_blank" rel="noopener">
                          Privacy Policy
                        </Link>
                      }
                    />
                  </ListItem>
                )}
                {displayRequest.client.termsOfService && (
                  <ListItem disableGutters>
                    <ListItemIcon sx={{ minWidth: 30 }}>
                      <InfoIcon fontSize="small" />
                    </ListItemIcon>
                    <ListItemText
                      primary={
                        <Link href={displayRequest.client.termsOfService} target="_blank" rel="noopener">
                          Terms of Service
                        </Link>
                      }
                    />
                  </ListItem>
                )}
              </List>
            </Grid>
            
            <Grid item xs={12}>
              <Alert severity="info">
                <Typography variant="body2">
                  • You can revoke access at any time from your account settings
                  <br />
                  • This app will not be able to access your password
                  <br />
                  • Your data will be handled according to the app's privacy policy
                </Typography>
              </Alert>
            </Grid>
          </Grid>
        </AccordionDetails>
      </Accordion>

      {/* Action Buttons */}
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Button
          fullWidth
          variant="outlined"
          size="large"
          onClick={handleDeny}
          disabled={processing}
          startIcon={<BlockIcon />}
        >
          Deny
        </Button>
        <Button
          fullWidth
          variant="contained"
          size="large"
          onClick={handleApprove}
          disabled={processing || selectedScopes.size === 0}
          startIcon={processing ? null : <CheckCircleIcon />}
        >
          {processing ? 'Processing...' : 'Allow'}
        </Button>
      </Box>

      {/* Footer Links */}
      <Box sx={{ mt: 3, textAlign: 'center' }}>
        <Button
          size="small"
          startIcon={<HelpIcon />}
          onClick={() => setShowDetails(true)}
        >
          Learn more about permissions
        </Button>
        {' • '}
        <Button
          size="small"
          startIcon={<ReportIcon />}
          color="error"
        >
          Report this app
        </Button>
      </Box>

      {/* Learn More Dialog */}
      <Dialog open={showDetails} onClose={() => setShowDetails(false)} maxWidth="sm" fullWidth>
        <DialogTitle>About OAuth Permissions</DialogTitle>
        <DialogContent>
          <Typography variant="body2" paragraph>
            When you authorize an application, you're granting it permission to access specific parts of your account data.
          </Typography>
          
          <Typography variant="subtitle2" gutterBottom>
            Permission Levels
          </Typography>
          <List dense>
            <ListItem>
              <ListItemIcon>
                <Chip label="low" size="small" color="success" />
              </ListItemIcon>
              <ListItemText
                primary="Low Risk"
                secondary="Basic information like your name and email"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <Chip label="medium" size="small" color="warning" />
              </ListItemIcon>
              <ListItemText
                primary="Medium Risk"
                secondary="Access to read your data and contacts"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <Chip label="high" size="small" color="error" />
              </ListItemIcon>
              <ListItemText
                primary="High Risk"
                secondary="Ability to modify or delete your data"
              />
            </ListItem>
          </List>
          
          <Alert severity="info" sx={{ mt: 2 }}>
            <Typography variant="body2">
              You can always revoke an app's access from your account settings without affecting your account or data.
            </Typography>
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowDetails(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default ConsentScreen;