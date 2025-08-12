import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  IconButton,
  Button,
  TextField,
  InputAdornment,
  Chip,
  Menu,
  MenuItem,
  Typography,
  Alert,
  Skeleton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Switch,
  FormControlLabel,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  MoreVert as MoreVertIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Security as SecurityIcon,
  VpnKey as VpnKeyIcon,
  ContentCopy as CopyIcon,
  Refresh as RefreshIcon,
  FilterList as FilterIcon,
  Download as DownloadIcon,
  Block as BlockIcon,
  CheckCircle as CheckCircleIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useOAuthClients } from '../../hooks/useOAuthClients';
import { OAuthClient, ClientType, ClientStatus } from '../../types/oauth';
import { ClientDetailsDialog } from '../../components/oauth/ClientDetailsDialog';
import { ClientCreationWizard } from '../../components/oauth/ClientCreationWizard';

const OAuthClients: React.FC = () => {
  const navigate = useNavigate();
  const {
    clients,
    loading,
    error,
    totalCount,
    fetchClients,
    deleteClient,
    rotateSecret,
    updateClientStatus,
  } = useOAuthClients();

  // State
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedClient, setSelectedClient] = useState<OAuthClient | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuClient, setMenuClient] = useState<OAuthClient | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showCreation, setShowCreation] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [clientToDelete, setClientToDelete] = useState<OAuthClient | null>(null);
  const [filterType, setFilterType] = useState<ClientType | 'all'>('all');
  const [filterStatus, setFilterStatus] = useState<ClientStatus | 'all'>('all');

  // Fetch clients on mount and when filters change
  useEffect(() => {
    fetchClients({
      page: page + 1,
      limit: rowsPerPage,
      search: searchQuery,
      type: filterType !== 'all' ? filterType : undefined,
      status: filterStatus !== 'all' ? filterStatus : undefined,
    });
  }, [page, rowsPerPage, searchQuery, filterType, filterStatus]);

  // Filtered clients
  const filteredClients = useMemo(() => {
    return clients.filter(client => {
      const matchesSearch = !searchQuery || 
        client.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        client.clientId.toLowerCase().includes(searchQuery.toLowerCase());
      
      const matchesType = filterType === 'all' || client.type === filterType;
      const matchesStatus = filterStatus === 'all' || client.status === filterStatus;
      
      return matchesSearch && matchesType && matchesStatus;
    });
  }, [clients, searchQuery, filterType, filterStatus]);

  // Handlers
  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, client: OAuthClient) => {
    setAnchorEl(event.currentTarget);
    setMenuClient(client);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setMenuClient(null);
  };

  const handleViewDetails = (client: OAuthClient) => {
    setSelectedClient(client);
    setShowDetails(true);
    handleMenuClose();
  };

  const handleEditClient = (client: OAuthClient) => {
    navigate(`/admin/oauth/clients/${client.id}/edit`);
    handleMenuClose();
  };

  const handleDeleteClick = (client: OAuthClient) => {
    setClientToDelete(client);
    setDeleteDialogOpen(true);
    handleMenuClose();
  };

  const handleDeleteConfirm = async () => {
    if (clientToDelete) {
      await deleteClient(clientToDelete.id);
      setDeleteDialogOpen(false);
      setClientToDelete(null);
    }
  };

  const handleRotateSecret = async (client: OAuthClient) => {
    await rotateSecret(client.id);
    handleMenuClose();
  };

  const handleToggleStatus = async (client: OAuthClient) => {
    const newStatus = client.status === 'active' ? 'suspended' : 'active';
    await updateClientStatus(client.id, newStatus);
    handleMenuClose();
  };

  const handleCopyClientId = (clientId: string) => {
    navigator.clipboard.writeText(clientId);
    // Show toast notification
  };

  const handleExportClients = () => {
    const csv = convertToCSV(filteredClients);
    downloadCSV(csv, 'oauth-clients.csv');
  };

  const getClientTypeColor = (type: ClientType): 'primary' | 'secondary' | 'default' => {
    switch (type) {
      case 'confidential':
        return 'primary';
      case 'public':
        return 'secondary';
      default:
        return 'default';
    }
  };

  const getClientStatusColor = (status: ClientStatus): 'success' | 'error' | 'warning' | 'default' => {
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

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">OAuth Clients</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleExportClients}
          >
            Export
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setShowCreation(true)}
          >
            Create Client
          </Button>
        </Box>
      </Box>

      {/* Filters */}
      <Card sx={{ mb: 3, p: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <TextField
            placeholder="Search clients..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            sx={{ flexGrow: 1 }}
          />
          
          <TextField
            select
            label="Type"
            value={filterType}
            onChange={(e) => setFilterType(e.target.value as ClientType | 'all')}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="all">All Types</MenuItem>
            <MenuItem value="confidential">Confidential</MenuItem>
            <MenuItem value="public">Public</MenuItem>
          </TextField>

          <TextField
            select
            label="Status"
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as ClientStatus | 'all')}
            sx={{ minWidth: 150 }}
          >
            <MenuItem value="all">All Status</MenuItem>
            <MenuItem value="active">Active</MenuItem>
            <MenuItem value="suspended">Suspended</MenuItem>
            <MenuItem value="pending">Pending</MenuItem>
          </TextField>

          <IconButton onClick={() => fetchClients({})}>
            <RefreshIcon />
          </IconButton>
        </Box>
      </Card>

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Clients Table */}
      <Card>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Client Name</TableCell>
                <TableCell>Client ID</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Redirect URIs</TableCell>
                <TableCell>Created</TableCell>
                <TableCell>Last Used</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                // Loading skeletons
                Array.from({ length: 5 }).map((_, index) => (
                  <TableRow key={index}>
                    {Array.from({ length: 8 }).map((_, cellIndex) => (
                      <TableCell key={cellIndex}>
                        <Skeleton variant="text" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filteredClients.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} align="center">
                    <Typography variant="body2" color="textSecondary">
                      No clients found
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredClients.map((client) => (
                  <TableRow key={client.id} hover>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <SecurityIcon fontSize="small" color="action" />
                        <Typography variant="body2" fontWeight="medium">
                          {client.name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="body2" fontFamily="monospace">
                          {client.clientId.substring(0, 12)}...
                        </Typography>
                        <IconButton
                          size="small"
                          onClick={() => handleCopyClientId(client.clientId)}
                        >
                          <CopyIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={client.type}
                        size="small"
                        color={getClientTypeColor(client.type)}
                      />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={client.status}
                        size="small"
                        color={getClientStatusColor(client.status)}
                        icon={
                          client.status === 'active' ? 
                            <CheckCircleIcon /> : 
                            client.status === 'suspended' ?
                            <BlockIcon /> :
                            undefined
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Tooltip title={client.redirectUris.join(', ')}>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                          {client.redirectUris.length} URI(s)
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {format(new Date(client.createdAt), 'MMM d, yyyy')}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {client.lastUsedAt 
                          ? format(new Date(client.lastUsedAt), 'MMM d, yyyy')
                          : 'Never'
                        }
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        onClick={(e) => handleMenuOpen(e, client)}
                      >
                        <MoreVertIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        <TablePagination
          rowsPerPageOptions={[10, 25, 50, 100]}
          component="div"
          count={totalCount}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </Card>

      {/* Actions Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={() => menuClient && handleViewDetails(menuClient)}>
          <SecurityIcon fontSize="small" sx={{ mr: 1 }} />
          View Details
        </MenuItem>
        <MenuItem onClick={() => menuClient && handleEditClient(menuClient)}>
          <EditIcon fontSize="small" sx={{ mr: 1 }} />
          Edit Client
        </MenuItem>
        <MenuItem onClick={() => menuClient && handleRotateSecret(menuClient)}>
          <VpnKeyIcon fontSize="small" sx={{ mr: 1 }} />
          Rotate Secret
        </MenuItem>
        <MenuItem onClick={() => menuClient && handleToggleStatus(menuClient)}>
          {menuClient?.status === 'active' ? (
            <>
              <BlockIcon fontSize="small" sx={{ mr: 1 }} />
              Suspend Client
            </>
          ) : (
            <>
              <CheckCircleIcon fontSize="small" sx={{ mr: 1 }} />
              Activate Client
            </>
          )}
        </MenuItem>
        <MenuItem 
          onClick={() => menuClient && handleDeleteClick(menuClient)}
          sx={{ color: 'error.main' }}
        >
          <DeleteIcon fontSize="small" sx={{ mr: 1 }} />
          Delete Client
        </MenuItem>
      </Menu>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete OAuth Client</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete the client "{clientToDelete?.name}"? 
            This action cannot be undone and will revoke all associated tokens.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>

      {/* Client Details Dialog */}
      {selectedClient && (
        <ClientDetailsDialog
          client={selectedClient}
          open={showDetails}
          onClose={() => {
            setShowDetails(false);
            setSelectedClient(null);
          }}
          onEdit={() => handleEditClient(selectedClient)}
          onRotateSecret={() => handleRotateSecret(selectedClient)}
        />
      )}

      {/* Client Creation Wizard */}
      <ClientCreationWizard
        open={showCreation}
        onClose={() => setShowCreation(false)}
        onSuccess={() => {
          setShowCreation(false);
          fetchClients({});
        }}
      />
    </Box>
  );
};

// Helper functions
const convertToCSV = (clients: OAuthClient[]): string => {
  const headers = ['Name', 'Client ID', 'Type', 'Status', 'Created', 'Last Used'];
  const rows = clients.map(client => [
    client.name,
    client.clientId,
    client.type,
    client.status,
    client.createdAt,
    client.lastUsedAt || 'Never',
  ]);
  
  return [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${cell}"`).join(',')),
  ].join('\n');
};

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

export default OAuthClients;