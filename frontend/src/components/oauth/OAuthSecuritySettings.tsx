import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Switch,
  FormControlLabel,
  Button,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Divider,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Grid,
  IconButton,
  Tooltip,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Security as SecurityIcon,
  Shield as ShieldIcon,
  Lock as LockIcon,
  Notifications as NotificationsIcon,
  Email as EmailIcon,
  Smartphone as SmartphoneIcon,
  Key as KeyIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Info as InfoIcon,
  ExpandMore as ExpandMoreIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  ContentCopy as CopyIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
  AccessTime as AccessTimeIcon,
  VpnKey as VpnKeyIcon,
  DevicesOther as DevicesIcon,
  Policy as PolicyIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useOAuthSettings } from '../../hooks/useOAuthSettings';

interface OAuthSecuritySettingsProps {
  onRefresh?: () => void;
}

interface SecuritySettings {
  twoFactorAuth: {
    enabled: boolean;
    method: 'authenticator' | 'sms' | 'email';
    backupCodes?: string[];
  };
  notifications: {
    newLogin: boolean;
    newApp: boolean;
    suspiciousActivity: boolean;
    tokenExpiry: boolean;
    method: 'email' | 'sms' | 'both';
  };
  sessionManagement: {
    maxSessions: number;
    sessionTimeout: number; // minutes
    rememberDevice: boolean;
    requireReauth: boolean;
  };
  tokenSettings: {
    defaultExpiry: number; // seconds
    maxTokensPerApp: number;
    autoRevokeInactive: boolean;
    inactivityPeriod: number; // days
  };
  consentSettings: {
    alwaysAskConsent: boolean;
    rememberConsent: boolean;
    consentExpiry: number; // days
    autoApproveVerified: boolean;
  };
  securityRestrictions: {
    ipWhitelist: string[];
    blockedApps: string[];
    allowedScopes: string[];
    requirePkce: boolean;
  };
}

export const OAuthSecuritySettings: React.FC<OAuthSecuritySettingsProps> = ({ onRefresh }) => {
  const { getSettings, updateSettings, generateBackupCodes, addSecurityKey } = useOAuthSettings();
  const [settings, setSettings] = useState<SecuritySettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showBackupCodes, setShowBackupCodes] = useState(false);
  const [showAddIp, setShowAddIp] = useState(false);
  const [newIp, setNewIp] = useState('');
  const [showSecurityKey, setShowSecurityKey] = useState(false);
  const [expandedSection, setExpandedSection] = useState<string | false>('authentication');
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const data = await getSettings();
      setSettings(data);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveSettings = async () => {
    if (!settings) return;
    
    setSaving(true);
    try {
      await updateSettings(settings);
      setHasChanges(false);
      onRefresh?.();
    } catch (error) {
      console.error('Failed to save settings:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleSettingChange = (section: keyof SecuritySettings, field: string, value: any) => {
    if (!settings) return;
    
    setSettings({
      ...settings,
      [section]: {
        ...settings[section],
        [field]: value,
      },
    });
    setHasChanges(true);
  };

  const handleGenerateBackupCodes = async () => {
    try {
      const codes = await generateBackupCodes();
      setSettings(prev => prev ? {
        ...prev,
        twoFactorAuth: {
          ...prev.twoFactorAuth,
          backupCodes: codes,
        },
      } : null);
      setShowBackupCodes(true);
    } catch (error) {
      console.error('Failed to generate backup codes:', error);
    }
  };

  const handleAddIp = () => {
    if (!settings || !newIp) return;
    
    setSettings({
      ...settings,
      securityRestrictions: {
        ...settings.securityRestrictions,
        ipWhitelist: [...settings.securityRestrictions.ipWhitelist, newIp],
      },
    });
    setNewIp('');
    setShowAddIp(false);
    setHasChanges(true);
  };

  const handleRemoveIp = (ip: string) => {
    if (!settings) return;
    
    setSettings({
      ...settings,
      securityRestrictions: {
        ...settings.securityRestrictions,
        ipWhitelist: settings.securityRestrictions.ipWhitelist.filter(i => i !== ip),
      },
    });
    setHasChanges(true);
  };

  const getSecurityScore = (): number => {
    if (!settings) return 0;
    
    let score = 0;
    
    // Two-factor authentication (30 points)
    if (settings.twoFactorAuth.enabled) score += 30;
    
    // Notifications (20 points)
    if (settings.notifications.newLogin) score += 5;
    if (settings.notifications.newApp) score += 5;
    if (settings.notifications.suspiciousActivity) score += 10;
    
    // Session management (20 points)
    if (settings.sessionManagement.sessionTimeout <= 60) score += 10;
    if (settings.sessionManagement.requireReauth) score += 10;
    
    // Token settings (15 points)
    if (settings.tokenSettings.autoRevokeInactive) score += 10;
    if (settings.tokenSettings.maxTokensPerApp <= 10) score += 5;
    
    // Security restrictions (15 points)
    if (settings.securityRestrictions.requirePkce) score += 10;
    if (settings.securityRestrictions.ipWhitelist.length > 0) score += 5;
    
    return Math.min(100, score);
  };

  const getSecurityLevel = (score: number) => {
    if (score >= 80) return { label: 'Excellent', color: 'success' };
    if (score >= 60) return { label: 'Good', color: 'success' };
    if (score >= 40) return { label: 'Fair', color: 'warning' };
    return { label: 'Needs Improvement', color: 'error' };
  };

  // Mock settings for demonstration
  const mockSettings: SecuritySettings = {
    twoFactorAuth: {
      enabled: true,
      method: 'authenticator',
      backupCodes: [],
    },
    notifications: {
      newLogin: true,
      newApp: true,
      suspiciousActivity: true,
      tokenExpiry: false,
      method: 'email',
    },
    sessionManagement: {
      maxSessions: 5,
      sessionTimeout: 30,
      rememberDevice: true,
      requireReauth: false,
    },
    tokenSettings: {
      defaultExpiry: 3600,
      maxTokensPerApp: 10,
      autoRevokeInactive: true,
      inactivityPeriod: 30,
    },
    consentSettings: {
      alwaysAskConsent: false,
      rememberConsent: true,
      consentExpiry: 365,
      autoApproveVerified: false,
    },
    securityRestrictions: {
      ipWhitelist: [],
      blockedApps: [],
      allowedScopes: ['openid', 'profile', 'email'],
      requirePkce: true,
    },
  };

  const displaySettings = settings || mockSettings;
  const securityScore = getSecurityScore();
  const securityLevel = getSecurityLevel(securityScore);

  if (loading) {
    return <LinearProgress />;
  }

  return (
    <Box>
      {/* Security Score */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Box>
              <Typography variant="h6" gutterBottom>
                Security Score
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography variant="h3">
                  {securityScore}%
                </Typography>
                <Chip
                  label={securityLevel.label}
                  color={securityLevel.color as any}
                  icon={<ShieldIcon />}
                />
              </Box>
            </Box>
            <Box sx={{ textAlign: 'right' }}>
              <Typography variant="body2" color="textSecondary">
                Last updated
              </Typography>
              <Typography variant="body2">
                {format(new Date(), 'PPp')}
              </Typography>
            </Box>
          </Box>
          <LinearProgress
            variant="determinate"
            value={securityScore}
            color={securityLevel.color as any}
            sx={{ mt: 2, height: 8, borderRadius: 1 }}
          />
        </CardContent>
      </Card>

      {/* Settings Sections */}
      <Accordion
        expanded={expandedSection === 'authentication'}
        onChange={(_, isExpanded) => setExpandedSection(isExpanded ? 'authentication' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <LockIcon />
            <Typography>Two-Factor Authentication</Typography>
            {displaySettings.twoFactorAuth.enabled && (
              <Chip label="Enabled" size="small" color="success" />
            )}
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <List>
            <ListItem>
              <ListItemIcon>
                <SecurityIcon />
              </ListItemIcon>
              <ListItemText
                primary="Enable Two-Factor Authentication"
                secondary="Add an extra layer of security to your account"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.twoFactorAuth.enabled}
                  onChange={(e) => handleSettingChange('twoFactorAuth', 'enabled', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            {displaySettings.twoFactorAuth.enabled && (
              <>
                <ListItem>
                  <ListItemIcon>
                    <SmartphoneIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Authentication Method"
                    secondary="Choose how to receive verification codes"
                  />
                  <ListItemSecondaryAction>
                    <Select
                      value={displaySettings.twoFactorAuth.method}
                      onChange={(e) => handleSettingChange('twoFactorAuth', 'method', e.target.value)}
                      size="small"
                    >
                      <MenuItem value="authenticator">Authenticator App</MenuItem>
                      <MenuItem value="sms">SMS</MenuItem>
                      <MenuItem value="email">Email</MenuItem>
                    </Select>
                  </ListItemSecondaryAction>
                </ListItem>

                <ListItem>
                  <ListItemIcon>
                    <KeyIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Backup Codes"
                    secondary="Generate codes to use when you can't access your phone"
                  />
                  <ListItemSecondaryAction>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={handleGenerateBackupCodes}
                    >
                      Generate
                    </Button>
                  </ListItemSecondaryAction>
                </ListItem>

                <ListItem>
                  <ListItemIcon>
                    <VpnKeyIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Security Keys"
                    secondary="Use a hardware security key for authentication"
                  />
                  <ListItemSecondaryAction>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => setShowSecurityKey(true)}
                    >
                      Add Key
                    </Button>
                  </ListItemSecondaryAction>
                </ListItem>
              </>
            )}
          </List>
        </AccordionDetails>
      </Accordion>

      <Accordion
        expanded={expandedSection === 'notifications'}
        onChange={(_, isExpanded) => setExpandedSection(isExpanded ? 'notifications' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <NotificationsIcon />
            <Typography>Security Notifications</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <List>
            <ListItem>
              <ListItemIcon>
                <DevicesIcon />
              </ListItemIcon>
              <ListItemText
                primary="New Login Alerts"
                secondary="Get notified when someone signs in from a new device"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.notifications.newLogin}
                  onChange={(e) => handleSettingChange('notifications', 'newLogin', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemIcon>
                <AppsIcon />
              </ListItemIcon>
              <ListItemText
                primary="New App Connections"
                secondary="Get notified when a new app is authorized"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.notifications.newApp}
                  onChange={(e) => handleSettingChange('notifications', 'newApp', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemIcon>
                <WarningIcon />
              </ListItemIcon>
              <ListItemText
                primary="Suspicious Activity"
                secondary="Get alerts about unusual account activity"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.notifications.suspiciousActivity}
                  onChange={(e) => handleSettingChange('notifications', 'suspiciousActivity', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemIcon>
                <AccessTimeIcon />
              </ListItemIcon>
              <ListItemText
                primary="Token Expiry Reminders"
                secondary="Get notified before tokens expire"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.notifications.tokenExpiry}
                  onChange={(e) => handleSettingChange('notifications', 'tokenExpiry', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemIcon>
                <EmailIcon />
              </ListItemIcon>
              <ListItemText
                primary="Notification Method"
                secondary="How to receive security notifications"
              />
              <ListItemSecondaryAction>
                <Select
                  value={displaySettings.notifications.method}
                  onChange={(e) => handleSettingChange('notifications', 'method', e.target.value)}
                  size="small"
                >
                  <MenuItem value="email">Email</MenuItem>
                  <MenuItem value="sms">SMS</MenuItem>
                  <MenuItem value="both">Both</MenuItem>
                </Select>
              </ListItemSecondaryAction>
            </ListItem>
          </List>
        </AccordionDetails>
      </Accordion>

      <Accordion
        expanded={expandedSection === 'sessions'}
        onChange={(_, isExpanded) => setExpandedSection(isExpanded ? 'sessions' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <DevicesIcon />
            <Typography>Session Management</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <List>
            <ListItem>
              <ListItemText
                primary="Maximum Concurrent Sessions"
                secondary="Limit the number of active sessions"
              />
              <ListItemSecondaryAction>
                <TextField
                  type="number"
                  value={displaySettings.sessionManagement.maxSessions}
                  onChange={(e) => handleSettingChange('sessionManagement', 'maxSessions', parseInt(e.target.value))}
                  size="small"
                  sx={{ width: 80 }}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemText
                primary="Session Timeout"
                secondary="Automatically sign out after inactivity (minutes)"
              />
              <ListItemSecondaryAction>
                <TextField
                  type="number"
                  value={displaySettings.sessionManagement.sessionTimeout}
                  onChange={(e) => handleSettingChange('sessionManagement', 'sessionTimeout', parseInt(e.target.value))}
                  size="small"
                  sx={{ width: 80 }}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemText
                primary="Remember This Device"
                secondary="Allow devices to stay signed in"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.sessionManagement.rememberDevice}
                  onChange={(e) => handleSettingChange('sessionManagement', 'rememberDevice', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemText
                primary="Require Re-authentication"
                secondary="Ask for password before sensitive actions"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.sessionManagement.requireReauth}
                  onChange={(e) => handleSettingChange('sessionManagement', 'requireReauth', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>
          </List>
        </AccordionDetails>
      </Accordion>

      <Accordion
        expanded={expandedSection === 'tokens'}
        onChange={(_, isExpanded) => setExpandedSection(isExpanded ? 'tokens' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <VpnKeyIcon />
            <Typography>Token Settings</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <List>
            <ListItem>
              <ListItemText
                primary="Default Token Expiry"
                secondary="How long tokens remain valid (seconds)"
              />
              <ListItemSecondaryAction>
                <TextField
                  type="number"
                  value={displaySettings.tokenSettings.defaultExpiry}
                  onChange={(e) => handleSettingChange('tokenSettings', 'defaultExpiry', parseInt(e.target.value))}
                  size="small"
                  sx={{ width: 100 }}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemText
                primary="Maximum Tokens Per App"
                secondary="Limit tokens each app can have"
              />
              <ListItemSecondaryAction>
                <TextField
                  type="number"
                  value={displaySettings.tokenSettings.maxTokensPerApp}
                  onChange={(e) => handleSettingChange('tokenSettings', 'maxTokensPerApp', parseInt(e.target.value))}
                  size="small"
                  sx={{ width: 80 }}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemText
                primary="Auto-revoke Inactive Tokens"
                secondary="Automatically revoke unused tokens"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.tokenSettings.autoRevokeInactive}
                  onChange={(e) => handleSettingChange('tokenSettings', 'autoRevokeInactive', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            {displaySettings.tokenSettings.autoRevokeInactive && (
              <ListItem>
                <ListItemText
                  primary="Inactivity Period"
                  secondary="Days before revoking inactive tokens"
                />
                <ListItemSecondaryAction>
                  <TextField
                    type="number"
                    value={displaySettings.tokenSettings.inactivityPeriod}
                    onChange={(e) => handleSettingChange('tokenSettings', 'inactivityPeriod', parseInt(e.target.value))}
                    size="small"
                    sx={{ width: 80 }}
                  />
                </ListItemSecondaryAction>
              </ListItem>
            )}
          </List>
        </AccordionDetails>
      </Accordion>

      <Accordion
        expanded={expandedSection === 'restrictions'}
        onChange={(_, isExpanded) => setExpandedSection(isExpanded ? 'restrictions' : false)}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PolicyIcon />
            <Typography>Security Restrictions</Typography>
          </Box>
        </AccordionSummary>
        <AccordionDetails>
          <List>
            <ListItem>
              <ListItemText
                primary="Require PKCE"
                secondary="Enforce Proof Key for Code Exchange for all apps"
              />
              <ListItemSecondaryAction>
                <Switch
                  checked={displaySettings.securityRestrictions.requirePkce}
                  onChange={(e) => handleSettingChange('securityRestrictions', 'requirePkce', e.target.checked)}
                />
              </ListItemSecondaryAction>
            </ListItem>

            <ListItem>
              <ListItemText
                primary="IP Whitelist"
                secondary="Restrict access to specific IP addresses"
              />
              <ListItemSecondaryAction>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() => setShowAddIp(true)}
                >
                  Add IP
                </Button>
              </ListItemSecondaryAction>
            </ListItem>

            {displaySettings.securityRestrictions.ipWhitelist.length > 0 && (
              <ListItem>
                <Box sx={{ width: '100%', pl: 2 }}>
                  {displaySettings.securityRestrictions.ipWhitelist.map((ip) => (
                    <Chip
                      key={ip}
                      label={ip}
                      onDelete={() => handleRemoveIp(ip)}
                      sx={{ m: 0.5 }}
                    />
                  ))}
                </Box>
              </ListItem>
            )}
          </List>
        </AccordionDetails>
      </Accordion>

      {/* Save Button */}
      {hasChanges && (
        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
          <Button
            variant="outlined"
            onClick={() => {
              fetchSettings();
              setHasChanges(false);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSaveSettings}
            disabled={saving}
            startIcon={saving ? null : <CheckCircleIcon />}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </Box>
      )}

      {/* Backup Codes Dialog */}
      <Dialog open={showBackupCodes} onClose={() => setShowBackupCodes(false)}>
        <DialogTitle>Backup Codes</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              Save these codes in a safe place. Each code can only be used once.
            </Typography>
          </Alert>
          <Grid container spacing={1}>
            {displaySettings.twoFactorAuth.backupCodes?.map((code, index) => (
              <Grid item xs={6} key={index}>
                <Card variant="outlined">
                  <CardContent sx={{ py: 1 }}>
                    <Typography variant="body2" fontFamily="monospace">
                      {code}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowBackupCodes(false)}>Close</Button>
          <Button variant="contained" startIcon={<CopyIcon />}>
            Copy All
          </Button>
        </DialogActions>
      </Dialog>

      {/* Add IP Dialog */}
      <Dialog open={showAddIp} onClose={() => setShowAddIp(false)}>
        <DialogTitle>Add IP Address</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="IP Address"
            value={newIp}
            onChange={(e) => setNewIp(e.target.value)}
            placeholder="192.168.1.1 or 192.168.1.0/24"
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAddIp(false)}>Cancel</Button>
          <Button onClick={handleAddIp} variant="contained">
            Add
          </Button>
        </DialogActions>
      </Dialog>

      {/* Security Key Dialog */}
      <Dialog open={showSecurityKey} onClose={() => setShowSecurityKey(false)}>
        <DialogTitle>Add Security Key</DialogTitle>
        <DialogContent>
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="body2">
              Insert your security key and follow the browser prompts to register it.
            </Typography>
          </Alert>
          <Box sx={{ textAlign: 'center', py: 3 }}>
            <VpnKeyIcon sx={{ fontSize: 64, color: 'primary.main' }} />
            <Typography variant="body1" sx={{ mt: 2 }}>
              Waiting for security key...
            </Typography>
            <LinearProgress sx={{ mt: 2 }} />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowSecurityKey(false)}>Cancel</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};