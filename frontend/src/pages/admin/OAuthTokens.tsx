import React, { useState, useEffect, useMemo } from 'react';
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
  FormControl,
  Select,
  Checkbox,
  Paper,
  Grid,
  LinearProgress,
  Divider,
} from '@mui/material';
import {
  Search as SearchIcon,
  FilterList as FilterIcon,
  Block as BlockIcon,
  Delete as DeleteIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Download as DownloadIcon,
  MoreVert as MoreVertIcon,
  AccessTime as AccessTimeIcon,
  VpnKey as KeyIcon,
  Person as PersonIcon,
  Apps as AppsIcon,
  Warning as WarningIcon,
  CheckCircle as CheckCircleIcon,
  Schedule as ScheduleIcon,
  ClearAll as ClearAllIcon,
} from '@mui/icons-material';
import { format, formatDistanceToNow, isAfter, addSeconds } from 'date-fns';
import { useOAuthTokens } from '../../hooks/useOAuthTokens';
import { OAuthToken, TokenType, TokenStatus } from '../../types/oauth';
import { TokenDetailsDialog } from '../../components/oauth/TokenDetailsDialog';
import { TokenAnalytics } from '../../components/oauth/TokenAnalytics';

const OAuthTokens: React.FC = () => {
  const {
    tokens,
    loading,
    error,
    totalCount,
    fetchTokens,
    revokeToken,
    revokeMultipleTokens,
    introspectToken,
    getTokenAnalytics,
  } = useOAuthTokens();

  // State
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTokens, setSelectedTokens] = useState<string[]>([]);
  const [selectedToken, setSelectedToken] = useState<OAuthToken | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuToken, setMenuToken] = useState<OAuthToken | null>(null);
  const [bulkActionDialog, setBulkActionDialog] = useState(false);
  const [bulkAction, setBulkAction] = useState<'revoke' | 'delete' | null>(null);
  
  // Filters
  const [filterType, setFilterType] = useState<TokenType | 'all'>('all');
  const [filterStatus, setFilterStatus] = useState<TokenStatus | 'all'>('all');
  const [filterClient, setFilterClient] = useState<string>('all');
  const [filterUser, setFilterUser] = useState<string>('');
  const [filterExpired, setFilterExpired] = useState<boolean>(false);
  const [filterExpiringSoon, setFilterExpiringSoon] = useState<boolean>(false);

  // Fetch tokens on mount and when filters change
  useEffect(() => {
    fetchTokens({
      page: page + 1,
      limit: rowsPerPage,
      search: searchQuery,
      type: filterType !== 'all' ? filterType : undefined,
      status: filterStatus !== 'all' ? filterStatus : undefined,
      clientId: filterClient !== 'all' ? filterClient : undefined,
      userId: filterUser || undefined,
      includeExpired: filterExpired,
    });
  }, [page, rowsPerPage, searchQuery, filterType, filterStatus, filterClient, filterUser, filterExpired]);

  // Calculate token statistics
  const tokenStats = useMemo(() => {
    const now = new Date();
    const stats = {
      total: tokens.length,
      active: 0,
      revoked: 0,
      expired: 0,
      expiringSoon: 0,
      byType: {} as Record<TokenType, number>,
    };

    tokens.forEach(token => {
      if (token.status === 'active') stats.active++;
      if (token.status === 'revoked') stats.revoked++;
      
      const expiresAt = new Date(token.expiresAt);
      if (isAfter(now, expiresAt)) {
        stats.expired++;
      } else if (isAfter(addSeconds(now, 3600), expiresAt)) {
        stats.expiringSoon++;
      }

      stats.byType[token.type] = (stats.byType[token.type] || 0) + 1;
    });

    return stats;
  }, [tokens]);

  // Handlers
  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      setSelectedTokens(tokens.map(t => t.id));
    } else {
      setSelectedTokens([]);
    }
  };

  const handleSelectToken = (tokenId: string) => {
    if (selectedTokens.includes(tokenId)) {
      setSelectedTokens(selectedTokens.filter(id => id !== tokenId));
    } else {
      setSelectedTokens([...selectedTokens, tokenId]);
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, token: OAuthToken) => {
    setAnchorEl(event.currentTarget);
    setMenuToken(token);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setMenuToken(null);
  };

  const handleViewDetails = async (token: OAuthToken) => {
    // Introspect token for latest details
    const details = await introspectToken(token.token);
    setSelectedToken({ ...token, ...details });
    setShowDetails(true);
    handleMenuClose();
  };

  const handleRevokeToken = async (token: OAuthToken) => {
    await revokeToken(token.id);
    handleMenuClose();
    fetchTokens({});
  };

  const handleBulkAction = (action: 'revoke' | 'delete') => {
    setBulkAction(action);
    setBulkActionDialog(true);
  };

  const handleBulkActionConfirm = async () => {
    if (bulkAction === 'revoke') {
      await revokeMultipleTokens(selectedTokens);
    }
    // Add delete logic if needed
    setBulkActionDialog(false);
    setBulkAction(null);
    setSelectedTokens([]);
    fetchTokens({});
  };

  const handleExportTokens = () => {
    const csv = convertToCSV(tokens);
    downloadCSV(csv, 'oauth-tokens.csv');
  };

  const getTokenStatusColor = (token: OAuthToken): 'success' | 'error' | 'warning' | 'default' => {
    const now = new Date();
    const expiresAt = new Date(token.expiresAt);
    
    if (token.status === 'revoked') return 'error';
    if (isAfter(now, expiresAt)) return 'error';
    if (isAfter(addSeconds(now, 3600), expiresAt)) return 'warning';
    if (token.status === 'active') return 'success';
    return 'default';
  };

  const getTokenStatusLabel = (token: OAuthToken): string => {
    const now = new Date();
    const expiresAt = new Date(token.expiresAt);
    
    if (token.status === 'revoked') return 'Revoked';
    if (isAfter(now, expiresAt)) return 'Expired';
    if (isAfter(addSeconds(now, 3600), expiresAt)) return 'Expiring Soon';
    return 'Active';
  };

  const getTokenTypeIcon = (type: TokenType) => {
    switch (type) {
      case 'access_token':
        return <KeyIcon fontSize="small" />;
      case 'refresh_token':
        return <RefreshIcon fontSize="small" />;
      case 'id_token':
        return <PersonIcon fontSize="small" />;
      default:
        return <KeyIcon fontSize="small" />;
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">OAuth Tokens</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<InfoIcon />}
            onClick={() => setShowAnalytics(true)}
          >
            Analytics
          </Button>
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleExportTokens}
          >
            Export
          </Button>
        </Box>
      </Box>

      {/* Statistics Cards */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4">{tokenStats.total}</Typography>
                <Typography variant="body2" color="textSecondary">
                  Total Tokens
                </Typography>
              </Box>
              <KeyIcon sx={{ fontSize: 40, color: 'primary.light' }} />
            </Box>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" color="success.main">
                  {tokenStats.active}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Active Tokens
                </Typography>
              </Box>
              <CheckCircleIcon sx={{ fontSize: 40, color: 'success.light' }} />
            </Box>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" color="warning.main">
                  {tokenStats.expiringSoon}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Expiring Soon
                </Typography>
              </Box>
              <ScheduleIcon sx={{ fontSize: 40, color: 'warning.light' }} />
            </Box>
          </Card>
        </Grid>
        
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Box>
                <Typography variant="h4" color="error.main">
                  {tokenStats.revoked}
                </Typography>
                <Typography variant="body2" color="textSecondary">
                  Revoked Tokens
                </Typography>
              </Box>
              <BlockIcon sx={{ fontSize: 40, color: 'error.light' }} />
            </Box>
          </Card>
        </Grid>
      </Grid>

      {/* Filters */}
      <Card sx={{ mb: 3, p: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
          <TextField
            placeholder="Search by token, user, or client..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            sx={{ flexGrow: 1, minWidth: 300 }}
          />
          
          <FormControl sx={{ minWidth: 120 }}>
            <Select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as TokenType | 'all')}
              displayEmpty
            >
              <MenuItem value="all">All Types</MenuItem>
              <MenuItem value="access_token">Access Token</MenuItem>
              <MenuItem value="refresh_token">Refresh Token</MenuItem>
              <MenuItem value="id_token">ID Token</MenuItem>
            </Select>
          </FormControl>

          <FormControl sx={{ minWidth: 120 }}>
            <Select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as TokenStatus | 'all')}
              displayEmpty
            >
              <MenuItem value="all">All Status</MenuItem>
              <MenuItem value="active">Active</MenuItem>
              <MenuItem value="revoked">Revoked</MenuItem>
              <MenuItem value="expired">Expired</MenuItem>
            </Select>
          </FormControl>

          <TextField
            placeholder="Filter by user ID"
            value={filterUser}
            onChange={(e) => setFilterUser(e.target.value)}
            sx={{ width: 200 }}
          />

          <IconButton onClick={() => fetchTokens({})} title="Refresh">
            <RefreshIcon />
          </IconButton>
        </Box>

        {(filterExpired || filterExpiringSoon || selectedTokens.length > 0) && (
          <Box sx={{ mt: 2, display: 'flex', gap: 1, alignItems: 'center' }}>
            {filterExpired && (
              <Chip
                label="Including Expired"
                onDelete={() => setFilterExpired(false)}
                size="small"
              />
            )}
            {filterExpiringSoon && (
              <Chip
                label="Expiring Soon"
                onDelete={() => setFilterExpiringSoon(false)}
                size="small"
                color="warning"
              />
            )}
            {selectedTokens.length > 0 && (
              <Chip
                label={`${selectedTokens.length} selected`}
                onDelete={() => setSelectedTokens([])}
                size="small"
                color="primary"
              />
            )}
          </Box>
        )}
      </Card>

      {/* Bulk Actions */}
      {selectedTokens.length > 0 && (
        <Card sx={{ mb: 2, p: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography variant="body1">
              {selectedTokens.length} token{selectedTokens.length > 1 ? 's' : ''} selected
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="outlined"
                color="error"
                startIcon={<BlockIcon />}
                onClick={() => handleBulkAction('revoke')}
              >
                Revoke Selected
              </Button>
              <Button
                variant="text"
                startIcon={<ClearAllIcon />}
                onClick={() => setSelectedTokens([])}
              >
                Clear Selection
              </Button>
            </Box>
          </Box>
        </Card>
      )}

      {/* Error Alert */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Tokens Table */}
      <Card>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    indeterminate={selectedTokens.length > 0 && selectedTokens.length < tokens.length}
                    checked={tokens.length > 0 && selectedTokens.length === tokens.length}
                    onChange={handleSelectAll}
                  />
                </TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Client</TableCell>
                <TableCell>User</TableCell>
                <TableCell>Scopes</TableCell>
                <TableCell>Issued</TableCell>
                <TableCell>Expires</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                // Loading skeletons
                Array.from({ length: 5 }).map((_, index) => (
                  <TableRow key={index}>
                    {Array.from({ length: 9 }).map((_, cellIndex) => (
                      <TableCell key={cellIndex}>
                        <Skeleton variant="text" />
                      </TableCell>
                    ))
                  </TableRow>
                ))
              ) : tokens.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} align="center">
                    <Typography variant="body2" color="textSecondary">
                      No tokens found
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                tokens.map((token) => (
                  <TableRow key={token.id} hover>
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selectedTokens.includes(token.id)}
                        onChange={() => handleSelectToken(token.id)}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {getTokenTypeIcon(token.type)}
                        <Typography variant="body2">
                          {token.type.replace('_', ' ')}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={getTokenStatusLabel(token)}
                        size="small"
                        color={getTokenStatusColor(token)}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <AppsIcon fontSize="small" color="action" />
                        <Tooltip title={token.clientId}>
                          <Typography variant="body2" noWrap sx={{ maxWidth: 150 }}>
                            {token.clientName || token.clientId}
                          </Typography>
                        </Tooltip>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <PersonIcon fontSize="small" color="action" />
                        <Tooltip title={token.userId}>
                          <Typography variant="body2" noWrap sx={{ maxWidth: 150 }}>
                            {token.userName || token.userId}
                          </Typography>
                        </Tooltip>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Tooltip title={token.scopes.join(', ')}>
                        <Typography variant="body2" noWrap sx={{ maxWidth: 200 }}>
                          {token.scopes.length} scope(s)
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Tooltip title={format(new Date(token.issuedAt), 'PPpp')}>
                        <Typography variant="body2">
                          {formatDistanceToNow(new Date(token.issuedAt), { addSuffix: true })}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <Tooltip title={format(new Date(token.expiresAt), 'PPpp')}>
                        <Typography variant="body2">
                          {formatDistanceToNow(new Date(token.expiresAt), { addSuffix: true })}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        onClick={(e) => handleMenuOpen(e, token)}
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
        <MenuItem onClick={() => menuToken && handleViewDetails(menuToken)}>
          <InfoIcon fontSize="small" sx={{ mr: 1 }} />
          View Details
        </MenuItem>
        <MenuItem 
          onClick={() => menuToken && handleRevokeToken(menuToken)}
          disabled={menuToken?.status === 'revoked'}
        >
          <BlockIcon fontSize="small" sx={{ mr: 1 }} />
          Revoke Token
        </MenuItem>
      </Menu>

      {/* Bulk Action Confirmation Dialog */}
      <Dialog open={bulkActionDialog} onClose={() => setBulkActionDialog(false)}>
        <DialogTitle>
          {bulkAction === 'revoke' ? 'Revoke Tokens' : 'Delete Tokens'}
        </DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="body2">
              Are you sure you want to {bulkAction} {selectedTokens.length} token(s)?
              This action cannot be undone.
            </Typography>
          </Alert>
          <Typography variant="body2">
            {bulkAction === 'revoke' 
              ? 'Revoking tokens will immediately invalidate them and prevent their use.'
              : 'Deleting tokens will permanently remove them from the system.'}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBulkActionDialog(false)}>Cancel</Button>
          <Button 
            onClick={handleBulkActionConfirm} 
            color="error" 
            variant="contained"
          >
            {bulkAction === 'revoke' ? 'Revoke' : 'Delete'} {selectedTokens.length} Token(s)
          </Button>
        </DialogActions>
      </Dialog>

      {/* Token Details Dialog */}
      {selectedToken && (
        <TokenDetailsDialog
          token={selectedToken}
          open={showDetails}
          onClose={() => {
            setShowDetails(false);
            setSelectedToken(null);
          }}
          onRevoke={() => {
            handleRevokeToken(selectedToken);
            setShowDetails(false);
          }}
        />
      )}

      {/* Token Analytics Dialog */}
      <TokenAnalytics
        open={showAnalytics}
        onClose={() => setShowAnalytics(false)}
      />
    </Box>
  );
};

// Helper functions
const convertToCSV = (tokens: OAuthToken[]): string => {
  const headers = ['Type', 'Status', 'Client', 'User', 'Scopes', 'Issued At', 'Expires At'];
  const rows = tokens.map(token => [
    token.type,
    token.status,
    token.clientName || token.clientId,
    token.userName || token.userId,
    token.scopes.join(';'),
    token.issuedAt,
    token.expiresAt,
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

export default OAuthTokens;