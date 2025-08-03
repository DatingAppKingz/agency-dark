import { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  TextField,
  InputAdornment,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Grid,
  MenuItem,
  Avatar,
  TablePagination,
} from '@mui/material';
import {
  Add,
  Search,
  Edit,
  Delete,
  Business,
  People,
  AttachMoney,
  MoreVert,
} from '@mui/icons-material';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useAuth } from '@/hooks/useAuth';
import { useNavigate } from 'react-router-dom';

const agencySchema = z.object({
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Invalid email address'),
  phone: z.string().optional(),
  website: z.string().url('Invalid URL').optional().or(z.literal('')),
  ownerEmail: z.string().email('Invalid owner email'),
  plan: z.enum(['starter', 'professional', 'enterprise']),
  maxModels: z.number().min(1).max(1000),
});

type AgencyFormData = z.infer<typeof agencySchema>;

interface Agency {
  id: string;
  name: string;
  email: string;
  owner: {
    name: string;
    email: string;
  };
  plan: 'starter' | 'professional' | 'enterprise';
  status: 'active' | 'suspended' | 'pending';
  models: number;
  chatters: number;
  revenue: number;
  createdAt: Date;
}

const AgenciesListPage = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [searchTerm, setSearchTerm] = useState('');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedAgency, setSelectedAgency] = useState<Agency | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<AgencyFormData>({
    resolver: zodResolver(agencySchema),
  });

  // Mock data - in real app, this would come from API
  const agencies: Agency[] = [
    {
      id: '1',
      name: 'Premium Marketing Agency',
      email: 'contact@premium.com',
      owner: { name: 'John Doe', email: 'john@premium.com' },
      plan: 'professional',
      status: 'active',
      models: 23,
      chatters: 12,
      revenue: 125000,
      createdAt: new Date('2024-01-15'),
    },
    {
      id: '2',
      name: 'Elite Models Management',
      email: 'info@elitemodels.com',
      owner: { name: 'Jane Smith', email: 'jane@elitemodels.com' },
      plan: 'enterprise',
      status: 'active',
      models: 67,
      chatters: 34,
      revenue: 450000,
      createdAt: new Date('2023-11-20'),
    },
    {
      id: '3',
      name: 'Rising Stars Agency',
      email: 'hello@risingstars.com',
      owner: { name: 'Mike Johnson', email: 'mike@risingstars.com' },
      plan: 'starter',
      status: 'pending',
      models: 5,
      chatters: 2,
      revenue: 15000,
      createdAt: new Date('2024-03-01'),
    },
  ];

  const filteredAgencies = agencies.filter(
    (agency) =>
      agency.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      agency.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      agency.owner.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleCreateAgency = async (data: AgencyFormData) => {
    console.log('Creating agency:', data);
    setCreateDialogOpen(false);
    reset();
  };

  const handleEditAgency = (agency: Agency) => {
    // Navigate to agency settings page or open edit dialog
    navigate(`/dashboard/agency/${agency.id}`);
  };

  const handleDeleteAgency = (agency: Agency) => {
    if (confirm(`Are you sure you want to delete ${agency.name}?`)) {
      console.log('Deleting agency:', agency.id);
    }
  };

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const getStatusColor = (status: Agency['status']) => {
    switch (status) {
      case 'active':
        return 'success';
      case 'suspended':
        return 'error';
      case 'pending':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getPlanColor = (plan: Agency['plan']) => {
    switch (plan) {
      case 'enterprise':
        return 'primary';
      case 'professional':
        return 'secondary';
      case 'starter':
        return 'default';
      default:
        return 'default';
    }
  };

  if (!user || user.role !== 'super_admin') {
    return (
      <Box p={3}>
        <Typography variant="h5" color="error">
          Access Denied
        </Typography>
        <Typography>Only super administrators can access this page.</Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4">Agencies Management</Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => setCreateDialogOpen(true)}
        >
          Create Agency
        </Button>
      </Box>

      {/* Summary Cards */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom>
                    Total Agencies
                  </Typography>
                  <Typography variant="h4">{agencies.length}</Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'primary.main' }}>
                  <Business />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom>
                    Total Models
                  </Typography>
                  <Typography variant="h4">
                    {agencies.reduce((sum, a) => sum + a.models, 0)}
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'secondary.main' }}>
                  <People />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom>
                    Total Chatters
                  </Typography>
                  <Typography variant="h4">
                    {agencies.reduce((sum, a) => sum + a.chatters, 0)}
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'success.main' }}>
                  <People />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="textSecondary" gutterBottom>
                    Total Revenue
                  </Typography>
                  <Typography variant="h4">
                    ${agencies.reduce((sum, a) => sum + a.revenue, 0).toLocaleString()}
                  </Typography>
                </Box>
                <Avatar sx={{ bgcolor: 'warning.main' }}>
                  <AttachMoney />
                </Avatar>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Search and Filters */}
      <Card sx={{ mb: 3 }}>
        <CardContent>
          <TextField
            fullWidth
            placeholder="Search agencies..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
        </CardContent>
      </Card>

      {/* Agencies Table */}
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Agency</TableCell>
              <TableCell>Owner</TableCell>
              <TableCell>Plan</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="center">Models</TableCell>
              <TableCell align="center">Chatters</TableCell>
              <TableCell align="right">Revenue</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredAgencies
              .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
              .map((agency) => (
                <TableRow key={agency.id} hover>
                  <TableCell>
                    <Box>
                      <Typography variant="subtitle2">{agency.name}</Typography>
                      <Typography variant="body2" color="textSecondary">
                        {agency.email}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Box>
                      <Typography variant="body2">{agency.owner.name}</Typography>
                      <Typography variant="caption" color="textSecondary">
                        {agency.owner.email}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={agency.plan}
                      size="small"
                      color={getPlanColor(agency.plan)}
                    />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={agency.status}
                      size="small"
                      color={getStatusColor(agency.status)}
                    />
                  </TableCell>
                  <TableCell align="center">{agency.models}</TableCell>
                  <TableCell align="center">{agency.chatters}</TableCell>
                  <TableCell align="right">
                    ${agency.revenue.toLocaleString()}
                  </TableCell>
                  <TableCell>
                    {agency.createdAt.toLocaleDateString()}
                  </TableCell>
                  <TableCell align="center">
                    <IconButton
                      size="small"
                      onClick={() => handleEditAgency(agency)}
                    >
                      <Edit />
                    </IconButton>
                    <IconButton
                      size="small"
                      onClick={() => handleDeleteAgency(agency)}
                      color="error"
                    >
                      <Delete />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25]}
          component="div"
          count={filteredAgencies.length}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </TableContainer>

      {/* Create Agency Dialog */}
      <Dialog
        open={createDialogOpen}
        onClose={() => setCreateDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <form onSubmit={handleSubmit(handleCreateAgency)}>
          <DialogTitle>Create New Agency</DialogTitle>
          <DialogContent>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Agency Name"
                  {...register('name')}
                  error={!!errors.name}
                  helperText={errors.name?.message}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Contact Email"
                  {...register('email')}
                  error={!!errors.email}
                  helperText={errors.email?.message}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Phone"
                  {...register('phone')}
                  error={!!errors.phone}
                  helperText={errors.phone?.message}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Website"
                  {...register('website')}
                  error={!!errors.website}
                  helperText={errors.website?.message}
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Owner Email"
                  {...register('ownerEmail')}
                  error={!!errors.ownerEmail}
                  helperText={errors.ownerEmail?.message}
                />
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  select
                  fullWidth
                  label="Plan"
                  {...register('plan')}
                  error={!!errors.plan}
                  helperText={errors.plan?.message}
                  defaultValue="starter"
                >
                  <MenuItem value="starter">Starter</MenuItem>
                  <MenuItem value="professional">Professional</MenuItem>
                  <MenuItem value="enterprise">Enterprise</MenuItem>
                </TextField>
              </Grid>
              <Grid item xs={12} sm={6}>
                <TextField
                  fullWidth
                  type="number"
                  label="Max Models"
                  {...register('maxModels', { valueAsNumber: true })}
                  error={!!errors.maxModels}
                  helperText={errors.maxModels?.message}
                  defaultValue={10}
                />
              </Grid>
            </Grid>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
            <Button type="submit" variant="contained">
              Create Agency
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  );
};

export default AgenciesListPage;