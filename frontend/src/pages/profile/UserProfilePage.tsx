import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  Avatar,
  Button,
  TextField,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Switch,
  Alert,
  Tab,
  Tabs,
  Paper,
  IconButton,
  Chip,
} from '@mui/material';
import {
  Edit,
  Save,
  Cancel,
  Lock,
  Notifications,
  Security,
  History,
  PhotoCamera,
} from '@mui/icons-material';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/hooks/useAuth';
import { useUpdateUser } from '@/hooks/useUsers';
import { format } from 'date-fns';

const profileSchema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Invalid email address'),
  phone: z.string().optional(),
  bio: z.string().max(500, 'Bio must be less than 500 characters').optional(),
});

const passwordSchema = z.object({
  current_password: z.string().min(8, 'Password must be at least 8 characters'),
  new_password: z.string().min(8, 'Password must be at least 8 characters'),
  confirm_password: z.string().min(8, 'Password must be at least 8 characters'),
}).refine((data) => data.new_password === data.confirm_password, {
  message: "Passwords don't match",
  path: ["confirm_password"],
});

type ProfileFormData = z.infer<typeof profileSchema>;
type PasswordFormData = z.infer<typeof passwordSchema>;

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
      id={`profile-tabpanel-${index}`}
      aria-labelledby={`profile-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
};

const UserProfilePage = () => {
  const { user, checkAuth } = useAuth();
  const updateUser = useUpdateUser();
  const [tab, setTab] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [notifications, setNotifications] = useState({
    email: true,
    push: false,
    sms: false,
    marketing: false,
  });

  const {
    register: registerProfile,
    handleSubmit: handleProfileSubmit,
    formState: { errors: profileErrors },
    reset: resetProfile,
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: user?.full_name || '',
      email: user?.email || '',
      phone: user?.phone || '',
      bio: user?.bio || '',
    },
  });

  const {
    register: registerPassword,
    handleSubmit: handlePasswordSubmit,
    formState: { errors: passwordErrors },
    reset: resetPassword,
  } = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
  });

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setTab(newValue);
  };

  const handleProfileUpdate = async (data: ProfileFormData) => {
    if (!user) return;
    
    await updateUser.mutateAsync({
      userId: user.id,
      data,
    });
    await checkAuth();
    setIsEditing(false);
  };

  const handlePasswordUpdate = async (data: PasswordFormData) => {
    if (!user) return;
    
    // API call to update password would go here
    console.log('Password update:', data);
    resetPassword();
  };

  const handleNotificationChange = (key: keyof typeof notifications) => {
    setNotifications(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleAvatarUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Handle avatar upload
      console.log('Avatar upload:', file);
    }
  };

  if (!user) {
    return <Typography>Loading...</Typography>;
  }

  const loginHistory = [
    { date: new Date(), ip: '192.168.1.1', device: 'Chrome on Windows', location: 'New York, US' },
    { date: new Date(Date.now() - 86400000), ip: '192.168.1.2', device: 'Safari on iPhone', location: 'New York, US' },
    { date: new Date(Date.now() - 172800000), ip: '192.168.1.1', device: 'Chrome on Windows', location: 'New York, US' },
  ];

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3 }}>
        My Profile
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Box display="flex" flexDirection="column" alignItems="center">
                <Box position="relative">
                  <Avatar
                    src={user.avatar}
                    sx={{ width: 120, height: 120, mb: 2 }}
                  >
                    {user.full_name.charAt(0)}
                  </Avatar>
                  <input
                    accept="image/*"
                    type="file"
                    id="avatar-upload"
                    hidden
                    onChange={handleAvatarUpload}
                  />
                  <label htmlFor="avatar-upload">
                    <IconButton
                      component="span"
                      sx={{
                        position: 'absolute',
                        bottom: 0,
                        right: 0,
                        backgroundColor: 'background.paper',
                      }}
                    >
                      <PhotoCamera />
                    </IconButton>
                  </label>
                </Box>
                <Typography variant="h6">{user.full_name}</Typography>
                <Typography variant="body2" color="textSecondary">
                  {user.email}
                </Typography>
                <Chip
                  label={user.role.replace('_', ' ')}
                  size="small"
                  color="primary"
                  sx={{ mt: 1 }}
                />
              </Box>
              <Divider sx={{ my: 2 }} />
              <List dense>
                <ListItem>
                  <ListItemText
                    primary="Member Since"
                    secondary={format(new Date(user.created_at), 'MMMM d, yyyy')}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Last Login"
                    secondary={format(new Date(user.last_login_at || Date.now()), 'MMMM d, yyyy h:mm a')}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Status"
                    secondary={
                      <Chip
                        label={user.is_active ? 'Active' : 'Inactive'}
                        size="small"
                        color={user.is_active ? 'success' : 'default'}
                      />
                    }
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper>
            <Tabs value={tab} onChange={handleTabChange}>
              <Tab icon={<Edit />} label="Profile" />
              <Tab icon={<Lock />} label="Security" />
              <Tab icon={<Notifications />} label="Notifications" />
              <Tab icon={<History />} label="Activity" />
            </Tabs>

            <TabPanel value={tab} index={0}>
              <Box px={3}>
                <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                  <Typography variant="h6">Profile Information</Typography>
                  {!isEditing ? (
                    <Button
                      startIcon={<Edit />}
                      onClick={() => setIsEditing(true)}
                    >
                      Edit Profile
                    </Button>
                  ) : (
                    <Box display="flex" gap={1}>
                      <Button
                        startIcon={<Save />}
                        variant="contained"
                        onClick={handleProfileSubmit(handleProfileUpdate)}
                      >
                        Save
                      </Button>
                      <Button
                        startIcon={<Cancel />}
                        onClick={() => {
                          setIsEditing(false);
                          resetProfile();
                        }}
                      >
                        Cancel
                      </Button>
                    </Box>
                  )}
                </Box>

                <form>
                  <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Full Name"
                        {...registerProfile('full_name')}
                        error={!!profileErrors.full_name}
                        helperText={profileErrors.full_name?.message}
                        disabled={!isEditing}
                      />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Email"
                        {...registerProfile('email')}
                        error={!!profileErrors.email}
                        helperText={profileErrors.email?.message}
                        disabled={!isEditing}
                      />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        fullWidth
                        label="Phone"
                        {...registerProfile('phone')}
                        error={!!profileErrors.phone}
                        helperText={profileErrors.phone?.message}
                        disabled={!isEditing}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        label="Bio"
                        multiline
                        rows={4}
                        {...registerProfile('bio')}
                        error={!!profileErrors.bio}
                        helperText={profileErrors.bio?.message}
                        disabled={!isEditing}
                      />
                    </Grid>
                  </Grid>
                </form>
              </Box>
            </TabPanel>

            <TabPanel value={tab} index={1}>
              <Box px={3}>
                <Typography variant="h6" gutterBottom>
                  Change Password
                </Typography>
                <form onSubmit={handlePasswordSubmit(handlePasswordUpdate)}>
                  <Grid container spacing={2}>
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        type="password"
                        label="Current Password"
                        {...registerPassword('current_password')}
                        error={!!passwordErrors.current_password}
                        helperText={passwordErrors.current_password?.message}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        type="password"
                        label="New Password"
                        {...registerPassword('new_password')}
                        error={!!passwordErrors.new_password}
                        helperText={passwordErrors.new_password?.message}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <TextField
                        fullWidth
                        type="password"
                        label="Confirm New Password"
                        {...registerPassword('confirm_password')}
                        error={!!passwordErrors.confirm_password}
                        helperText={passwordErrors.confirm_password?.message}
                      />
                    </Grid>
                    <Grid item xs={12}>
                      <Button
                        type="submit"
                        variant="contained"
                        startIcon={<Lock />}
                      >
                        Update Password
                      </Button>
                    </Grid>
                  </Grid>
                </form>

                <Divider sx={{ my: 3 }} />

                <Typography variant="h6" gutterBottom>
                  Two-Factor Authentication
                </Typography>
                <Alert severity="info" sx={{ mb: 2 }}>
                  Protect your account with an extra layer of security.
                </Alert>
                <Button variant="outlined" startIcon={<Security />}>
                  Enable 2FA
                </Button>
              </Box>
            </TabPanel>

            <TabPanel value={tab} index={2}>
              <Box px={3}>
                <Typography variant="h6" gutterBottom>
                  Notification Preferences
                </Typography>
                <List>
                  <ListItem>
                    <ListItemText
                      primary="Email Notifications"
                      secondary="Receive updates and alerts via email"
                    />
                    <ListItemSecondaryAction>
                      <Switch
                        checked={notifications.email}
                        onChange={() => handleNotificationChange('email')}
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Push Notifications"
                      secondary="Receive notifications on your device"
                    />
                    <ListItemSecondaryAction>
                      <Switch
                        checked={notifications.push}
                        onChange={() => handleNotificationChange('push')}
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="SMS Notifications"
                      secondary="Receive text messages for important updates"
                    />
                    <ListItemSecondaryAction>
                      <Switch
                        checked={notifications.sms}
                        onChange={() => handleNotificationChange('sms')}
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                  <ListItem>
                    <ListItemText
                      primary="Marketing Emails"
                      secondary="Receive news and promotional content"
                    />
                    <ListItemSecondaryAction>
                      <Switch
                        checked={notifications.marketing}
                        onChange={() => handleNotificationChange('marketing')}
                      />
                    </ListItemSecondaryAction>
                  </ListItem>
                </List>
              </Box>
            </TabPanel>

            <TabPanel value={tab} index={3}>
              <Box px={3}>
                <Typography variant="h6" gutterBottom>
                  Login History
                </Typography>
                <List>
                  {loginHistory.map((item, index) => (
                    <ListItem key={index} divider>
                      <ListItemText
                        primary={item.device}
                        secondary={
                          <>
                            {format(item.date, 'MMMM d, yyyy h:mm a')} • {item.location}
                            <br />
                            IP: {item.ip}
                          </>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </Box>
            </TabPanel>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default UserProfilePage;