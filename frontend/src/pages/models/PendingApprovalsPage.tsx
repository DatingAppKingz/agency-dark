import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Avatar,
  Chip,
  IconButton,
  Button,
  TextField,
  InputAdornment,
  Badge,
  Tooltip,
} from '@mui/material';
import {
  Search,
  Visibility,
  CheckCircle,
  Cancel,
  Refresh,
  FilterList,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { usePendingModels } from '@/hooks/useModels';
import { ModelApprovalDialog } from '@/components/models/ModelApprovalDialog';
import { ModelProfile, ModelStatus } from '@/types/models';
import { useAuthStore } from '@/store/authStore';
import { UserRole } from '@/types/auth';
import { Navigate } from 'react-router-dom';

export default function PendingApprovalsPage() {
  const { user } = useAuthStore();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModel, setSelectedModel] = useState<ModelProfile | null>(null);
  const [approvalDialogOpen, setApprovalDialogOpen] = useState(false);

  // Check permissions
  const hasPermission =
    user &&
    [UserRole.SUPER_ADMIN, UserRole.AGENCY_OWNER, UserRole.AGENCY_ADMIN].includes(
      user.role
    );

  const { data, isLoading, refetch } = usePendingModels({
    limit: rowsPerPage,
    offset: page * rowsPerPage,
  });

  if (!hasPermission) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const handleOpenApproval = (model: ModelProfile) => {
    setSelectedModel(model);
    setApprovalDialogOpen(true);
  };

  const handleCloseApproval = () => {
    setApprovalDialogOpen(false);
    setSelectedModel(null);
  };

  const handleApprovalComplete = () => {
    refetch();
    handleCloseApproval();
  };

  const filteredModels = data?.filter((model) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      model.stage_name?.toLowerCase().includes(query) ||
      model.real_name?.toLowerCase().includes(query) ||
      model.platform_username?.toLowerCase().includes(query) ||
      model.email?.toLowerCase().includes(query)
    );
  });

  const getStatusColor = (status: ModelStatus) => {
    switch (status) {
      case ModelStatus.PENDING:
        return 'warning';
      case ModelStatus.UNDER_REVIEW:
        return 'info';
      default:
        return 'default';
    }
  };

  const getProfileCompletion = (model: ModelProfile) => {
    const fields = [
      model.stage_name,
      model.platform,
      model.platform_username,
      model.bio,
      model.profile_photo_url,
    ];
    const completed = fields.filter(Boolean).length;
    return {
      completed,
      total: fields.length,
      isComplete: completed === fields.length,
    };
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Pending Model Approvals
          </Typography>
          <Typography variant="body2" color="textSecondary">
            Review and approve model applications
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Badge badgeContent={data?.length || 0} color="warning">
            <Button variant="outlined" startIcon={<FilterList />}>
              Filter
            </Button>
          </Badge>
          <Button
            variant="outlined"
            startIcon={<Refresh />}
            onClick={() => refetch()}
            disabled={isLoading}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      <Paper sx={{ mb: 3 }}>
        <Box sx={{ p: 2 }}>
          <TextField
            fullWidth
            placeholder="Search by name, username, or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
            }}
          />
        </Box>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Model</TableCell>
              <TableCell>Platform</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Profile Completion</TableCell>
              <TableCell>Documents</TableCell>
              <TableCell>Applied</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  Loading...
                </TableCell>
              </TableRow>
            ) : filteredModels?.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center">
                  No pending approvals
                </TableCell>
              </TableRow>
            ) : (
              filteredModels?.map((model) => {
                const completion = getProfileCompletion(model);
                return (
                  <TableRow key={model.id}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Avatar src={model.profile_photo_url}>
                          {model.stage_name?.charAt(0)}
                        </Avatar>
                        <Box>
                          <Typography variant="body1">{model.stage_name}</Typography>
                          <Typography variant="caption" color="textSecondary">
                            {model.real_name}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Chip label={model.platform} size="small" />
                      <Typography variant="caption" display="block">
                        @{model.platform_username}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={model.status}
                        size="small"
                        color={getStatusColor(model.status)}
                      />
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {completion.isComplete ? (
                          <CheckCircle color="success" fontSize="small" />
                        ) : (
                          <Cancel color="error" fontSize="small" />
                        )}
                        <Typography variant="body2">
                          {completion.completed}/{completion.total}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell>
                      {model.id_document_url ? (
                        <Chip
                          label="Uploaded"
                          size="small"
                          color="success"
                          variant="outlined"
                        />
                      ) : (
                        <Chip
                          label="Missing"
                          size="small"
                          color="error"
                          variant="outlined"
                        />
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {format(new Date(model.created_at), 'MMM dd, yyyy')}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Review Application">
                        <IconButton
                          color="primary"
                          onClick={() => handleOpenApproval(model)}
                        >
                          <Visibility />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[5, 10, 25, 50]}
          component="div"
          count={data?.length || 0}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={handleChangePage}
          onRowsPerPageChange={handleChangeRowsPerPage}
        />
      </TableContainer>

      {selectedModel && (
        <ModelApprovalDialog
          open={approvalDialogOpen}
          onClose={handleCloseApproval}
          model={selectedModel}
          onApprove={handleApprovalComplete}
        />
      )}
    </Box>
  );
}