import { 
  AppBar, 
  Toolbar, 
  IconButton, 
  Typography, 
  Box, 
  Avatar, 
  Menu, 
  MenuItem, 
  Badge,
  Button,
  useTheme,
  useMediaQuery,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider
} from '@mui/material';
import { 
  Menu as MenuIcon, 
  Notifications, 
  AccountCircle, 
  Dashboard, 
  People, 
  Person, 
  Chat, 
  Analytics, 
  AttachMoney, 
  Settings, 
  Business, 
  AdminPanelSettings, 
  CloudSync, 
  Group, 
  Assessment,
  Close
} from '@mui/icons-material';
import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { UserRole } from '@/types/auth';

interface NavItem {
  text: string;
  icon: React.ReactNode;
  path: string;
  roles?: UserRole[];
}

const navItems: NavItem[] = [
  {
    text: 'Dashboard',
    icon: <Dashboard />,
    path: '/dashboard',
  },
  {
    text: 'Agencies',
    icon: <Business />,
    path: '/dashboard/agencies',
    roles: [UserRole.SUPER_ADMIN],
  },
  {
    text: 'Users',
    icon: <People />,
    path: '/dashboard/users',
    roles: [UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN], // Removed SUPER_ADMIN
  },
  {
    text: 'Model Overview',
    icon: <Person />,
    path: '/dashboard/models',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN, UserRole.MODEL],
  },
  {
    text: 'Chat',
    icon: <Chat />,
    path: '/dashboard/chat',
    roles: [UserRole.MODEL, UserRole.CHATTER],
  },
  {
    text: 'Analytics',
    icon: <Analytics />,
    path: '/dashboard/analytics',
  },
  {
    text: 'User Management',
    icon: <AdminPanelSettings />,
    path: '/dashboard/admin/users',
    roles: [UserRole.SUPER_ADMIN],
  },
  {
    text: 'Reports',
    icon: <Assessment />,
    path: '/dashboard/reports',
  },
  {
    text: 'Data Sync',
    icon: <CloudSync />,
    path: '/dashboard/sync',
    roles: [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN],
  },
  {
    text: 'Financial',
    icon: <AttachMoney />,
    path: '/dashboard/financial',
  },
  {
    text: 'Settings',
    icon: <Settings />,
    path: '/dashboard/settings',
  },
];

export const Header = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('lg'));
  const isTablet = useMediaQuery(theme.breakpoints.down('xl'));
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleProfileMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/auth/login');
  };

  const handleProfile = () => {
    handleMenuClose();
    navigate('/dashboard/settings');
  };

  const filteredNavItems = navItems.filter((item) => {
    if (!item.roles) return true;
    return user && item.roles.includes(user.role);
  });

  // Show only important items on tablet, all on desktop
  const visibleNavItems = isTablet 
    ? filteredNavItems.slice(0, 6) 
    : filteredNavItems;

  const handleNavigation = (path: string) => {
    navigate(path);
    setMobileMenuOpen(false);
  };

  return (
    <>
      <AppBar position="fixed">
        <Toolbar sx={{ px: { xs: 2, sm: 3 } }}>
          {/* Logo */}
          <Box sx={{ display: 'flex', alignItems: 'center', mr: 3 }}>
            <AdminPanelSettings sx={{ fontSize: 28, mr: 1 }} />
            <Typography 
              variant="h6" 
              sx={{ 
                fontWeight: 600,
                display: { xs: 'none', sm: 'block' }
              }}
            >
              AgencyDark
            </Typography>
          </Box>

          {/* Desktop Navigation */}
          {!isMobile && (
            <Box sx={{ display: 'flex', gap: 0.5, flexGrow: 1 }}>
              {visibleNavItems.map((item) => (
                <Button
                  key={item.path}
                  color="inherit"
                  startIcon={item.icon}
                  onClick={() => handleNavigation(item.path)}
                  sx={{
                    px: isTablet ? 1.5 : 2,
                    py: 1,
                    borderRadius: 1,
                    textTransform: 'none',
                    backgroundColor: location.pathname === item.path 
                      ? 'rgba(255, 255, 255, 0.1)' 
                      : 'transparent',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.15)',
                    },
                    minWidth: 'auto',
                    fontSize: isTablet ? '0.875rem' : '0.9375rem',
                  }}
                >
                  {item.text}
                </Button>
              ))}
            </Box>
          )}

          {/* Mobile menu button */}
          {isMobile && (
            <>
              <Box sx={{ flexGrow: 1 }} />
              <IconButton
                color="inherit"
                onClick={() => setMobileMenuOpen(true)}
                sx={{ mr: 1 }}
              >
                <MenuIcon />
              </IconButton>
            </>
          )}

          {/* Right side items */}
          {!isMobile && <Box sx={{ flexGrow: 1 }} />}
          
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton color="inherit" size="large">
              <Badge badgeContent={4} color="error">
                <Notifications />
              </Badge>
            </IconButton>

            <IconButton
              size="large"
              edge="end"
              aria-label="account of current user"
              aria-controls="profile-menu"
              aria-haspopup="true"
              onClick={handleProfileMenuOpen}
              color="inherit"
            >
              {user?.full_name ? (
                <Avatar sx={{ width: 32, height: 32 }}>
                  {user.full_name.charAt(0).toUpperCase()}
                </Avatar>
              ) : (
                <AccountCircle />
              )}
            </IconButton>
          </Box>

          <Menu
            id="profile-menu"
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem disabled>
              <Typography variant="body2" color="text.secondary">
                {user?.email}
              </Typography>
            </MenuItem>
            <MenuItem onClick={handleProfile}>Profile Settings</MenuItem>
            <MenuItem onClick={handleLogout}>Logout</MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Mobile Navigation Drawer */}
      <Drawer
        anchor="right"
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        sx={{
          '& .MuiDrawer-paper': {
            width: 280,
          },
        }}
      >
        <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Typography variant="h6">Menu</Typography>
          <IconButton onClick={() => setMobileMenuOpen(false)}>
            <Close />
          </IconButton>
        </Box>
        <Divider />
        <List>
          {filteredNavItems.map((item) => (
            <ListItem key={item.path} disablePadding>
              <ListItemButton
                selected={location.pathname === item.path}
                onClick={() => handleNavigation(item.path)}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.text} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
        <Box sx={{ flexGrow: 1 }} />
        <Divider />
        <Box sx={{ p: 2 }}>
          <Typography variant="caption" color="text.secondary">
            Logged in as
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 500 }}>
            {user?.full_name || 'User'}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {user?.role.replace('_', ' ')}
          </Typography>
        </Box>
      </Drawer>
    </>
  );
};