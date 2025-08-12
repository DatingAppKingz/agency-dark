import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  Grid,
  Chip,
  List,
  ListItem,
  ListItemText,
  Divider,
  Alert,
  Card,
  CardContent,
  IconButton,
  Tooltip,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableRow,
} from '@mui/material';
import {
  ContentCopy as CopyIcon,
  Block as BlockIcon,
  AccessTime as AccessTimeIcon,
  VpnKey as KeyIcon,
  Person as PersonIcon,
  Apps as AppsIcon,
  Security as SecurityIcon,
  Info as InfoIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Fingerprint as FingerprintIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow, isAfter, addSeconds } from 'date-fns';
import { OAuthToken } from '../../types/oauth';
import { CodeBlock } from '../common/CodeBlock';

interface TokenDetailsDialogProps {
  token: OAuthToken;
  open: boolean;
  onClose: () => void;
  onRevoke: () => void;
}

export const TokenDetailsDialog: React.FC<TokenDetailsDialogProps> = ({
  token,
  open,
  onClose,
  onRevoke,
}) => {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [showToken, setShowToken] = useState(false);

  const handleCopy = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const getTokenStatus = () => {
    const now = new Date();
    const expiresAt = new Date(token.expiresAt);
    
    if (token.status === 'revoked') {
      return { label: 'Revoked', color: 'error' as const, icon: <BlockIcon /> };
    }
    if (isAfter(now, expiresAt)) {
      return { label: 'Expired', color: 'error' as const, icon: <ErrorIcon /> };
    }
    if (isAfter(addSeconds(now, 3600), expiresAt)) {
      return { label: 'Expiring Soon', color: 'warning' as const, icon: <WarningIcon /> };
    }
    return { label: 'Active', color: 'success' as const, icon: <CheckCircleIcon /> };
  };

  const getTimeRemaining = () => {
    const now = new Date();
    const expiresAt = new Date(token.expiresAt);
    
    if (isAfter(now, expiresAt)) {
      return { percentage: 0, label: 'Expired' };
    }
    
    const issuedAt = new Date(token.issuedAt);
    const totalDuration = expiresAt.getTime() - issuedAt.getTime();
    const elapsed = now.getTime() - issuedAt.getTime();
    const percentage = Math.max(0, Math.min(100, (elapsed / totalDuration) * 100));
    
    return {
      percentage: 100 - percentage,
      label: formatDistanceToNow(expiresAt, { addSuffix: true }),
    };
  };

  const tokenStatus = getTokenStatus();
  const timeRemaining = getTimeRemaining();

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <KeyIcon />
            <Typography variant="h6">Token Details</Typography>
            <Chip
              label={tokenStatus.label}
              size="small"
              color={tokenStatus.color}
              icon={tokenStatus.icon}
            />
          </Box>
          <Typography variant="caption" color="textSecondary">
            {token.type.replace('_', ' ').toUpperCase()}
          </Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Grid container spacing={3}>
          {/* Token Information */}
          <Grid item xs={12}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                  <Typography variant="subtitle1">Token Information</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Button
                      size="small"
                      variant="outlined"
                      onClick={() => setShowToken(!showToken)}
                    >
                      {showToken ? 'Hide' : 'Show'} Token
                    </Button>
                    {showToken && (
                      <IconButton
                        size="small"
                        onClick={() => handleCopy(token.token, 'token')}
                      >
                        <CopyIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                </Box>
                
                {showToken && (
                  <Alert severity="warning" sx={{ mb: 2 }}>
                    <Typography variant="caption">
                      This is sensitive information. Never share tokens publicly.
                    </Typography>
                  </Alert>
                )}
                
                <Table size="small">
                  <TableBody>
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'medium', width: '30%' }}>
                        Token ID
                      </TableCell>
                      <TableCell>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Typography variant="body2" fontFamily="monospace">
                            {token.id}
                          </Typography>
                          <IconButton
                            size="small"
                            onClick={() => handleCopy(token.id, 'id')}
                          >
                            <CopyIcon fontSize="small" />
                          </IconButton>
                          {copiedField === 'id' && (
                            <Typography variant="caption" color="success.main">
                              Copied!
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                    
                    {showToken && (
                      <TableRow>
                        <TableCell sx={{ fontWeight: 'medium' }}>
                          Token Value
                        </TableCell>
                        <TableCell>
                          <Typography
                            variant="body2"
                            fontFamily="monospace"
                            sx={{
                              wordBreak: 'break-all',
                              fontSize: '0.75rem',
                            }}
                          >
                            {token.token}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                    
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'medium' }}>
                        Type
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={token.type.replace('_', ' ')}
                          size="small"
                          variant="outlined"
                        />
                      </TableCell>
                    </TableRow>
                    
                    <TableRow>
                      <TableCell sx={{ fontWeight: 'medium' }}>
                        JTI (Token ID)
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {token.jti || 'N/A'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </Grid>

          {/* Client & User Information */}
          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <AppsIcon />
                  <Typography variant="subtitle1">Client Information</Typography>
                </Box>
                
                <List dense>
                  <ListItem disableGutters>
                    <ListItemText
                      primary="Client Name"
                      secondary={token.clientName || 'Unknown'}
                    />
                  </ListItem>
                  <ListItem disableGutters>
                    <ListItemText
                      primary="Client ID"
                      secondary={
                        <Typography variant="body2" fontFamily="monospace">
                          {token.clientId}
                        </Typography>
                      }
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={6}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <PersonIcon />
                  <Typography variant="subtitle1">User Information</Typography>
                </Box>
                
                <List dense>
                  <ListItem disableGutters>
                    <ListItemText
                      primary="User Name"
                      secondary={token.userName || 'Unknown'}
                    />
                  </ListItem>
                  <ListItem disableGutters>
                    <ListItemText
                      primary="User ID"
                      secondary={
                        <Typography variant="body2" fontFamily="monospace">
                          {token.userId}
                        </Typography>
                      }
                    />
                  </ListItem>
                  <ListItem disableGutters>
                    <ListItemText
                      primary="Subject"
                      secondary={token.subject || token.userId}
                    />
                  </ListItem>
                </List>
              </CardContent>
            </Card>
          </Grid>

          {/* Token Lifetime */}
          <Grid item xs={12}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <AccessTimeIcon />
                  <Typography variant="subtitle1">Token Lifetime</Typography>
                </Box>
                
                <Box sx={{ mb: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="body2">Time Remaining</Typography>
                    <Typography variant="body2" color="textSecondary">
                      {timeRemaining.label}
                    </Typography>
                  </Box>
                  <LinearProgress
                    variant="determinate"
                    value={timeRemaining.percentage}
                    color={timeRemaining.percentage > 20 ? 'primary' : 'warning'}
                    sx={{ height: 8, borderRadius: 1 }}
                  />
                </Box>
                
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={4}>
                    <Typography variant="body2" color="textSecondary">
                      Issued At
                    </Typography>
                    <Typography variant="body1">
                      {format(new Date(token.issuedAt), 'PPpp')}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      {formatDistanceToNow(new Date(token.issuedAt), { addSuffix: true })}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={12} sm={4}>
                    <Typography variant="body2" color="textSecondary">
                      Expires At
                    </Typography>
                    <Typography variant="body1">
                      {format(new Date(token.expiresAt), 'PPpp')}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      {formatDistanceToNow(new Date(token.expiresAt), { addSuffix: true })}
                    </Typography>
                  </Grid>
                  
                  <Grid item xs={12} sm={4}>
                    <Typography variant="body2" color="textSecondary">
                      Last Used
                    </Typography>
                    <Typography variant="body1">
                      {token.lastUsedAt
                        ? format(new Date(token.lastUsedAt), 'PPpp')
                        : 'Never'}
                    </Typography>
                    {token.lastUsedAt && (
                      <Typography variant="caption" color="textSecondary">
                        {formatDistanceToNow(new Date(token.lastUsedAt), { addSuffix: true })}
                      </Typography>
                    )}
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>

          {/* Scopes & Permissions */}
          <Grid item xs={12}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <SecurityIcon />
                  <Typography variant="subtitle1">Scopes & Permissions</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {token.scopes.map((scope) => (
                    <Chip
                      key={scope}
                      label={scope}
                      size="small"
                      variant="outlined"
                      icon={<CheckCircleIcon />}
                    />
                  ))}
                </Box>
                
                {token.audience && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="textSecondary" gutterBottom>
                      Audience
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {(Array.isArray(token.audience) ? token.audience : [token.audience]).map((aud) => (
                        <Chip
                          key={aud}
                          label={aud}
                          size="small"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Additional Information */}
          <Grid item xs={12}>
            <Card variant="outlined">
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <InfoIcon />
                  <Typography variant="subtitle1">Additional Information</Typography>
                </Box>
                
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <List dense>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="IP Address"
                          secondary={token.ipAddress || 'Unknown'}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="User Agent"
                          secondary={
                            <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                              {token.userAgent || 'Unknown'}
                            </Typography>
                          }
                        />
                      </ListItem>
                    </List>
                  </Grid>
                  
                  <Grid item xs={12} sm={6}>
                    <List dense>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Grant Type"
                          secondary={token.grantType || 'Unknown'}
                        />
                      </ListItem>
                      <ListItem disableGutters>
                        <ListItemText
                          primary="Session ID"
                          secondary={
                            <Typography variant="body2" fontFamily="monospace">
                              {token.sessionId || 'N/A'}
                            </Typography>
                          }
                        />
                      </ListItem>
                    </List>
                  </Grid>
                </Grid>

                {token.deviceInfo && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" color="textSecondary" gutterBottom>
                      Device Information
                    </Typography>
                    <Typography variant="body2">
                      {token.deviceInfo.name || 'Unknown Device'} - {token.deviceInfo.type || 'Unknown Type'}
                    </Typography>
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Token Usage Example */}
          {token.status === 'active' && (
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Usage Example
              </Typography>
              <CodeBlock
                language="bash"
                code={`# Using the token in an API request
curl -H "Authorization: Bearer ${showToken ? token.token : 'YOUR_TOKEN_HERE'}" \\
  ${window.location.origin}/api/v1/resource

# Introspect token
curl -X POST ${window.location.origin}/oauth/introspect \\
  -H "Content-Type: application/x-www-form-urlencoded" \\
  -d "token=${showToken ? token.token : 'YOUR_TOKEN_HERE'}" \\
  -d "client_id=${token.clientId}" \\
  -d "client_secret=YOUR_CLIENT_SECRET"`}
              />
            </Grid>
          )}
        </Grid>
      </DialogContent>

      <DialogActions>
        <Button onClick={onClose}>Close</Button>
        <Button
          onClick={onRevoke}
          color="error"
          variant="contained"
          startIcon={<BlockIcon />}
          disabled={token.status === 'revoked'}
        >
          Revoke Token
        </Button>
      </DialogActions>
    </Dialog>
  );
};