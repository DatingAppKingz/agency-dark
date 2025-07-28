import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  CardActions,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  TextField,
  InputAdornment,
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Search as SearchIcon,
  MoreVert as MoreIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  FileCopy as DuplicateIcon,
  Download as ExportIcon,
  Schedule as ScheduleIcon,
  Share as ShareIcon,
  Assessment as ReportIcon,
  ShowChart as ChartIcon,
  TableChart as TableIcon,
  Dashboard as DashboardIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { format } from 'date-fns';
import { reportsService } from '@/services/api/reports';
import { ReportType, ReportTemplate } from '@/types/reports';
import { useAuth } from '@/hooks/useAuth';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div role="tabpanel" hidden={value !== index} {...other}>
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const ReportsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<ReportTemplate | null>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [duplicateDialogOpen, setDuplicateDialogOpen] = useState(false);
  const [duplicateName, setDuplicateName] = useState('');

  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  // Fetch templates
  const { data: templates, isLoading } = useQuery({
    queryKey: ['report-templates', activeTab, searchTerm],
    queryFn: () => reportsService.getTemplates({
      type: activeTab === 0 ? undefined : Object.values(ReportType)[activeTab - 1],
      search: searchTerm,
    }),
  });

  // Fetch predefined templates
  const { data: predefinedTemplates } = useQuery({
    queryKey: ['predefined-templates'],
    queryFn: () => reportsService.getPredefinedTemplates(),
    enabled: activeTab === 0,
  });

  // Delete template
  const deleteTemplate = useMutation({
    mutationFn: (id: string) => reportsService.deleteTemplate(id),
    onSuccess: () => {
      toast.success('Report template deleted');
      queryClient.invalidateQueries({ queryKey: ['report-templates'] });
      setDeleteDialogOpen(false);
      setSelectedTemplate(null);
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to delete template');
    },
  });

  // Duplicate template
  const duplicateTemplate = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      reportsService.duplicateTemplate(id, name),
    onSuccess: () => {
      toast.success('Report template duplicated');
      queryClient.invalidateQueries({ queryKey: ['report-templates'] });
      setDuplicateDialogOpen(false);
      setSelectedTemplate(null);
      setDuplicateName('');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to duplicate template');
    },
  });

  const handleMenuClick = (event: React.MouseEvent<HTMLElement>, template: ReportTemplate) => {
    setAnchorEl(event.currentTarget);
    setSelectedTemplate(template);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleCreateReport = () => {
    navigate('/dashboard/reports/builder');
  };

  const handleEditTemplate = (template: ReportTemplate) => {
    navigate(`/dashboard/reports/builder/${template.id}`);
  };

  const handleViewReport = (template: ReportTemplate) => {
    navigate(`/dashboard/reports/view/${template.id}`);
  };

  const handleExportReport = async (template: ReportTemplate) => {
    try {
      const exportData = await reportsService.exportReport(template.id, 'pdf');
      toast.success('Report export started. You will be notified when it\'s ready.');
    } catch (error: any) {
      toast.error('Failed to export report');
    }
  };

  const getTemplateIcon = (type: ReportType) => {
    switch (type) {
      case ReportType.REVENUE:
        return <ChartIcon />;
      case ReportType.USER_ACTIVITY:
        return <TableIcon />;
      case ReportType.MESSAGE_ANALYTICS:
        return <ChartIcon />;
      case ReportType.CONTENT_PERFORMANCE:
        return <DashboardIcon />;
      case ReportType.SUBSCRIPTION_METRICS:
        return <ChartIcon />;
      default:
        return <ReportIcon />;
    }
  };

  const renderTemplateCard = (template: ReportTemplate, isPredefined = false) => (
    <Grid item xs={12} sm={6} md={4} key={template.id}>
      <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        <CardContent sx={{ flexGrow: 1 }}>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
            <Box display="flex" alignItems="center" gap={1}>
              {getTemplateIcon(template.type)}
              <Typography variant="h6" noWrap>
                {template.name}
              </Typography>
            </Box>
            {!isPredefined && (
              <IconButton size="small" onClick={(e) => handleMenuClick(e, template)}>
                <MoreIcon />
              </IconButton>
            )}
          </Box>

          {template.description && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {template.description}
            </Typography>
          )}

          <Box display="flex" gap={1} flexWrap="wrap" mb={2}>
            <Chip label={template.type.replace(/_/g, ' ')} size="small" />
            <Chip label={`${template.widgets.length} widgets`} size="small" />
            {template.refreshInterval && (
              <Chip
                icon={<ScheduleIcon />}
                label={`Refreshes every ${template.refreshInterval}s`}
                size="small"
              />
            )}
          </Box>

          <Typography variant="caption" color="text.secondary">
            Updated {format(new Date(template.updatedAt), 'MMM d, yyyy')}
          </Typography>
        </CardContent>
        <CardActions>
          <Button size="small" onClick={() => handleViewReport(template)}>
            View Report
          </Button>
          {!isPredefined && (
            <Button size="small" onClick={() => handleEditTemplate(template)}>
              Edit
            </Button>
          )}
        </CardActions>
      </Card>
    </Grid>
  );

  return (
    <Container maxWidth="xl">
      <Box py={4}>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Reports
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Create and manage custom reports for your analytics
            </Typography>
          </Box>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateReport}
          >
            Create Report
          </Button>
        </Box>

        {/* Search */}
        <TextField
          fullWidth
          placeholder="Search reports..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 3 }}
        />

        {/* Tabs */}
        <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)} sx={{ mb: 3 }}>
          <Tab label="All Reports" />
          <Tab label="Revenue" />
          <Tab label="User Activity" />
          <Tab label="Messages" />
          <Tab label="Content" />
          <Tab label="Subscriptions" />
        </Tabs>

        {/* Tab Panels */}
        <TabPanel value={activeTab} index={0}>
          {predefinedTemplates && predefinedTemplates.length > 0 && (
            <>
              <Typography variant="h6" gutterBottom>
                Template Gallery
              </Typography>
              <Grid container spacing={3} sx={{ mb: 4 }}>
                {predefinedTemplates.map((template) => renderTemplateCard(template, true))}
              </Grid>
              <Typography variant="h6" gutterBottom sx={{ mt: 4 }}>
                My Reports
              </Typography>
            </>
          )}
          <Grid container spacing={3}>
            {isLoading ? (
              <Grid item xs={12}>
                <Typography variant="body1" color="text.secondary" align="center">
                  Loading reports...
                </Typography>
              </Grid>
            ) : templates?.items.length === 0 ? (
              <Grid item xs={12}>
                <Alert severity="info">
                  No custom reports yet. Create your first report or use a template from the gallery.
                </Alert>
              </Grid>
            ) : (
              templates?.items.map((template) => renderTemplateCard(template))
            )}
          </Grid>
        </TabPanel>

        {[ReportType.REVENUE, ReportType.USER_ACTIVITY, ReportType.MESSAGE_ANALYTICS, ReportType.CONTENT_PERFORMANCE, ReportType.SUBSCRIPTION_METRICS].map((type, index) => (
          <TabPanel key={type} value={activeTab} index={index + 1}>
            <Grid container spacing={3}>
              {isLoading ? (
                <Grid item xs={12}>
                  <Typography variant="body1" color="text.secondary" align="center">
                    Loading reports...
                  </Typography>
                </Grid>
              ) : templates?.items.length === 0 ? (
                <Grid item xs={12}>
                  <Alert severity="info">
                    No {type.replace(/_/g, ' ').toLowerCase()} reports yet.
                  </Alert>
                </Grid>
              ) : (
                templates?.items.map((template) => renderTemplateCard(template))
              )}
            </Grid>
          </TabPanel>
        ))}

        {/* Context Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
        >
          <MenuItem
            onClick={() => {
              if (selectedTemplate) {
                handleEditTemplate(selectedTemplate);
              }
              handleMenuClose();
            }}
          >
            <EditIcon sx={{ mr: 1 }} fontSize="small" />
            Edit
          </MenuItem>
          <MenuItem
            onClick={() => {
              if (selectedTemplate) {
                setDuplicateName(`${selectedTemplate.name} (Copy)`);
                setDuplicateDialogOpen(true);
              }
              handleMenuClose();
            }}
          >
            <DuplicateIcon sx={{ mr: 1 }} fontSize="small" />
            Duplicate
          </MenuItem>
          <MenuItem
            onClick={() => {
              if (selectedTemplate) {
                handleExportReport(selectedTemplate);
              }
              handleMenuClose();
            }}
          >
            <ExportIcon sx={{ mr: 1 }} fontSize="small" />
            Export
          </MenuItem>
          <MenuItem
            onClick={() => {
              setDeleteDialogOpen(true);
              handleMenuClose();
            }}
          >
            <DeleteIcon sx={{ mr: 1 }} fontSize="small" color="error" />
            Delete
          </MenuItem>
        </Menu>

        {/* Delete Dialog */}
        <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
          <DialogTitle>Delete Report Template</DialogTitle>
          <DialogContent>
            <Typography>
              Are you sure you want to delete "{selectedTemplate?.name}"? This action cannot be undone.
            </Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button
              color="error"
              variant="contained"
              onClick={() => {
                if (selectedTemplate) {
                  deleteTemplate.mutate(selectedTemplate.id);
                }
              }}
              disabled={deleteTemplate.isLoading}
            >
              Delete
            </Button>
          </DialogActions>
        </Dialog>

        {/* Duplicate Dialog */}
        <Dialog open={duplicateDialogOpen} onClose={() => setDuplicateDialogOpen(false)}>
          <DialogTitle>Duplicate Report Template</DialogTitle>
          <DialogContent>
            <TextField
              label="New Report Name"
              fullWidth
              value={duplicateName}
              onChange={(e) => setDuplicateName(e.target.value)}
              sx={{ mt: 2 }}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDuplicateDialogOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={() => {
                if (selectedTemplate && duplicateName) {
                  duplicateTemplate.mutate({ id: selectedTemplate.id, name: duplicateName });
                }
              }}
              disabled={!duplicateName || duplicateTemplate.isLoading}
            >
              Duplicate
            </Button>
          </DialogActions>
        </Dialog>
      </Box>
    </Container>
  );
};

export default ReportsPage;