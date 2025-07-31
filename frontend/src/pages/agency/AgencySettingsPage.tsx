import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Grid,
  Switch,
  Divider,
  Alert,
  Tab,
  Tabs,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Avatar,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  MenuItem } from '@mui/material';
import {
  Business,
  Edit,
  Save,
  Cancel,
  Delete,
  PersonAdd,
  Payment,
  People,
  Link } from '@mui/icons-material';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/hooks/useAuth';

const agencySchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Invalid email address'),
  phone: z.string().optional(),
  website: z.string().url('Invalid URL').optional().or(z.literal('')),
  address: z.string().optional(),
  description: z.string().max(500, 'Description must be less than 500 characters').optional() });

const inviteSchema = z.object({
  email: z.string().email('Invalid email address'),
  role: z.enum(['agency_admin', 'model', 'chatter']),
  message: z.string().optional() });

type AgencyFormData = z.infer<typeof agencySchema>;
type InviteFormData = z.infer<typeof inviteSchema>;

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel = (props: TabPanelProps) => {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`agency-tabpanel-${index}`}
      aria-labelledby={`agency-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const AgencySettingsPage = () => {
  const { user } = useAuth();
  const [tab, setTab] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [apiKeys, setApiKeys] = useState({
    onlyFansApiEnabled: false,
    inflowApiEnabled: false });

  const {
    register: registerAgency,
    handleSubmit: handleAgencySubmit,
    formState: { errors: agencyErrors },
    reset: resetAgency } = useForm<AgencyFormData>({
    resolver: zodResolver(agencySchema),
    defaultValues: {
      name: 'Premium Marketing Agency',
      email: 'contact@agency.com',
      phone: '+1 234 567 8900',
      website: 'https://agency.com',
      address: '123 Business St, New York, NY 10001',
      description: 'Leading OnlyFans marketing agency specializing in growth and monetization.' } });

  const {
    register: registerInvite,
    handleSubmit: handleInviteSubmit,
    formState: { errors: inviteErrors },
    reset: resetInvite } = useForm<InviteFormData>({
    resolver: zodResolver(inviteSchema) });

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTab(newValue);
  };

  const handleAgencyUpdate = async (data: AgencyFormData) => {
    console.log('Agency update:', data);
    setIsEditing(false);
  };

  const handleInvite = async (data: InviteFormData) => {
    console.log('Invite:', data);
    setInviteDialogOpen(false);
    resetInvite();
  };

  const handleApiKeyToggle = (key: keyof typeof apiKeys) => {
    setApiKeys(prev => ({
      ...prev,
      [key]: !prev[key] }));
  };

  // Mock data
  const teamMembers = [
    { id: '1', name: 'John Doe', email: 'john@agency.com', role: 'agency_admin', status: 'active' },
    { id: '2', name: 'Jane Smith', email: 'jane@agency.com', role: 'model', status: 'active' },
    { id: '3', name: 'Mike Johnson', email: 'mike@agency.com', role: 'chatter', status: 'active' },
  ];

  const pendingInvites = [
    { id: '1', email: 'sarah@example.com', role: 'model', sentAt: new Date(Date.now() - 86400000) },
    { id: '2', email: 'tom@example.com', role: 'chatter', sentAt: new Date(Date.now() - 172800000) },
  ];

  const integrations = [
    { name: 'OnlyFans API', description: 'Connect to OnlyFans for automated management', connected: true },
    { name: 'Inflow API', description: 'Advanced analytics and automation', connected: false },
    { name: 'Stripe', description: 'Payment processing', connected: true },
    { name: 'Twilio', description: 'SMS notifications', connected: false },
  ];

  if (!user || !['agency_owner', 'agency_admin'].includes(user.role)) {
    return <Typography>You don't have permission to access this page.</Typography>;
  }

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        Agency </Typography>

      <Card>
        <Tabs value={tab} onChange={handleTabChange}>
          <Tab icon={<Business />} label="General" />
          <Tab icon={<People />} label="Team" />
          <Tab icon={<Payment />} label="Billing" />
          <Tab icon={<Link />} label="Integrations" />
        </Tabs>

        <TabPanel value={tab} index={0}>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
              <Typography variant="h6">Agency Information</Typography>
              {!isEditing ? (
                <Button startIcon={<Edit />} onClick={() => setIsEditing(true)}>
                  Edit
                </Button>
              ) : (
                <Box display="flex" gap={1}>
                  <Button
                    startIcon={<Save />}
                    variant="contained"
                    onClick={handleAgencySubmit(handleAgencyUpdate)}
                  >
                    Save
                  </Button>
                  <Button
                    startIcon={<Cancel />}
                    onClick={() => {
                      setIsEditing(false);
                      resetAgency();
                    }}
                  >
                    Cancel
                  </Button>
                </Box>
              )}
            </Box>

            <form>
              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Agency Name"
                    {...registerAgency('name')}
                    error={!!agencyErrors.name}
                    helperText={agencyErrors.name?.message}
                    disabled={!isEditing}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Contact "
                    {...registerAgency('email')}
                    error={!!agencyErrors.email}
                    helperText={agencyErrors.email?.message}
                    disabled={!isEditing}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Phone"
                    {...registerAgency('phone')}
                    error={!!agencyErrors.phone}
                    helperText={agencyErrors.phone?.message}
                    disabled={!isEditing}
                  />
                </Grid>
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Website"
                    {...registerAgency('website')}
                    error={!!agencyErrors.website}
                    helperText={agencyErrors.website?.message}
                    disabled={!isEditing}
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Address"
                    {...registerAgency('address')}
                    error={!!agencyErrors.address}
                    helperText={agencyErrors.address?.message}
                    disabled={!isEditing}
                  />
                </Grid>
                <Grid item xs={12}>
                  <TextField
                    fullWidth
                    label="Description"
                    multiline
                    rows={4}
                    {...registerAgency('description')}
                    error={!!agencyErrors.description}
                    helperText={agencyErrors.description?.message}
                    disabled={!isEditing}
                  />
                </Grid>
              </Grid>
            </form>

            <Divider sx={{ my: 3 }} />

            <Typography variant="h6" gutterBottom>
              Agency </Typography>
            <List>
              <ListItem>
                <ListItemText
                  primary="Allow models to override chatter claims"
                  secondary="Models can reclaim fans assigned to chatters"
                />
                <ListItemSecondaryAction>
                  <Switch defaultChecked />
                </ListItemSecondaryAction>
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Auto-assign new fans"
                  secondary="Automatically distribute new fans to available chatters"
                />
                <ListItemSecondaryAction>
                  <Switch defaultChecked />
                </ListItemSecondaryAction>
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Require approval for payouts"
                  secondary="Agency admin must approve all payout requests"
                />
                <ListItemSecondaryAction>
                  <Switch />
                </ListItemSecondaryAction>
              </ListItem>
            </List>
          </CardContent>
        </TabPanel>

        <TabPanel value={tab} index={1}>
          <CardContent>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
              <Typography variant="h6">Team Members</Typography>
              <Button
                startIcon={<PersonAdd />}
                variant="contained"
                onClick={() => setInviteDialogOpen(true)}
              >
                Invite Member
              </Button>
            </Box>

            <List>
              {teamMembers.map((member) => (
                <ListItem key={member.id}>
                  <ListItemAvatar>
                    <Avatar>{member.name.charAt(0)}</Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={member.name}
                    secondary={member.email}
                  />
                  <Chip
                    label={member.role.replace('_', ' ')}
                    size="small"
                    color={member.role === 'agency_admin' ? 'primary' : 'default'}
                    sx={{ mr: 2 }}
                  />
                  <ListItemSecondaryAction>
                    <IconButton edge="end">
                      <Delete />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>

            {pendingInvites.length > 0 && (
              <>
                <Divider sx={{ my: 3 }} />
                <Typography variant="h6" gutterBottom>
                  Pending Invitations
                </Typography>
                <List>
                  {pendingInvites.map((invite) => (
                    <ListItem key={invite.id}>
                      <ListItemText
                        primary={invite.email}
                        secondary={`Invited ${Math.floor((Date.now() - invite.sentAt.getTime()) / 86400000)} days ago`}
                      />
                      <Chip
                        label={invite.role.replace('_', ' ')}
                        size="small"
                        sx={{ mr: 2 }}
                      />
                      <ListItemSecondaryAction>
                        <Button size="small" sx={{ mr: 1 }}>
                          Resend
                        </Button>
                        <IconButton edge="end">
                          <Cancel />
                        </IconButton>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              </>
            )}
          </CardContent>
        </TabPanel>

        <TabPanel value={tab} index={2}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Subscription Plan
            </Typography>
            <Card variant="outlined" sx={{ mb: 3 }}>
              <CardContent>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Typography variant="h5">Professional Plan</Typography>
                    <Typography variant="body2" color="textSecondary">
                      $299/month • Up to 50 models
                    </Typography>
                  </Box>
                  <Button variant="outlined">Upgrade Plan</Button>
                </Box>
              </CardContent>
            </Card>

            <Typography variant="h6" gutterBottom>
              Usage
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">
                      Active Models
                    </Typography>
                    <Typography variant="h4">
                      23 / 50
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">
                      Active Chatters
                    </Typography>
                    <Typography variant="h4">
                      12 / ∞
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} sm={4}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="body2" color="textSecondary">
                      Storage Used
                    </Typography>
                    <Typography variant="h4">
                      45 GB
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            <Divider sx={{ my: 3 }} />

            <Typography variant="h6" gutterBottom>
              Payment Method
            </Typography>
            <List>
              <ListItem>
                <ListItemText
                  primary="•••• •••• •••• 4242"
                  secondary="Expires 12/24"
                />
                <ListItemSecondaryAction>
                  <Button>Update</Button>
                </ListItemSecondaryAction>
              </ListItem>
            </List>
          </CardContent>
        </TabPanel>

        <TabPanel value={tab} index={3}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              API Integrations
            </Typography>
            <List>
              {integrations.map((integration) => (
                <ListItem key={integration.name}>
                  <ListItemText
                    primary={integration.name}
                    secondary={integration.description}
                  />
                  <ListItemSecondaryAction>
                    <Button
                      variant={integration.connected ? 'outlined' : 'contained'}
                      color={integration.connected ? 'error' : 'primary'}
                    >
                      {integration.connected ? 'Disconnect' : 'Connect'}
                    </Button>
                  </ListItemSecondaryAction>
                </ListItem>
              ))}
            </List>

            <Divider sx={{ my: 3 }} />

            <Typography variant="h6" gutterBottom>
              API Keys
            </Typography>
            <Alert severity="warning" sx={{ mb: 2 }}>
              Keep your API keys secure. Never share them publicly.
            </Alert>
            <List>
              <ListItem>
                <ListItemText
                  primary="OnlyFans API Key"
                  secondary={apiKeys.onlyFansApiEnabled ? '••••••••••••••••' : 'Not configured'}
                />
                <ListItemSecondaryAction>
                  <Button
                    onClick={() => handleApiKeyToggle('onlyFansApiEnabled')}
                  >
                    {apiKeys.onlyFansApiEnabled ? 'Regenerate' : 'Configure'}
                  </Button>
                </ListItemSecondaryAction>
              </ListItem>
              <ListItem>
                <ListItemText
                  primary="Inflow API Key"
                  secondary={apiKeys.inflowApiEnabled ? '••••••••••••••••' : 'Not configured'}
                />
                <ListItemSecondaryAction>
                  <Button
                    onClick={() => handleApiKeyToggle('inflowApiEnabled')}
                  >
                    {apiKeys.inflowApiEnabled ? 'Regenerate' : 'Configure'}
                  </Button>
                </ListItemSecondaryAction>
              </ListItem>
            </List>
          </CardContent>
        </TabPanel>
      </Card>

      <Dialog open={inviteDialogOpen} onClose={() => setInviteDialogOpen(false)} maxWidth="sm" fullWidth>
        <form onSubmit={handleInviteSubmit(handleInvite)}>
          <DialogTitle>Invite Team Member</DialogTitle>
          <DialogContent>
            <Box display="flex" flexDirection="column" gap={2} pt={1}>
              <TextField
                fullWidth
                label="Address"
                {...registerInvite('email')}
                error={!!inviteErrors.email}
                helperText={inviteErrors.email?.message}
              />
              <TextField
                select
                fullWidth
                label="Role"
                {...registerInvite('role')}
                error={!!inviteErrors.role}
                helperText={inviteErrors.role?.message}
                defaultValue="model"
              >
                <MenuItem value="agency_admin">Agency Admin</MenuItem>
                <MenuItem value="model">Model</MenuItem>
                <MenuItem value="chatter">Chatter</MenuItem>
              </TextField>
              <TextField
                fullWidth
                label="Personal Message (Optional)"
                multiline
                rows={3}
                {...registerInvite('message')}
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setInviteDialogOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained">
              Send Invitation
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  );
};

export default AgencySettingsPage;
