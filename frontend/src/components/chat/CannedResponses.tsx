import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Box,
  Typography,
  Tabs,
  Tab,
  SpeedDial,
  SpeedDialIcon,
  SpeedDialAction,
  Chip,
  InputAdornment,
  Divider } from '@mui/material';
import {
  Edit,
  Delete,
  Add,
  TextFields,
  QuickreplyOutlined,
  Search,
  Close,
  Save } from '@mui/icons-material';
import { useToast } from '@/components/common/Toaster';

interface CannedResponse {
  id: string;
  title: string;
  content: string;
  category: string;
  shortcut?: string;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

interface CannedResponsesProps {
  onSelectResponse: (response: string) => void;
}

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
      id={`canned-responses-tabpanel-${index}`}
      aria-labelledby={`canned-responses-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 2 }}>{children}</Box>}
    </div>
  );
};

export const CannedResponses = ({ onSelectResponse }: CannedResponsesProps) => {
  const { error, success } = useToast();
  const [open, setOpen] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(0);
  const [editingResponse, setEditingResponse] = useState<CannedResponse | null>(null);
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    category: '',
    shortcut: '' });

  // Mock data - replace with API call
  const [responses, setResponses] = useState<CannedResponse[]>([
    {
      id: '1',
      title: 'Welcome Message',
      content: 'Hey there! Welcome to my page! 😊 Feel free to check out my latest content and let me know what you think!',
      category: 'Greetings',
      shortcut: '/welcome',
      usage_count: 150,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z' },
    {
      id: '2',
      title: 'Thank You',
      content: 'Thank you so much for your support! It really means a lot to me. Can\'t wait to share more exclusive content with you!',
      category: 'Greetings',
      shortcut: '/thanks',
      usage_count: 230,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z' },
    {
      id: '3',
      title: 'New Content Alert',
      content: 'Just posted something special for you! Check it out and let me know your thoughts 💕',
      category: 'Promotions',
      shortcut: '/new',
      usage_count: 89,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z' },
    {
      id: '4',
      title: 'Custom Request Info',
      content: 'I\'d love to create custom content for you! Send me your ideas and we can discuss the details.',
      category: 'Business',
      shortcut: '/custom',
      usage_count: 67,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z' },
    {
      id: '5',
      title: 'Subscription Benefits',
      content: 'As a subscriber, you get access to all my exclusive content, priority messaging, and special discounts on custom requests!',
      category: 'Business',
      shortcut: '/benefits',
      usage_count: 112,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z' },
  ]);

  const categories = ['All', 'Greetings', 'Promotions', 'Business', 'Personal'];

  const filteredResponses = responses.filter((response) => {
    const matchesSearch = response.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         response.content.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (response.shortcut && response.shortcut.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesCategory = selectedCategory === 0 || response.category === categories[selectedCategory];
    
    return matchesSearch && matchesCategory;
  });

  const handleOpenDialog = (response?: CannedResponse) => {
    if (response) {
      setEditingResponse(response);
      setFormData({
        title: response.title,
        content: response.content,
        category: response.category,
        shortcut: response.shortcut || '' });
    } else {
      setEditingResponse(null);
      setFormData({
        title: '',
        content: '',
        category: 'Greetings',
        shortcut: '' });
    }
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingResponse(null);
    setFormData({
      title: '',
      content: '',
      category: '',
      shortcut: '' });
  };

  const handleSave = async () => {
    try {
      if (editingResponse) {
        // Update existing response
        const updated = {
          ...editingResponse,
          ...formData,
          updated_at: new Date().toISOString() };
        setResponses(responses.map(r => r.id === editingResponse.id ? updated : r));
        success('Response updated successfully');
      } else {
        // Create new response
        const newResponse: CannedResponse = {
          id: Date.now().toString(),
          ...formData,
          usage_count: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString() };
        setResponses([...responses, newResponse]);
        success('Response created successfully');
      }
      handleCloseDialog();
    } catch (err) {
      error('Failed to save response');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      setResponses(responses.filter(r => r.id !== id));
      success('Response deleted successfully');
    } catch (err) {
      error('Failed to delete response');
    }
  };

  const handleUseResponse = (response: CannedResponse) => {
    onSelectResponse(response.content);
    // Update usage count
    setResponses(responses.map(r => 
      r.id === response.id 
        ? { ...r, usage_count: r.usage_count + 1 }
        : r
    ));
    setOpen(false);
  };

  const speedDialActions = [
    { icon: <Add />, name: 'Create New', action: () => handleOpenDialog() },
    { icon: <TextFields />, name: 'Manage Responses', action: () => setOpen(true) },
  ];

  return (
    <>
      <SpeedDial
        ariaLabel="Canned Responses"
        sx={{ position: 'absolute', bottom: 16, right: 16 }}
        icon={<SpeedDialIcon icon={<QuickreplyOutlined />} />}
        onClose={() => {}}
        onOpen={() => {}}
      >
        {speedDialActions.map((action) => (
          <SpeedDialAction
            key={action.name}
            icon={action.icon}
            tooltipTitle={action.name}
            onClick={action.action}
          />
        ))}
      </SpeedDial>

      {/* Canned Responses List Dialog */}
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Canned Responses</Typography>
            <IconButton onClick={() => setOpen(false)} size="small">
              <Close />
            </IconButton>
          </Box>
        </DialogTitle>
        
        <DialogContent dividers>
          <TextField
            fullWidth
            placeholder="Search responses..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ) }}
            sx={{ mb: 2 }}
          />

          <Tabs
            value={selectedCategory}
            onChange={(_, value) => setSelectedCategory(value)}
            sx={{ mb: 2 }}
          >
            {categories.map((category, ) => (
              <Tab key={category} label={category} />
            ))}
          </Tabs>

          <List>
            {filteredResponses.map((response, index) => (
              <Box key={response.id}>
                {index > 0 && <Divider />}
                <ListItem
                  button
                  onClick={() => handleUseResponse(response)}
                  sx={{
                    '&:hover': {
                      backgroundColor: 'action.hover' } }}
                >
                  <ListItemText
                    primary={
                      <Box display="flex" alignItems="center" gap={1}>
                        <Typography variant="subtitle2">{response.title}</Typography>
                        {response.shortcut && (
                          <Chip
                            label={response.shortcut}
                            size="small"
                            variant="outlined"
                          />
                        )}
                        <Chip
                          label={`Used ${response.usage_count} times`}
                          size="small"
                          color="default"
                        />
                      </Box>
                    }
                    secondary={
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden' }}
                      >
                        {response.content}
                      </Typography>
                    }
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDialog(response);
                      }}
                    >
                      <Edit />
                    </IconButton>
                    <IconButton
                      edge="end"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(response.id);
                      }}
                    >
                      <Delete />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              </Box>
            ))}
          </List>

          {filteredResponses.length === 0 && (
            <Box textAlign="center" py={4}>
              <Typography variant="body2" color="text.secondary">
                No responses found
              </Typography>
            </Box>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={() => handleOpenDialog()} startIcon={<Add />}>
            Create New Response
          </Button>
        </DialogActions>
      </Dialog>

      {/* Create/Edit Response Dialog */}
      <Dialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          {editingResponse ? 'Edit Response' : 'Create New Response'}
        </DialogTitle>
        
        <DialogContent dividers>
          <TextField
            fullWidth
            label="Title"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            margin="normal"
          />
          
          <TextField
            fullWidth
            label="Content"
            value={formData.content}
            onChange={(e) => setFormData({ ...formData, content: e.target.value })}
            multiline
            rows={4}
            margin="normal"
          />
          
          <TextField
            fullWidth
            select
            label=""
            value={formData.category}
            onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            margin="normal"
            SelectProps={{
              native: true }}
          >
            <option value="">Select a category</option>
            {categories.slice(1).map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </TextField>
          
          <TextField
            fullWidth
            label="Shortcut (optional)"
            value={formData.shortcut}
            onChange={(e) => setFormData({ ...formData, shortcut: e.target.value })}
            placeholder="/example"
            margin="normal"
            helperText="Type this shortcut in a message to quickly insert this response"
          />
        </DialogContent>

        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button
            onClick={handleSave}
            variant="contained"
            startIcon={<Save />}
            disabled={!formData.title || !formData.content || !formData.category}
          >
            {editingResponse ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};
