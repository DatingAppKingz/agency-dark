import { useState } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemAvatar,
  ListItemText,
  Avatar,
  Typography,
  TextField,
  InputAdornment,
  Chip,
  Badge,
  IconButton,
  Menu,
  MenuItem,
  Divider,
} from '@mui/material';
import {
  Search,
  MoreVert,
  PushPin,
  Archive,
  Delete,
} from '@mui/icons-material';
import { formatDistanceToNow } from 'date-fns';
import { Conversation } from '@/types/chat';
import { useChatStore } from '@/store/chatStore';

interface ConversationListProps {
  conversations: Conversation[];
  onConversationSelect: (conversation: Conversation) => void;
  selectedConversationId?: string;
}

export const ConversationList = ({
  conversations,
  onConversationSelect,
  selectedConversationId,
}: ConversationListProps) => {
  const { filters, setFilters, onlineUsers } = useChatStore();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, conversation: Conversation) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
    setSelectedConversation(conversation);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedConversation(null);
  };

  const filteredConversations = conversations.filter((conv) => {
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      return (
        conv.fan.name.toLowerCase().includes(searchLower) ||
        conv.last_message?.content.toLowerCase().includes(searchLower)
      );
    }
    
    if (filters.status === 'unread') {
      return conv.unread_count > 0;
    }
    
    if (filters.status === 'pinned') {
      return conv.is_pinned;
    }
    
    if (filters.status === 'archived') {
      return conv.is_archived;
    }
    
    return !conv.is_archived;
  });

  const sortedConversations = [...filteredConversations].sort((a, b) => {
    // Pinned conversations first
    if (a.is_pinned && !b.is_pinned) return -1;
    if (!a.is_pinned && b.is_pinned) return 1;
    
    // Then by last message time
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2 }}>
        <TextField
          fullWidth
          size="small"
          placeholder="Search conversations..."
          value={filters.search}
          onChange={(e) => setFilters({ search: e.target.value })}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search />
              </InputAdornment>
            ),
          }}
        />
      </Box>

      <Divider />

      <List sx={{ flexGrow: 1, overflow: 'auto' }}>
        {sortedConversations.map((conversation) => {
          const isOnline = onlineUsers.has(conversation.fan.id);
          const isSelected = conversation.id === selectedConversationId;

          return (
            <ListItem
              key={conversation.id}
              disablePadding
              secondaryAction={
                <IconButton
                  edge="end"
                  size="small"
                  onClick={(e) => handleMenuOpen(e, conversation)}
                >
                  <MoreVert />
                </IconButton>
              }
            >
              <ListItemButton
                selected={isSelected}
                onClick={() => onConversationSelect(conversation)}
              >
                <ListItemAvatar>
                  <Badge
                    overlap="circular"
                    anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                    variant="dot"
                    sx={{
                      '& .MuiBadge-badge': {
                        backgroundColor: isOnline ? '#44b700' : 'transparent',
                        color: isOnline ? '#44b700' : 'transparent',
                      },
                    }}
                  >
                    <Avatar src={conversation.fan.avatar_url}>
                      {conversation.fan.name[0]}
                    </Avatar>
                  </Badge>
                </ListItemAvatar>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="subtitle2">
                        {conversation.fan.name}
                      </Typography>
                      {conversation.is_pinned && (
                        <PushPin sx={{ fontSize: 16, color: 'text.secondary' }} />
                      )}
                      {conversation.unread_count > 0 && (
                        <Chip
                          label={conversation.unread_count}
                          size="small"
                          color="primary"
                          sx={{ height: 20, minWidth: 20 }}
                        />
                      )}
                    </Box>
                  }
                  secondary={
                    <Box>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {conversation.last_message?.content || 'No messages yet'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {conversation.last_message
                          ? formatDistanceToNow(new Date(conversation.last_message.created_at), {
                              addSuffix: true,
                            })
                          : ''}
                      </Typography>
                    </Box>
                  }
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleMenuClose}>
          <PushPin fontSize="small" sx={{ mr: 1 }} />
          {selectedConversation?.is_pinned ? 'Unpin' : 'Pin'}
        </MenuItem>
        <MenuItem onClick={handleMenuClose}>
          <Archive fontSize="small" sx={{ mr: 1 }} />
          Archive
        </MenuItem>
        <MenuItem onClick={handleMenuClose} sx={{ color: 'error.main' }}>
          <Delete fontSize="small" sx={{ mr: 1 }} />
          Delete
        </MenuItem>
      </Menu>
    </Box>
  );
};
