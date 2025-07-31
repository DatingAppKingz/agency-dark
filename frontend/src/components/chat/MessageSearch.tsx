import { useState, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  TextField,
  InputAdornment,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  Typography,
  Box,
  IconButton,
  Chip,
  CircularProgress,
  Divider } from '@mui/material';
import {
  Search,
  Close,
  Person,
  AccessTime,
  AttachFile,
  Image as ImageIcon,
  VideoFile } from '@mui/icons-material';
import { debounce } from 'lodash';
import { format } from 'date-fns';
import { Message } from '@/types/chat';

interface MessageSearchProps {
  open: boolean;
  onClose: () => void;
  conversationId?: string;
  onMessageSelect?: (message: Message) => void;
}

interface SearchResult {
  message: Message;
  conversationName: string;
  participantName: string;
  participantAvatar?: string;
}

export const MessageSearch = ({ open, onClose, conversationId, onMessageSelect }: MessageSearchProps) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchFilters, setSearchFilters] = useState({
    hasAttachments: false,
    dateRange: 'all' as 'all' | 'today' | 'week' | 'month' });

  // Mock search function - replace with actual API call
  const performSearch = async (term: string) => {
    if (!term.trim()) {
      setSearchResults([]);
      return;
    }

    setIsSearching(true);
    
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));

    // Mock search results
    const mockResults: SearchResult[] = [
      {
        message: {
          id: '1',
          conversation_id: 'conv1',
          sender_id: 'user1',
          sender_type: 'model',
          content: `Found "${term}" in this message about scheduling content`,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          delivered_at: new Date().toISOString(),
          read_at: new Date().toISOString(),
          is_automated: false,
          attachments: [] },
        conversationName: 'John Doe',
        participantName: 'Sarah Model',
        participantAvatar: 'S' },
      {
        message: {
          id: '2',
          conversation_id: 'conv2',
          sender_id: 'user2',
          sender_type: 'fan',
          content: `Message containing "${term}" with some context`,
          created_at: new Date(Date.now() - 86400000).toISOString(),
          updated_at: new Date(Date.now() - 86400000).toISOString(),
          delivered_at: new Date(Date.now() - 86400000).toISOString(),
          read_at: null,
          is_automated: false,
          attachments: [
            {
              id: 'att1',
              type: 'image',
              url: 'https://example.com/image.jpg',
              thumbnail_url: 'https://example.com/thumb.jpg',
              filename: 'photo.jpg',
              size: 1024000,
              mime_type: 'image/jpeg' },
          ] },
        conversationName: 'Mike Smith',
        participantName: 'Mike Smith',
        participantAvatar: 'M' },
    ];

    // Filter by conversation if specified
    const filtered = conversationId 
      ? mockResults.filter(r => r.message.conversation_id === conversationId)
      : mockResults;

    // Apply filters
    let finalResults = filtered;
    
    if (searchFilters.hasAttachments) {
      finalResults = finalResults.filter(r => r.message.attachments && r.message.attachments.length > 0);
    }

    if (searchFilters.dateRange !== 'all') {
      const now = new Date();
      const cutoff = new Date();
      
      switch (searchFilters.dateRange) {
        case 'today':
          cutoff.setHours(0, 0, 0, 0);
          break;
        case 'week':
          cutoff.setDate(now.getDate() - 7);
          break;
        case 'month':
          cutoff.setMonth(now.getMonth() - 1);
          break;
      }
      
      finalResults = finalResults.filter(r => new Date(r.message.created_at) >= cutoff);
    }

    setSearchResults(finalResults);
    setIsSearching(false);
  };

  const debouncedSearch = useCallback(
    debounce((term: string) => performSearch(term), 300),
    [conversationId, searchFilters]
  );

  useEffect(() => {
    debouncedSearch(searchTerm);
  }, [searchTerm, debouncedSearch]);

  const handleMessageClick = (result: SearchResult) => {
    if (onMessageSelect) {
      onMessageSelect(result.message);
    }
    onClose();
  };

  const highlightSearchTerm = (text: string) => {
    if (!searchTerm.trim()) return text;
    
    const parts = text.split(new RegExp(`(${searchTerm})`, 'gi'));
    return parts.map((part, index) => 
      part.toLowerCase() === searchTerm.toLowerCase() ? (
        <Box component="span" key={index} sx={{ backgroundColor: 'warning.light', fontWeight: 'bold' }}>
          {part}
        </Box>
      ) : (
        part
      )
    );
  };

  const getAttachmentIcon = (type: string) => {
    switch (type) {
      case 'image':
        return <ImageIcon fontSize="small" />;
      case 'video':
        return <VideoFile fontSize="small" />;
      default:
        return <AttachFile fontSize="small" />;
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Search Messages</Typography>
          <IconButton onClick={onClose} size="small">
            <Close />
          </IconButton>
        </Box>
      </DialogTitle>
      
      <DialogContent dividers>
        <TextField
          fullWidth
          placeholder="Search messages..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ) }}
          autoFocus
          sx={{ mb: 2 }}
        />

        <Box display="flex" gap={1} mb={2}>
          <Chip
            label="Has Attachments"
            icon={<AttachFile />}
            onClick={() => setSearchFilters(prev => ({ ...prev, hasAttachments: !prev.hasAttachments }))}
            color={searchFilters.hasAttachments ? 'primary' : 'default'}
            variant={searchFilters.hasAttachments ? 'filled' : 'outlined'}
          />
          <Chip
            label="Today"
            icon={<AccessTime />}
            onClick={() => setSearchFilters(prev => ({ ...prev, dateRange: prev.dateRange === 'today' ? 'all' : 'today' }))}
            color={searchFilters.dateRange === 'today' ? 'primary' : 'default'}
            variant={searchFilters.dateRange === 'today' ? 'filled' : 'outlined'}
          />
          <Chip
            label="This Week"
            icon={<AccessTime />}
            onClick={() => setSearchFilters(prev => ({ ...prev, dateRange: prev.dateRange === 'week' ? 'all' : 'week' }))}
            color={searchFilters.dateRange === 'week' ? 'primary' : 'default'}
            variant={searchFilters.dateRange === 'week' ? 'filled' : 'outlined'}
          />
          <Chip
            label="This Month"
            icon={<AccessTime />}
            onClick={() => setSearchFilters(prev => ({ ...prev, dateRange: prev.dateRange === 'month' ? 'all' : 'month' }))}
            color={searchFilters.dateRange === 'month' ? 'primary' : 'default'}
            variant={searchFilters.dateRange === 'month' ? 'filled' : 'outlined'}
          />
        </Box>

        {isSearching ? (
          <Box display="flex" justifyContent="center" py={4}>
            <CircularProgress />
          </Box>
        ) : searchResults.length === 0 ? (
          <Box textAlign="center" py={4}>
            <Typography variant="body2" color="textSecondary">
              {searchTerm.trim() ? 'No messages found' : 'Start typing to search messages'}
            </Typography>
          </Box>
        ) : (
          <List>
            {searchResults.map((result, index) => (
              <Box key={result.message.id}>
                {index > 0 && <Divider />}
                <ListItem
                  button
                  onClick={() => handleMessageClick(result)}
                  sx={{
                    '&:hover': {
                      backgroundColor: 'action.hover' } }}
                >
                  <ListItemAvatar>
                    <Avatar>{result.participantAvatar}</Avatar>
                  </ListItemAvatar>
                  <ListItemText
                    primary={
                      <Box display="flex" justifyContent="space-between" alignItems="center">
                        <Box display="flex" alignItems="center" gap={1}>
                          <Typography variant="subtitle2">
                            {result.conversationName}
                          </Typography>
                          {!conversationId && (
                            <Chip
                              label={result.participantName}
                              size="small"
                              icon={<Person />}
                            />
                          )}
                        </Box>
                        <Typography variant="caption" color="textSecondary">
                          {format(new Date(result.message.created_at), 'MMM d, h:mm a')}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Box>
                        <Typography variant="body2" component="div">
                          {highlightSearchTerm(result.message.content)}
                        </Typography>
                        {result.message.attachments && result.message.attachments.length > 0 && (
                          <Box display="flex" gap={0.5} mt={0.5}>
                            {result.message.attachments.map((attachment) => (
                              <Chip
                                key={attachment.id}
                                icon={getAttachmentIcon(attachment.type)}
                                label={attachment.filename}
                                size="small"
                                variant="outlined"
                              />
                            ))}
                          </Box>
                        )}
                      </Box>
                    }
                  />
                </ListItem>
              </Box>
            ))}
          </List>
        )}

        {searchResults.length > 0 && (
          <Box mt={2} textAlign="center">
            <Typography variant="caption" color="textSecondary">
              Found {searchResults.length} messages
            </Typography>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
};
