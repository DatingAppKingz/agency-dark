import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Paper,
  Card,
  CardContent,
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
  Grid,
  Avatar,
  CircularProgress,
  Button,
} from '@mui/material';
import {
  Search,
  ExpandMore,
  ExpandLess,
  Person,
  Business,
  ModelTraining,
  Visibility,
  Star,
  TrendingUp,
} from '@mui/icons-material';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { UserRole, normalizeRole } from '@/types/auth';
import { format } from 'date-fns';

interface Model {
  id: string;
  email: string;
  full_name: string;
  stage_name?: string;
  agency_id: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login?: string;
  // Model-specific fields
  profile_completion?: number;
  total_earnings?: number;
  active_subscribers?: number;
  content_count?: number;
  average_rating?: number;
}

interface Agency {
  id: string;
  name: string;
  models?: Model[];
}

const ModelOverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedAgencies, setExpandedAgencies] = useState<Set<string>>(new Set());

  const userRole = user ? normalizeRole(user.role) : '';
  const isSuperAdmin = userRole === UserRole.SUPER_ADMIN;
  const isModel = userRole === UserRole.MODEL;

  // If user is a model, redirect to their details page
  React.useEffect(() => {
    if (isModel && user?.id) {
      navigate(`/dashboard/models/${user.id}`);
    }
  }, [isModel, user?.id, navigate]);

  // Fetch models data
  const { data: modelsData, isLoading: loadingModels } = useQuery({
    queryKey: ['models-overview'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/v1/admin/users/list?page=1&size=1000', {
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error('Failed to fetch models');
        }
        const data = await response.json();
        // Filter only MODEL role users
        return {
          ...data,
          data: data.data.filter((user: any) => 
            normalizeRole(user.role) === UserRole.MODEL
          ),
        };
      } catch (error) {
        console.error('Error fetching models:', error);
        return { data: [], total: 0 };
      }
    },
    enabled: !isModel, // Don't fetch if user is a model
  });

  // Fetch agencies data
  const { data: agencies, isLoading: loadingAgencies } = useQuery({
    queryKey: ['agencies-overview'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/v1/admin/agencies/list?page=1&size=100', {
          credentials: 'include',
        });
        if (!response.ok) {
          throw new Error('Failed to fetch agencies');
        }
        return await response.json();
      } catch (error) {
        console.error('Error fetching agencies:', error);
        return { data: [], total: 0 };
      }
    },
    enabled: isSuperAdmin, // Only fetch agencies for super admin
  });

  const allModels = modelsData?.data || [];
  const agencyList = agencies?.data || [];

  // Group models by agency
  const modelsByAgency = React.useMemo(() => {
    const grouped = new Map<string, Model[]>();
    
    if (isSuperAdmin) {
      // Initialize with all agencies
      agencyList.forEach(agency => {
        grouped.set(agency.id, []);
      });
      
      // Add "No Agency" group
      grouped.set('no-agency', []);
      
      // Group models
      allModels.forEach(model => {
        if (model.agency_id) {
          const models = grouped.get(model.agency_id) || [];
          models.push(model);
          grouped.set(model.agency_id, models);
        } else {
          const noAgencyModels = grouped.get('no-agency') || [];
          noAgencyModels.push(model);
          grouped.set('no-agency', noAgencyModels);
        }
      });
    } else {
      // For agency owners/admins, only show their agency's models
      const userAgencyModels = allModels.filter(model => 
        model.agency_id === user?.agency_id
      );
      grouped.set(user?.agency_id || 'current-agency', userAgencyModels);
    }
    
    return grouped;
  }, [allModels, agencyList, isSuperAdmin, user?.agency_id]);

  const toggleAgencyExpansion = (agencyId: string) => {
    const newExpanded = new Set(expandedAgencies);
    if (newExpanded.has(agencyId)) {
      newExpanded.delete(agencyId);
    } else {
      newExpanded.add(agencyId);
    }
    setExpandedAgencies(newExpanded);
  };

  const navigateToModelDetails = (modelId: string) => {
    navigate(`/dashboard/models/${modelId}`);
  };

  const renderModelRow = (model: Model) => {
    // Generate mock data for demonstration
    const mockData = {
      profile_completion: Math.floor(Math.random() * 40) + 60,
      total_earnings: Math.floor(Math.random() * 50000) + 10000,
      active_subscribers: Math.floor(Math.random() * 1000) + 100,
      average_rating: (Math.random() * 2 + 3).toFixed(1),
    };

    return (
      <TableRow 
        key={model.id} 
        hover 
        sx={{ cursor: 'pointer' }}
        onClick={() => navigateToModelDetails(model.id)}
      >
        <TableCell>
          <Box display="flex" alignItems="center" gap={1}>
            <Avatar sx={{ width: 40, height: 40 }}>
              {model.stage_name?.[0] || model.full_name?.[0] || model.email[0].toUpperCase()}
            </Avatar>
            <Box>
              <Typography variant="body2" fontWeight="medium">
                {model.stage_name || model.full_name || 'No name'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {model.email}
              </Typography>
            </Box>
          </Box>
        </TableCell>
        <TableCell>
          <Box display="flex" alignItems="center" gap={0.5}>
            <Star sx={{ fontSize: 16, color: 'warning.main' }} />
            <Typography variant="body2">{mockData.average_rating}</Typography>
          </Box>
        </TableCell>
        <TableCell>
          <Typography variant="body2">
            {mockData.active_subscribers.toLocaleString()}
          </Typography>
        </TableCell>
        <TableCell>
          <Typography variant="body2" color="success.main" fontWeight="medium">
            ${mockData.total_earnings.toLocaleString()}
          </Typography>
        </TableCell>
        <TableCell>
          <Box display="flex" alignItems="center" gap={1}>
            <CircularProgress 
              variant="determinate" 
              value={mockData.profile_completion} 
              size={24}
              color={mockData.profile_completion >= 80 ? 'success' : 'warning'}
            />
            <Typography variant="caption">
              {mockData.profile_completion}%
            </Typography>
          </Box>
        </TableCell>
        <TableCell>
          <Chip
            label={model.is_active ? 'Active' : 'Inactive'}
            size="small"
            color={model.is_active ? 'success' : 'default'}
            variant={model.is_active ? 'filled' : 'outlined'}
          />
        </TableCell>
        <TableCell>
          {model.last_login ? (
            <Typography variant="caption">
              {format(new Date(model.last_login), 'MMM dd, yyyy')}
            </Typography>
          ) : (
            <Typography variant="caption" color="text.secondary">
              Never
            </Typography>
          )}
        </TableCell>
        <TableCell>
          <IconButton size="small" onClick={(e) => e.stopPropagation()}>
            <Visibility />
          </IconButton>
        </TableCell>
      </TableRow>
    );
  };

  const renderStatistics = () => {
    const totalModels = allModels.length;
    const activeModels = allModels.filter(m => m.is_active).length;
    const verifiedModels = allModels.filter(m => m.is_verified).length;
    const recentlyActive = allModels.filter(m => {
      if (!m.last_login) return false;
      const lastLogin = new Date(m.last_login);
      const daysSinceLogin = (Date.now() - lastLogin.getTime()) / (1000 * 60 * 60 * 24);
      return daysSinceLogin <= 7;
    }).length;

    return (
      <Grid container spacing={2} mb={4}>
        <Grid item xs={6} sm={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h4">{totalModels}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Total Models
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h4" color="success.main">{activeModels}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Active Models
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h4" color="info.main">{verifiedModels}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Verified Models
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Card>
            <CardContent>
              <Box textAlign="center">
                <Typography variant="h4" color="warning.main">{recentlyActive}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Active This Week
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    );
  };

  const renderAgencyView = () => (
    <Box>
      {/* Search */}
      <TextField
        fullWidth
        variant="outlined"
        placeholder="Search models by name or email..."
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

      {/* Agencies with models */}
      {Array.from(modelsByAgency.entries()).map(([agencyId, models]) => {
        const agency = agencyList.find(a => a.id === agencyId);
        const agencyName = agencyId === 'no-agency' 
          ? 'Unassigned Models' 
          : agencyId === 'current-agency'
          ? 'Your Agency'
          : agency?.name || `Agency ${agencyId.slice(0, 8)}`;

        const filteredModels = models.filter(model =>
          model.full_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          model.stage_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          model.email.toLowerCase().includes(searchTerm.toLowerCase())
        );

        if (searchTerm && filteredModels.length === 0) return null;

        return (
          <Card key={agencyId} sx={{ mb: 2 }}>
            <CardContent>
              <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                sx={{ cursor: 'pointer' }}
                onClick={() => toggleAgencyExpansion(agencyId)}
              >
                <Box display="flex" alignItems="center" gap={2}>
                  <Business color="action" />
                  <Box>
                    <Typography variant="h6">{agencyName}</Typography>
                    <Typography variant="caption" color="text.secondary">
                      {models.length} models
                    </Typography>
                  </Box>
                </Box>
                <IconButton>
                  {expandedAgencies.has(agencyId) ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>

              <Collapse in={expandedAgencies.has(agencyId)}>
                <TableContainer sx={{ mt: 2 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Model</TableCell>
                        <TableCell>Rating</TableCell>
                        <TableCell>Subscribers</TableCell>
                        <TableCell>Earnings</TableCell>
                        <TableCell>Profile</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Last Active</TableCell>
                        <TableCell>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredModels.map(renderModelRow)}
                    </TableBody>
                  </Table>
                </TableContainer>
              </Collapse>
            </CardContent>
          </Card>
        );
      })}
    </Box>
  );

  if (loadingModels || (isSuperAdmin && loadingAgencies)) {
    return (
      <Container maxWidth="xl">
        <Box display="flex" justifyContent="center" alignItems="center" height={400}>
          <CircularProgress />
        </Box>
      </Container>
    );
  }

  // If user is a model, they will be redirected to their details page
  if (isModel) {
    return (
      <Container maxWidth="xl">
        <Box display="flex" justifyContent="center" alignItems="center" height={400}>
          <CircularProgress />
          <Typography ml={2}>Redirecting to your profile...</Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="xl">
      <Box py={4}>
        {/* Header */}
        <Box display="flex" alignItems="center" justifyContent="space-between" mb={4}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Model Overview
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {isSuperAdmin 
                ? 'View and manage all models across agencies'
                : 'View and manage models in your agency'
              }
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<Person />}
            onClick={() => navigate('/dashboard/models/new')}
          >
            Add New Model
          </Button>
        </Box>

        {/* Statistics */}
        {renderStatistics()}

        {/* Models List */}
        <Paper>
          {renderAgencyView()}
        </Paper>
      </Box>
    </Container>
  );
};

export default ModelOverviewPage;