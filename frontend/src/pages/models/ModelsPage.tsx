import { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Grid,
  TextField,
  InputAdornment,
  FormControl,
  Select,
  MenuItem,
  InputLabel,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Skeleton,
} from '@mui/material';
import {
  Add,
  Search,
  ViewModule,
  ViewList,
} from '@mui/icons-material';
import { ModelCard } from '@/components/models/ModelCard';
import { ModelDialog } from '@/components/models/ModelDialog';
import { 
  useModels, 
  useCreateModel, 
  useUpdateModel, 
  useDeleteModel,
  useToggleModelStatus 
} from '@/hooks/useModels';
import { ModelProfile } from '@/types/models';

const ModelsPage = () => {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelProfile | undefined>();
  const [filters, setFilters] = useState({
    search: '',
    status: 'all',
    sortBy: 'created_at',
  });

  // API hooks
  const { data, isPending } = useModels({
    search: filters.search,
    // Add other query params as needed
  });
  const createModel = useCreateModel();
  const updateModel = useUpdateModel();
  const deleteModel = useDeleteModel();
  const toggleStatus = useToggleModelStatus();

  const models = data?.items || [];

  const handleEdit = (model: ModelProfile) => {
    setEditingModel(model);
    setDialogOpen(true);
  };

  const handleDelete = async (modelId: string) => {
    if (window.confirm('Are you sure you want to delete this model profile?')) {
      await deleteModel.mutateAsync(modelId);
    }
  };

  const handleToggleStatus = async (modelId: string, isActive: boolean) => {
    await toggleStatus.mutateAsync({ modelId, isActive });
  };

  const handleSubmit = async (data: any) => {
    if (editingModel) {
      await updateModel.mutateAsync({
        modelId: editingModel.id,
        data,
      });
    } else {
      await createModel.mutateAsync(data);
    }
    setDialogOpen(false);
    setEditingModel(undefined);
  };

  const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: 'grid' | 'list' | null) => {
    if (newMode !== null) {
      setViewMode(newMode);
    }
  };

  const LoadingCards = () => (
    <>
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <Grid item xs={12} sm={6} md={4} key={i}>
          <Skeleton variant="rectangular" height={320} />
        </Grid>
      ))}
    </>
  );

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Models</Typography>
        <Button
          variant="contained"
          startIcon={<Add />}
          onClick={() => {
            setEditingModel(undefined);
            setDialogOpen(true);
          }}
        >
          Add Model
        </Button>
      </Box>

      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2} alignItems="center">
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              placeholder="Search models..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Search />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth>
              <InputLabel>Status</InputLabel>
              <Select
                value={filters.status}
                label="Status"
                onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="inactive">Inactive</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <FormControl fullWidth>
              <InputLabel>Sort By</InputLabel>
              <Select
                value={filters.sortBy}
                label="Sort By"
                onChange={(e) => setFilters({ ...filters, sortBy: e.target.value })}
              >
                <MenuItem value="created_at">Newest</MenuItem>
                <MenuItem value="stage_name">Name</MenuItem>
                <MenuItem value="total_earnings">Earnings</MenuItem>
                <MenuItem value="total_fans">Fans</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={12} md={2}>
            <ToggleButtonGroup
              value={viewMode}
              exclusive
              onChange={handleViewModeChange}
              fullWidth
            >
              <ToggleButton value="grid" aria-label="grid view">
                <ViewModule />
              </ToggleButton>
              <ToggleButton value="list" aria-label="list view">
                <ViewList />
              </ToggleButton>
            </ToggleButtonGroup>
          </Grid>
        </Grid>
      </Paper>

      {isPending ? (
        <Grid container spacing={3}>
          <LoadingCards />
        </Grid>
      ) : models.length === 0 ? (
        <Paper sx={{ p: 6, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No models found
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            {filters.search ? 'Try adjusting your search criteria' : 'Get started by adding your first model'}
          </Typography>
          {!filters.search && (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => setDialogOpen(true)}
            >
              Add First Model
            </Button>
          )}
        </Paper>
      ) : viewMode === 'grid' ? (
        <Grid container spacing={3}>
          {models.map((model: any) => (
            <Grid item xs={12} sm={6} md={4} key={model.id}>
              <ModelCard
                model={model}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onToggleStatus={handleToggleStatus}
              />
            </Grid>
          ))}
        </Grid>
      ) : (
        <Paper>
          {/* TODO: Implement list view */}
          <Typography sx={{ p: 3 }}>List view coming soon...</Typography>
        </Paper>
      )}

      <ModelDialog
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setEditingModel(undefined);
        }}
        onSubmit={handleSubmit}
        model={editingModel}
        loading={createModel.isPending || updateModel.isPending}
      />
    </Box>
  );
};

export default ModelsPage;
