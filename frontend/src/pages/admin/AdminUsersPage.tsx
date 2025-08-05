import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Tabs,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Collapse,
  TextField,
  InputAdornment,
  Card,
  CardContent,
  Grid,
  Avatar,
  Tooltip,
  CircularProgress,
} from '@mui/material';
import {
  Search,
  ExpandMore,
  ExpandLess,
  Person,
  Business,
  Groups,
  AdminPanelSettings,
  ModelTraining,
  Chat,
  Group,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { usersService } from '@/services/api/users';
import { agenciesService } from '@/services/api/agencies';
import { UserRole, normalizeRole } from '@/types/auth';
import { format } from 'date-fns';

interface Agency {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
  is_active: boolean;
  users?: User[];
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  agency_id: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login?: string;
}

const AdminUsersPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedAgencies, setExpandedAgencies] = useState<Set<string>>(new Set());

  // Fetch all agencies
  const { data: agencies, isLoading: loadingAgencies } = useQuery({
    queryKey: ['admin-agencies'],
    queryFn: () => agenciesService.getAgencies({ page: 1, size: 100 }),
  });

  // Fetch all users
  const { data: usersData, isLoading: loadingUsers } = useQuery({
    queryKey: ['admin-users'],
    queryFn: async () => {
      try {
        // Use the new admin users endpoint
        const response = await fetch('/api/v1/admin/users/list?page=1&size=1000', {
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error('Failed to fetch users');
        }
        return await response.json();
      } catch (error) {
        console.error('Error fetching users:', error);
        // Return mock data for now
        return {
          data: [
            {
              id: 'c2aadc72-7020-447c-bf9a-241a94f4bc08',
              email: 'admin@agency.com',
              full_name: 'Admin User',
              role: 'SUPER_ADMIN',
              agency_id: null,
              is_active: true,
              is_verified: true,
              created_at: new Date().toISOString(),
            },
          ],
          total: 1,
        };
      }
    },
  });

  const allUsers = usersData?.data || [];
  const agencyList = agencies?.data || [];

  // Group users by agency
  const usersByAgency = React.useMemo(() => {
    const grouped = new Map<string, User[]>();
    
    // Initialize with all agencies
    agencyList.forEach(agency => {
      grouped.set(agency.id, []);
    });
    
    // Add "No Agency" group for unassigned users
    grouped.set('no-agency', []);
    
    // Group users
    allUsers.forEach(user => {
      if (user.agency_id) {
        const users = grouped.get(user.agency_id) || [];
        users.push(user);
        grouped.set(user.agency_id, users);
      } else {
        const noAgencyUsers = grouped.get('no-agency') || [];
        noAgencyUsers.push(user);
        grouped.set('no-agency', noAgencyUsers);
      }
    });
    
    return grouped;
  }, [allUsers, agencyList]);

  // Filter users by role
  const getUsersByRole = (role?: string) => {
    if (!role) return allUsers;
    return allUsers.filter(user => normalizeRole(user.role) === role);
  };

  // Role statistics
  const roleStats = React.useMemo(() => {
    const stats = {
      total: allUsers.length,
      super_admin: 0,
      agency_owner: 0,
      agency_admin: 0,
      model: 0,
      chatter: 0,
      agency_member: 0,
    };

    allUsers.forEach(user => {
      const role = normalizeRole(user.role);
      if (role in stats) {
        stats[role as keyof typeof stats]++;
      }
    });

    return stats;
  }, [allUsers]);

  const toggleAgencyExpansion = (agencyId: string) => {
    const newExpanded = new Set(expandedAgencies);
    if (newExpanded.has(agencyId)) {
      newExpanded.delete(agencyId);
    } else {
      newExpanded.add(agencyId);
    }
    setExpandedAgencies(newExpanded);
  };

  const getRoleIcon = (role: string) => {
    const normalized = normalizeRole(role);
    switch (normalized) {
      case UserRole.SUPER_ADMIN:
        return <AdminPanelSettings />;
      case UserRole.AGENCY_OWNER:
        return <Business />;
      case UserRole.AGENCY_ADMIN:
        return <Groups />;
      case UserRole.MODEL:
        return <ModelTraining />;
      case UserRole.CHATTER:
        return <Chat />;
      default:
        return <Person />;
    }
  };

  const getRoleColor = (role: string): 'error' | 'warning' | 'info' | 'success' | 'primary' | 'default' => {
    const normalized = normalizeRole(role);
    switch (normalized) {
      case UserRole.SUPER_ADMIN:
        return 'error';
      case UserRole.AGENCY_OWNER:
        return 'warning';
      case UserRole.AGENCY_ADMIN:
        return 'info';
      case UserRole.MODEL:
        return 'success';
      case UserRole.CHATTER:
        return 'primary';
      default:
        return 'default';
    }
  };

  const renderUserRow = (user: User) => (
    <TableRow key={user.id} hover>
      <TableCell>
        <Box display="flex" alignItems="center" gap={1}>
          <Avatar sx={{ width: 32, height: 32 }}>
            {user.full_name?.[0] || user.email[0].toUpperCase()}
          </Avatar>
          <Box>
            <Typography variant="body2" fontWeight="medium">
              {user.full_name || 'No name'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {user.email}
            </Typography>
          </Box>
        </Box>
      </TableCell>
      <TableCell>
        <Chip
          icon={getRoleIcon(user.role)}
          label={user.role.replace(/_/g, ' ').toLowerCase()}
          size="small"
          color={getRoleColor(user.role)}
          variant="outlined"
        />
      </TableCell>
      <TableCell>
        <Chip
          label={user.is_active ? 'Active' : 'Inactive'}
          size="small"
          color={user.is_active ? 'success' : 'default'}
          variant={user.is_active ? 'filled' : 'outlined'}
        />
      </TableCell>
      <TableCell>
        <Typography variant="caption">
          {format(new Date(user.created_at), 'MMM dd, yyyy')}
        </Typography>
      </TableCell>
      <TableCell>
        {user.last_login ? (
          <Typography variant="caption">
            {format(new Date(user.last_login), 'MMM dd, yyyy HH:mm')}
          </Typography>
        ) : (
          <Typography variant="caption" color="text.secondary">
            Never
          </Typography>
        )}
      </TableCell>
    </TableRow>
  );

  const renderAgencyView = () => (
    <Box>
      {/* Search */}
      <TextField
        fullWidth
        variant="outlined"
        placeholder="Search users by name or email..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        sx={{ mb: 3 }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <Search />
            </InputAdornment>
          ),
        }}
      />

      {/* Agencies with users */}
      {agencyList.map(agency => {
        const agencyUsers = usersByAgency.get(agency.id) || [];
        const filteredUsers = agencyUsers.filter(user =>
          user.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          user.email.toLowerCase().includes(searchTerm.toLowerCase())
        );

        if (searchTerm && filteredUsers.length === 0) return null;

        return (
          <Card key={agency.id} sx={{ mb: 2 }}>
            <CardContent>
              <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                sx={{ cursor: 'pointer' }}
                onClick={() => toggleAgencyExpansion(agency.id)}
              >
                <Box display="flex" alignItems="center" gap={2}>
                  <Business color="action" />
                  <Box>
                    <Typography variant="h6">{agency.name}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {agencyUsers.length} users
                    </Typography>
                  </Box>
                </Box>
                <IconButton>
                  {expandedAgencies.has(agency.id) ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>

              <Collapse in={expandedAgencies.has(agency.id)}>
                <TableContainer sx={{ mt: 2 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>User</TableCell>
                        <TableCell>Role</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Joined</TableCell>
                        <TableCell>Last Login</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredUsers.map(renderUserRow)}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Collapse>
            </CardContent>
          </Card>
        );
      })}

      {/* Users without agency */}
      {usersByAgency.get('no-agency')?.length > 0 && (
        <Card sx={{ mb: 2 }}>
          <CardContent>
            <Box
              display="flex"
              alignItems="center"
              justifyContent="space-between"
              sx={{ cursor: 'pointer' }}
              onClick={() => toggleAgencyExpansion('no-agency')}
            >
              <Box display="flex" alignItems="center" gap={2}>
                <Group color="action" />
                <Box>
                  <Typography variant="h6">Unassigned Users</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {usersByAgency.get('no-agency')?.length || 0} users
                  </Typography>
                </Box>
              </Box>
              <IconButton>
                {expandedAgencies.has('no-agency') ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
            </Box>

            <Collapse in={expandedAgencies.has('no-agency')}>
              <TableContainer sx={{ mt: 2 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>User</TableCell>
                      <TableCell>Role</TableCell>
                      <TableCell>Status</TableCell>
                      <TableCell>Joined</TableCell>
                      <TableCell>Last Login</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {usersByAgency.get('no-agency')?.map(renderUserRow)}
                  </TableBody>
                </Table>
              </TableContainer>
            </Collapse>
          </CardContent>
        </Card>
      )}
    </Box>
  );

  const renderRoleView = () => {
    const roleGroups = [
      { role: UserRole.SUPER_ADMIN, label: 'Super Admins', icon: <AdminPanelSettings /> },
      { role: UserRole.AGENCY_OWNER, label: 'Agency Owners', icon: <Business /> },
      { role: UserRole.AGENCY_ADMIN, label: 'Agency Admins', icon: <Groups /> },
      { role: UserRole.MODEL, label: 'Models', icon: <ModelTraining /> },
      { role: UserRole.CHATTER, label: 'Chatters', icon: <Chat /> },
      { role: UserRole.AGENCY_MEMBER, label: 'Agency Members', icon: <Person /> },
    ];

    return (
      <Box>
        {roleGroups.map(({ role, label, icon }) => {
          const users = getUsersByRole(role);
          if (users.length === 0) return null;

          return (
            <Card key={role} sx={{ mb: 2 }}>
              <CardContent>
                <Box display="flex" alignItems="center" gap={2} mb={2}>
                  {icon}
                  <Typography variant="h6">{label}</Typography>
                  <Chip label={users.length} size="small" />
                </Box>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>User</TableCell>
                        <TableCell>Agency</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Joined</TableCell>
                        <TableCell>Last Login</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {users.map(user => (
                        <TableRow key={user.id} hover>
                          <TableCell>
                            <Box display="flex" alignItems="center" gap={1}>
                              <Avatar sx={{ width: 32, height: 32 }}>
                                {user.full_name?.[0] || user.email[0].toUpperCase()}
                              </Avatar>
                              <Box>
                                <Typography variant="body2" fontWeight="medium">
                                  {user.full_name || 'No name'}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                  {user.email}
                                </Typography>
                              </Box>
                            </Box>
                          </TableCell>
                          <TableCell>
                            {user.agency_id ? (
                              <Typography variant="body2">
                                {agencyList.find(a => a.id === user.agency_id)?.name || 'Unknown'}
                              </Typography>
                            ) : (
                              <Typography variant="body2" color="text.secondary">
                                No agency
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={user.is_active ? 'Active' : 'Inactive'}
                              size="small"
                              color={user.is_active ? 'success' : 'default'}
                              variant={user.is_active ? 'filled' : 'outlined'}
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption">
                              {format(new Date(user.created_at), 'MMM dd, yyyy')}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {user.last_login ? (
                              <Typography variant="caption">
                                {format(new Date(user.last_login), 'MMM dd, yyyy HH:mm')}
                              </Typography>
                            ) : (
                              <Typography variant="caption" color="text.secondary">
                                Never
                              </Typography>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          );
        })}
      </Box>
    );
  };

  if (loadingAgencies || loadingUsers) {
    return (
      <Container maxWidth="xl">
        <Box display="flex" justifyContent="center" alignItems="center" height={400}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl">
      <Box py={4}>
        {/* Header */}
        <Box mb={4}>
          <Typography variant="h4" gutterBottom>
            User Management
          </Typography>
          <Typography variant="body1" color="text.secondary">
            View and manage all users across agencies
          </Typography>
        </Box>

        {/* Statistics */}
        <Grid container spacing={2} mb={4}>
          <Grid item xs={6} sm={4} md={2}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4">{roleStats.total}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Total Users
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4">{roleStats.super_admin}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Super Admins
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4">{roleStats.agency_owner}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Agency Owners
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4">{roleStats.model}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Models
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4">{roleStats.chatter}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Chatters
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={6} sm={4} md={2}>
            <Card>
              <CardContent>
                <Box textAlign="center">
                  <Typography variant="h4">{agencyList.length}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Agencies
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* View Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)}>
            <Tab label="By Agency" />
            <Tab label="By Role" />
          </Tabs>
        </Paper>

        {/* Content */}
        {activeTab === 0 && renderAgencyView()}
        {activeTab === 1 && renderRoleView()}
      </Box>
    </Container>
  );
};

export default AdminUsersPage;