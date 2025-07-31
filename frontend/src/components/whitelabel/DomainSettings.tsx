import { useState } from 'react';
import {
  Box,
  Typography,
  Grid,
  Paper,
  TextField,
  Button,
  Alert,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Switch,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction } from '@mui/material';
import {
  ContentCopy,
  CheckCircle,
  Error as ErrorIcon,
  Refresh,
  Delete,
  Add,
  Security } from '@mui/icons-material';
import { useToast } from '@/components/common/Toaster';

interface DomainSettingsProps {
  onChange: () => void;
}

interface DomainRecord {
  type: string;
  name: string;
  value: string;
  ttl: number;
}

interface CustomDomain {
  id: string;
  domain: string;
  status: 'pending' | 'verified' | 'active' | '';
  sslStatus: 'pending' | 'active' | '';
  createdAt: string;
  verifiedAt?: string;
}

export const DomainSettings = ({ onChange }: DomainSettingsProps) => {
  const { success } = useToast();
  const [newDomain, setNewDomain] = useState('');
  const [activeStep, setActiveStep] = useState(0);
  const [domains, setDomains] = useState<CustomDomain[]>([
    {
      id: '1',
      domain: 'app.example.com',
      status: 'active',
      sslStatus: 'active',
      createdAt: '2024-01-15',
      verifiedAt: '2024-01-15' },
  ]);

  const [domainSettings, setDomainSettings] = useState({
    enforceSSL: true,
    allowSubdomains: false,
    customHeaders: '',
    redirectWWW: true });

  const dnsRecords: DomainRecord[] = [
    { type: 'A', name: '@', value: '192.168.1.1', ttl: 3600 },
    { type: 'CNAME', name: 'www', value: 'app.agencydark.com', ttl: 3600 },
    { type: 'TXT', name: '_verification', value: 'agencydark-verify=abc123xyz', ttl: 300 },
  ];

  const handleAddDomain = () => {
    if (!newDomain) return;

    const domain: CustomDomain = {
      id: Date.now().toString(),
      domain: newDomain,
      status: 'pending',
      sslStatus: 'pending',
      createdAt: new Date().toISOString().split('T')[0] };

    setDomains([...domains, domain]);
    setNewDomain('');
    setActiveStep(1);
    onChange();
    success('added. Please configure DNS records.');
  };

  const handleVerifyDomain = (domainId: string) => {
    // Simulate domain verification
    setDomains(prev => prev.map(d => 
      d.id === domainId 
        ? { ...d, status: 'verified', verifiedAt: new Date().toISOString().split('T')[0] }
        : d
    ));
    success('verified successfully');
    onChange();
  };

  const handleActivateDomain = (domainId: string) => {
    setDomains(prev => prev.map(d => 
      d.id === domainId 
        ? { ...d, status: 'active', sslStatus: 'active' }
        : d
    ));
    success('activated successfully');
    onChange();
  };

  const handleRemoveDomain = (domainId: string) => {
    setDomains(prev => prev.filter(d => d.id !== domainId));
    success('removed');
    onChange();
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    success('Copied to clipboard');
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
      case 'verified':
        return <CheckCircle color="success" fontSize="small" />;
      case '':
        return <ErrorIcon color="" fontSize="small" />;
      default:
        return <Refresh color="warning" fontSize="small" />;
    }
  };

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Add */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Add Custom </Typography>
            
            <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
              <TextField
                fullWidth
                label="Name"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                placeholder="app.yourdomain.com"
                helperText="Enter your custom domain without https://"
              />
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={handleAddDomain}
                disabled={!newDomain}
              >
                Add </Button>
            </Box>
          </Paper>
        </Grid>

        {/* Setup Steps */}
        {domains.some(d => d.status === 'pending') && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Setup Guide
              </Typography>
              
              <Stepper activeStep={activeStep} orientation="vertical">
                <Step>
                  <StepLabel>Add </StepLabel>
                  <StepContent>
                    <Typography>added successfully. Proceed to DNS configuration.</Typography>
                    <Button onClick={() => setActiveStep(1)} sx={{ mt: 2 }}>
                      Continue
                    </Button>
                  </StepContent>
                </Step>
                
                <Step>
                  <StepLabel>Configure DNS Records</StepLabel>
                  <StepContent>
                    <Typography gutterBottom>
                      Add the following DNS records to your domain:
                    </Typography>
                    
                    <TableContainer sx={{ mt: 2 }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow>
                            <TableCell>Type</TableCell>
                            <TableCell>Name</TableCell>
                            <TableCell>Value</TableCell>
                            <TableCell>TTL</TableCell>
                            <TableCell width={50}></TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {dnsRecords.map((record, index) => (
                            <TableRow key={index}>
                              <TableCell>{record.type}</TableCell>
                              <TableCell>{record.name}</TableCell>
                              <TableCell>{record.value}</TableCell>
                              <TableCell>{record.ttl}</TableCell>
                              <TableCell>
                                <IconButton
                                  size="small"
                                  onClick={() => copyToClipboard(record.value)}
                                >
                                  <ContentCopy fontSize="small" />
                                </IconButton>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                    
                    <Box sx={{ mt: 2 }}>
                      <Button onClick={() => setActiveStep(2)}>
                        I've Added DNS Records
                      </Button>
                    </Box>
                  </StepContent>
                </Step>
                
                <Step>
                  <StepLabel>Verify </StepLabel>
                  <StepContent>
                    <Typography>
                      Click verify to check if DNS records are properly configured.
                    </Typography>
                    <Alert severity="info" sx={{ mt: 2 }}>
                      DNS propagation can take up to 48 hours. If verification fails, please try again later.
                    </Alert>
                    <Button
                      variant="contained"
                      onClick={() => {
                        const pendingDomain = domains.find(d => d.status === 'pending');
                        if (pendingDomain) {
                          handleVerifyDomain(pendingDomain.id);
                          setActiveStep(3);
                        }
                      }}
                      sx={{ mt: 2 }}
                    >
                      Verify </Button>
                  </StepContent>
                </Step>
                
                <Step>
                  <StepLabel>Activate </StepLabel>
                  <StepContent>
                    <Typography>
                      Your domain is verified! Click activate to start using it.
                    </Typography>
                    <Button
                      variant="contained"
                      color="success"
                      onClick={() => {
                        const verifiedDomain = domains.find(d => d.status === 'verified');
                        if (verifiedDomain) {
                          handleActivateDomain(verifiedDomain.id);
                          setActiveStep(0);
                        }
                      }}
                      sx={{ mt: 2 }}
                    >
                      Activate </Button>
                  </StepContent>
                </Step>
              </Stepper>
            </Paper>
          </Grid>
        )}

        {/* List */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Configured Domains
            </Typography>
            
            <TableContainer>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell></TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>SSL</TableCell>
                    <TableCell>Created</TableCell>
                    <TableCell>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {domains.map((domain) => (
                    <TableRow key={domain.id}>
                      <TableCell>{domain.domain}</TableCell>
                      <TableCell>
                        <Chip
                          icon={getStatusIcon(domain.status)}
                          label={domain.status}
                          size="small"
                          color={domain.status === 'active' ? 'success' : 'default'}
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          icon={<Security fontSize="small" />}
                          label={domain.sslStatus}
                          size="small"
                          color={domain.sslStatus === 'active' ? 'success' : 'default'}
                        />
                      </TableCell>
                      <TableCell>{domain.createdAt}</TableCell>
                      <TableCell>
                        {domain.status === 'pending' && (
                          <Button
                            size="small"
                            onClick={() => handleVerifyDomain(domain.id)}
                          >
                            Verify
                          </Button>
                        )}
                        {domain.status === 'verified' && (
                          <Button
                            size="small"
                            color="success"
                            onClick={() => handleActivateDomain(domain.id)}
                          >
                            Activate
                          </Button>
                        )}
                        <IconButton
                          size="small"
                          color=""
                          onClick={() => handleRemoveDomain(domain.id)}
                        >
                          <Delete />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        {/* Settings */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Settings
            </Typography>
            
            <List>
              <ListItem>
                <ListItemText
                  primary="Enforce SSL"
                  secondary="Redirect all HTTP traffic to HTTPS"
                />
                <ListItemSecondaryAction>
                  <Switch
                    checked={domainSettings.enforceSSL}
                    onChange={(e) => {
                      setDomainSettings(prev => ({ ...prev, enforceSSL: e.target.checked }));
                      onChange();
                    }}
                  />
                </ListItemSecondaryAction>
              </ListItem>
              
              <ListItem>
                <ListItemText
                  primary="Allow Subdomains"
                  secondary="Enable wildcard subdomain support (*.yourdomain.com)"
                />
                <ListItemSecondaryAction>
                  <Switch
                    checked={domainSettings.allowSubdomains}
                    onChange={(e) => {
                      setDomainSettings(prev => ({ ...prev, allowSubdomains: e.target.checked }));
                      onChange();
                    }}
                  />
                </ListItemSecondaryAction>
              </ListItem>
              
              <ListItem>
                <ListItemText
                  primary="Redirect WWW"
                  secondary="Redirect www subdomain to root domain"
                />
                <ListItemSecondaryAction>
                  <Switch
                    checked={domainSettings.redirectWWW}
                    onChange={(e) => {
                      setDomainSettings(prev => ({ ...prev, redirectWWW: e.target.checked }));
                      onChange();
                    }}
                  />
                </ListItemSecondaryAction>
              </ListItem>
            </List>
            
            <TextField
              fullWidth
              multiline
              rows={4}
              label="Custom Headers"
              value={domainSettings.customHeaders}
              onChange={(e) => {
                setDomainSettings(prev => ({ ...prev, customHeaders: e.target.value }));
                onChange();
              }}
              helperText="Add custom HTTP headers (one per line)"
              sx={{ mt: 2 }}
            />
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};
