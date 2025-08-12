import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  Card,
  CardContent,
  Grid,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Paper,
  Chip,
  IconButton,
  TextField,
  InputAdornment,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction,
  Switch,
  FormControlLabel,
  Tabs,
  Tab,
  Tooltip,
  LinearProgress,
  Avatar,
  Divider,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Download as DownloadIcon,
  Upload as UploadIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Block as BlockIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
  Policy as PolicyIcon,
  Security as SecurityIcon,
  Person as PersonIcon,
  Apps as AppsIcon,
  AccessTime as AccessTimeIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon,
  Add as AddIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow } from 'date-fns';
import { useConsentManagement } from '../../hooks/useConsentManagement';

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
      id={`consent-tabpanel-${index}`}
      aria-labelledby={`consent-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
};

interface ConsentRecord {
  id: string;
  userId: string;
  userName: string;
  userEmail: string;
  clientId: string;
  clientName: string;
  scopes: string[];
  grantedAt: string;
  expiresAt?: string;
  revokedAt?: string;
  status: 'active' | 'expired' | 'revoked';
  ipAddress: string;
  userAgent: string;
}

interface ConsentPolicy {
  id: string;
  name: string;
  description: string;
  rules: {
    autoApprove: boolean;
    requireReauth: boolean;
    maxDuration: number; // days
    allowedScopes: string[];
    deniedScopes: string[];
    clientWhitelist: string[];
    clientBlacklist: string[];
  };
  createdAt: string;
  updatedAt: string;
  isActive: boolean;
}

interface ConsentTemplate {
  id: string;
  name: string;
  description: string;
  content: {
    title: string;
    message: string;
    scopes: {
      scope: string;
      description: string;
      required: boolean;
    }[];
    customCSS?: string;
  };
  language: string;
  isDefault: boolean;
}

const ConsentManagement: React.FC = () => {
  const {
    getConsentRecords,
    getConsentPolicies,
    getConsentTemplates,
    revokeConsent,
    updatePolicy,
    updateTemplate,
    deletePolicy,
    deleteTemplate,
    exportConsents,
  } = useConsentManagement();

  const [activeTab, setActiveTab] = useState(0);
  const [loading, setLoading] = useState(false);
  
  // Consent Records State
  const [consentRecords, setConsentRecords] = useState<ConsentRecord[]>([]);
  const [recordsPage, setRecordsPage] = useState(0);
  const [recordsRowsPerPage, setRecordsRowsPerPage] = useState(25);
  const [recordsSearchQuery, setRecordsSearchQuery] = useState('');
  const [recordsFilter, setRecordsFilter] = useState<'all' | 'active' | 'expired' | 'revoked'>('all');
  
  // Policies State
  const [policies, setPolicies] = useState<ConsentPolicy[]>([]);
  const [selectedPolicy, setSelectedPolicy] = useState<ConsentPolicy | null>(null);
  const [showPolicyDialog, setShowPolicyDialog] = useState(false);
  
  // Templates State
  const [templates, setTemplates] = useState<ConsentTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<ConsentTemplate | null>(null);
  const [showTemplateDialog, setShowTemplateDialog] = useState(false);
  const [showTemplatePreview, setShowTemplatePreview] = useState(false);

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    setLoading(true);
    try {
      switch (activeTab) {
        case 0:
          const records = await getConsentRecords();
          setConsentRecords(records);
          break;
        case 1:
          const policiesData = await getConsentPolicies();
          setPolicies(policiesData);
          break;
        case 2:
          const templatesData = await getConsentTemplates();
          setTemplates(templatesData);
          break;
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  const handleRevokeConsent = async (recordId: string) => {
    await revokeConsent(recordId);
    fetchData();
  };

  const handleExportConsents = async () => {
    const csv = await exportConsents();
    downloadCSV(csv, `consents-${format(new Date(), 'yyyy-MM-dd')}.csv`);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'success';
      case 'expired': return 'warning';
      case 'revoked': return 'error';
      default: return 'default';
    }
  };

  // Mock data for demonstration
  const mockRecords: ConsentRecord[] = [
    {
      id: '1',
      userId: 'user_1',
      userName: 'John Doe',
      userEmail: 'john@example.com',
      clientId: 'client_1',
      clientName: 'Analytics Dashboard',
      scopes: ['openid', 'profile', 'email', 'api:read'],
      grantedAt: new Date(Date.now() - 30 * 86400000).toISOString(),
      status: 'active',
      ipAddress: '192.168.1.1',
      userAgent: 'Mozilla/5.0 Chrome/120.0',
    },
    {
      id: '2',
      userId: 'user_2',
      userName: 'Jane Smith',
      userEmail: 'jane@example.com',
      clientId: 'client_2',
      clientName: 'Mobile App',
      scopes: ['openid', 'profile'],
      grantedAt: new Date(Date.now() - 60 * 86400000).toISOString(),
      expiresAt: new Date(Date.now() - 86400000).toISOString(),
      status: 'expired',
      ipAddress: '10.0.0.1',
      userAgent: 'Mobile App iOS/17.0',
    },
    {
      id: '3',
      userId: 'user_3',
      userName: 'Bob Johnson',
      userEmail: 'bob@example.com',
      clientId: 'client_1',
      clientName: 'Analytics Dashboard',
      scopes: ['openid', 'profile', 'email', 'api:read', 'api:write'],
      grantedAt: new Date(Date.now() - 90 * 86400000).toISOString(),
      revokedAt: new Date(Date.now() - 7 * 86400000).toISOString(),
      status: 'revoked',
      ipAddress: '172.16.0.1',
      userAgent: 'Mozilla/5.0 Firefox/121.0',
    },
  ];

  const mockPolicies: ConsentPolicy[] = [
    {
      id: '1',
      name: 'Default Policy',
      description: 'Standard consent policy for all applications',
      rules: {
        autoApprove: false,
        requireReauth: false,
        maxDuration: 365,
        allowedScopes: ['openid', 'profile', 'email'],
        deniedScopes: ['api:delete'],
        clientWhitelist: [],
        clientBlacklist: [],
      },
      createdAt: new Date(Date.now() - 180 * 86400000).toISOString(),
      updatedAt: new Date(Date.now() - 30 * 86400000).toISOString(),
      isActive: true,
    },
    {
      id: '2',
      name: 'Trusted Apps Policy',
      description: 'Auto-approve policy for verified applications',
      rules: {
        autoApprove: true,
        requireReauth: false,
        maxDuration: 730,
        allowedScopes: ['openid', 'profile', 'email', 'api:read'],
        deniedScopes: ['api:delete'],
        clientWhitelist: ['client_1', 'client_2'],
        clientBlacklist: [],
      },
      createdAt: new Date(Date.now() - 90 * 86400000).toISOString(),
      updatedAt: new Date(Date.now() - 7 * 86400000).toISOString(),
      isActive: true,
    },
  ];

  const mockTemplates: ConsentTemplate[] = [
    {
      id: '1',
      name: 'Default Template',
      description: 'Standard consent screen template',
      content: {
        title: '{app_name} wants to access your account',
        message: 'This application will be able to:',
        scopes: [
          { scope: 'openid', description: 'Verify your identity', required: true },
          { scope: 'profile', description: 'Access your profile information', required: false },
          { scope: 'email', description: 'Access your email address', required: false },
        ],
      },
      language: 'en',
      isDefault: true,
    },
    {
      id: '2',
      name: 'Minimal Template',
      description: 'Simplified consent screen for trusted apps',
      content: {
        title: 'Grant access to {app_name}',
        message: 'Review the requested permissions:',
        scopes: [],
      },
      language: 'en',
      isDefault: false,
    },
  ];

  const displayRecords = consentRecords.length > 0 ? consentRecords : mockRecords;
  const displayPolicies = policies.length > 0 ? policies : mockPolicies;
  const displayTemplates = templates.length > 0 ? templates : mockTemplates;

  const filteredRecords = displayRecords.filter(record => {
    const matchesSearch = !recordsSearchQuery ||
      record.userName.toLowerCase().includes(recordsSearchQuery.toLowerCase()) ||
      record.userEmail.toLowerCase().includes(recordsSearchQuery.toLowerCase()) ||
      record.clientName.toLowerCase().includes(recordsSearchQuery.toLowerCase());
    
    const matchesFilter = recordsFilter === 'all' || record.status === recordsFilter;
    
    return matchesSearch && matchesFilter;
  });

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Consent Management</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchData}
          >
            Refresh
          </Button>
          <Button
            variant="contained"
            startIcon={<DownloadIcon />}
            onClick={handleExportConsents}
          >
            Export
          </Button>
        </Box>
      </Box>

      {/* Statistics */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h4">
                {displayRecords.filter(r => r.status === 'active').length}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Active Consents
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h4">
                {displayPolicies.filter(p => p.isActive).length}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Active Policies
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h4">
                {displayTemplates.length}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Templates
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="h4">
                {new Set(displayRecords.map(r => r.userId)).size}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Unique Users
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Card>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={activeTab} onChange={handleTabChange}>
            <Tab label="Consent Records" icon={<CheckCircleIcon />} iconPosition="start" />
            <Tab label="Policies" icon={<PolicyIcon />} iconPosition="start" />
            <Tab label="Templates" icon={<AppsIcon />} iconPosition="start" />
          </Tabs>
        </Box>

        {loading && <LinearProgress />}

        {/* Consent Records Tab */}
        <TabPanel value={activeTab} index={0}>
          <Box sx={{ p: 2 }}>
            {/* Filters */}
            <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
              <TextField
                placeholder="Search by user or client..."
                value={recordsSearchQuery}
                onChange={(e) => setRecordsSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
                sx={{ flexGrow: 1 }}
              />
              <FormControl sx={{ minWidth: 150 }}>
                <Select
                  value={recordsFilter}
                  onChange={(e) => setRecordsFilter(e.target.value as any)}
                >
                  <MenuItem value="all">All Records</MenuItem>
                  <MenuItem value="active">Active</MenuItem>
                  <MenuItem value="expired">Expired</MenuItem>
                  <MenuItem value="revoked">Revoked</MenuItem>
                </Select>
              </FormControl>
            </Box>

            {/* Table */}
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>User</TableCell>
                    <TableCell>Client</TableCell>
                    <TableCell>Scopes</TableCell>
                    <TableCell>Granted</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredRecords
                    .slice(recordsPage * recordsRowsPerPage, recordsPage * recordsRowsPerPage + recordsRowsPerPage)
                    .map((record) => (
                      <TableRow key={record.id}>
                        <TableCell>
                          <Box>
                            <Typography variant="body2" fontWeight="medium">
                              {record.userName}
                            </Typography>
                            <Typography variant="caption" color="textSecondary">
                              {record.userEmail}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <AppsIcon fontSize="small" color="action" />
                            <Typography variant="body2">
                              {record.clientName}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                            {record.scopes.slice(0, 3).map((scope) => (
                              <Chip key={scope} label={scope} size="small" variant="outlined" />
                            ))}
                            {record.scopes.length > 3 && (
                              <Chip label={`+${record.scopes.length - 3}`} size="small" />
                            )}
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Tooltip title={format(new Date(record.grantedAt), 'PPpp')}>
                            <Typography variant="body2">
                              {formatDistanceToNow(new Date(record.grantedAt), { addSuffix: true })}
                            </Typography>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <Chip
                            label={record.status}
                            size="small"
                            color={getStatusColor(record.status)}
                          />
                        </TableCell>
                        <TableCell align="right">
                          <Tooltip title="View Details">
                            <IconButton size="small">
                              <InfoIcon />
                            </IconButton>
                          </Tooltip>
                          {record.status === 'active' && (
                            <Tooltip title="Revoke Consent">
                              <IconButton
                                size="small"
                                onClick={() => handleRevokeConsent(record.id)}
                              >
                                <BlockIcon />
                              </IconButton>
                            </Tooltip>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </TableContainer>

            <TablePagination
              rowsPerPageOptions={[10, 25, 50, 100]}
              component="div"
              count={filteredRecords.length}
              rowsPerPage={recordsRowsPerPage}
              page={recordsPage}
              onPageChange={(_, newPage) => setRecordsPage(newPage)}
              onRowsPerPageChange={(e) => {
                setRecordsRowsPerPage(parseInt(e.target.value, 10));
                setRecordsPage(0);
              }}
            />
          </Box>
        </TabPanel>

        {/* Policies Tab */}
        <TabPanel value={activeTab} index={1}>
          <Box sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 3 }}>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => {
                  setSelectedPolicy(null);
                  setShowPolicyDialog(true);
                }}
              >
                Create Policy
              </Button>
            </Box>

            <Grid container spacing={3}>
              {displayPolicies.map((policy) => (
                <Grid item xs={12} md={6} key={policy.id}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                        <Box>
                          <Typography variant="h6">{policy.name}</Typography>
                          <Typography variant="body2" color="textSecondary">
                            {policy.description}
                          </Typography>
                        </Box>
                        <Chip
                          label={policy.isActive ? 'Active' : 'Inactive'}
                          color={policy.isActive ? 'success' : 'default'}
                          size="small"
                        />
                      </Box>

                      <List dense>
                        <ListItem disableGutters>
                          <ListItemIcon sx={{ minWidth: 40 }}>
                            {policy.rules.autoApprove ? <CheckCircleIcon color="success" /> : <BlockIcon color="action" />}
                          </ListItemIcon>
                          <ListItemText primary="Auto-approve" secondary={policy.rules.autoApprove ? 'Enabled' : 'Disabled'} />
                        </ListItem>
                        <ListItem disableGutters>
                          <ListItemIcon sx={{ minWidth: 40 }}>
                            <AccessTimeIcon />
                          </ListItemIcon>
                          <ListItemText primary="Max Duration" secondary={`${policy.rules.maxDuration} days`} />
                        </ListItem>
                        <ListItem disableGutters>
                          <ListItemIcon sx={{ minWidth: 40 }}>
                            <SecurityIcon />
                          </ListItemIcon>
                          <ListItemText
                            primary="Allowed Scopes"
                            secondary={`${policy.rules.allowedScopes.length} scope(s)`}
                          />
                        </ListItem>
                      </List>

                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                        <IconButton
                          size="small"
                          onClick={() => {
                            setSelectedPolicy(policy);
                            setShowPolicyDialog(true);
                          }}
                        >
                          <EditIcon />
                        </IconButton>
                        <IconButton size="small" color="error">
                          <DeleteIcon />
                        </IconButton>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        </TabPanel>

        {/* Templates Tab */}
        <TabPanel value={activeTab} index={2}>
          <Box sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 3 }}>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => {
                  setSelectedTemplate(null);
                  setShowTemplateDialog(true);
                }}
              >
                Create Template
              </Button>
            </Box>

            <Grid container spacing={3}>
              {displayTemplates.map((template) => (
                <Grid item xs={12} md={6} key={template.id}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                        <Box>
                          <Typography variant="h6">{template.name}</Typography>
                          <Typography variant="body2" color="textSecondary">
                            {template.description}
                          </Typography>
                        </Box>
                        {template.isDefault && (
                          <Chip label="Default" color="primary" size="small" />
                        )}
                      </Box>

                      <Box sx={{ mb: 2 }}>
                        <Typography variant="body2" color="textSecondary" gutterBottom>
                          Title Template:
                        </Typography>
                        <Typography variant="body2" fontFamily="monospace" sx={{ p: 1, bgcolor: 'grey.100', borderRadius: 1 }}>
                          {template.content.title}
                        </Typography>
                      </Box>

                      <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip label={`Language: ${template.language}`} size="small" variant="outlined" />
                        <Chip label={`${template.content.scopes.length} scopes`} size="small" variant="outlined" />
                      </Box>

                      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2, gap: 1 }}>
                        <Button
                          size="small"
                          onClick={() => {
                            setSelectedTemplate(template);
                            setShowTemplatePreview(true);
                          }}
                        >
                          Preview
                        </Button>
                        <IconButton
                          size="small"
                          onClick={() => {
                            setSelectedTemplate(template);
                            setShowTemplateDialog(true);
                          }}
                        >
                          <EditIcon />
                        </IconButton>
                        <IconButton size="small" color="error">
                          <DeleteIcon />
                        </IconButton>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        </TabPanel>
      </Card>

      {/* Policy Dialog */}
      <Dialog open={showPolicyDialog} onClose={() => setShowPolicyDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {selectedPolicy ? 'Edit Policy' : 'Create Policy'}
        </DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Policy Name"
            defaultValue={selectedPolicy?.name}
            sx={{ mt: 2, mb: 2 }}
          />
          <TextField
            fullWidth
            label="Description"
            multiline
            rows={2}
            defaultValue={selectedPolicy?.description}
            sx={{ mb: 2 }}
          />
          <FormControlLabel
            control={<Switch defaultChecked={selectedPolicy?.rules.autoApprove} />}
            label="Auto-approve consents"
          />
          <FormControlLabel
            control={<Switch defaultChecked={selectedPolicy?.rules.requireReauth} />}
            label="Require re-authentication"
          />
          <TextField
            fullWidth
            type="number"
            label="Max Duration (days)"
            defaultValue={selectedPolicy?.rules.maxDuration || 365}
            sx={{ mt: 2 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowPolicyDialog(false)}>Cancel</Button>
          <Button variant="contained">Save</Button>
        </DialogActions>
      </Dialog>

      {/* Template Dialog */}
      <Dialog open={showTemplateDialog} onClose={() => setShowTemplateDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {selectedTemplate ? 'Edit Template' : 'Create Template'}
        </DialogTitle>
        <DialogContent>
          <TextField
            fullWidth
            label="Template Name"
            defaultValue={selectedTemplate?.name}
            sx={{ mt: 2, mb: 2 }}
          />
          <TextField
            fullWidth
            label="Description"
            multiline
            rows={2}
            defaultValue={selectedTemplate?.description}
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Title Template"
            defaultValue={selectedTemplate?.content.title}
            helperText="Use {app_name} for the application name"
            sx={{ mb: 2 }}
          />
          <TextField
            fullWidth
            label="Message"
            multiline
            rows={2}
            defaultValue={selectedTemplate?.content.message}
            sx={{ mb: 2 }}
          />
          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Language</InputLabel>
            <Select defaultValue={selectedTemplate?.language || 'en'}>
              <MenuItem value="en">English</MenuItem>
              <MenuItem value="es">Spanish</MenuItem>
              <MenuItem value="fr">French</MenuItem>
              <MenuItem value="de">German</MenuItem>
            </Select>
          </FormControl>
          <FormControlLabel
            control={<Switch defaultChecked={selectedTemplate?.isDefault} />}
            label="Set as default template"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowTemplateDialog(false)}>Cancel</Button>
          <Button variant="contained">Save</Button>
        </DialogActions>
      </Dialog>

      {/* Template Preview Dialog */}
      <Dialog open={showTemplatePreview} onClose={() => setShowTemplatePreview(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Template Preview</DialogTitle>
        <DialogContent>
          {selectedTemplate && (
            <Box sx={{ p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
              <Typography variant="h6" gutterBottom>
                {selectedTemplate.content.title.replace('{app_name}', 'Example App')}
              </Typography>
              <Typography variant="body2" paragraph>
                {selectedTemplate.content.message}
              </Typography>
              <List>
                {selectedTemplate.content.scopes.map((scope) => (
                  <ListItem key={scope.scope}>
                    <ListItemIcon>
                      <CheckCircleIcon color={scope.required ? 'primary' : 'action'} />
                    </ListItemIcon>
                    <ListItemText
                      primary={scope.description}
                      secondary={scope.required ? 'Required' : 'Optional'}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowTemplatePreview(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

// Helper function
const downloadCSV = (csv: string, filename: string): void => {
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
};

export default ConsentManagement;