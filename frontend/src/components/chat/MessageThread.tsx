import { useEffect, useRef, useState } from 'react';
import {
  Box,
  Typography,
  Avatar,
  Paper,
  IconButton,
  Chip,
  CircularProgress,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  MoreVert,
  Done,
  DoneAll,
  AttachFile,
  Image,
  VideoFile,
} from '@mui/icons-material';
import { format, isToday, isYesterday } from 'date-fns';
import { Message, MessageAttachment } from '@/types/chat';
import { useAuthStore } from '@/store/authStore';
import { useChatStore } from '@/store/chatStore';

interface MessageThreadProps {
  messages: Message[];
  conversationId: string;
  isLoading?: boolean;
}

export const MessageThread = ({ messages, conversationId, isLoading }: MessageThreadProps) => {
  const { user } = useAuthStore();
  const { typingStatuses } = useChatStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, message: Message) => {
    setAnchorEl(event.currentTarget);
    setSelectedMessage(message);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
    setSelectedMessage(null);
  };

  const formatMessageDate = (date: string) => {
    const messageDate = new Date(date);
    
    if (isToday(messageDate)) {
      return format(messageDate, 'h:mm a');
    } else if (isYesterday(messageDate)) {
      return `Yesterday ${format(messageDate, 'h:mm a')}`;
    } else {
      return format(messageDate, 'MMM d, h:mm a');
    }
  };

  const renderAttachment = (attachment: MessageAttachment) => {
    switch (attachment.type) {
      case 'image':
        return (
          <Box
            component="img"
            src={attachment.thumbnail_url || attachment.url}
            alt={attachment.filename}
            sx={{
              maxWidth: 300,
              maxHeight: 300,
              borderRadius: 1,
              cursor: 'pointer',
            }}
            onClick={() => window.open(attachment.url, '_blank')}
          />
        );
      case 'video':
        return (
          <Box sx={{ position: 'relative', cursor: 'pointer' }}>
            <Box
              component="img"
              src={attachment.thumbnail_url}
              alt={attachment.filename}
              sx={{
                maxWidth: 300,
                maxHeight: 300,
                borderRadius: 1,
              }}
            />
            <VideoFile
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                fontSize: 48,
                color: 'white',
                filter: 'drop-shadow(0 0 4px rgba(0,0,0,0.5))',
              }}
            />
          </Box>
        );
      default:
        return (
          <Chip
            icon={<AttachFile />}
            label={attachment.filename}
            onClick={() => window.open(attachment.url, '_blank')}
            sx={{ cursor: 'pointer' }}
          />
        );
    }
  };

  const groupMessagesByDate = (messages: Message[]) => {
    const groups: Record<string, Message[]> = {};
    
    messages.forEach((message) => {
      const date = format(new Date(message.created_at), 'yyyy-MM-dd');
      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(message);
    });
    
    return groups;
  };

  const messageGroups = groupMessagesByDate(messages);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', overflow: 'auto', p: 2 }}>
      {Object.entries(messageGroups).map(([date, dateMessages]) => (
        <Box key={date}>
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 2 }}>
            <Chip
              label={
                isToday(new Date(date))
                  ? 'Today'
                  : isYesterday(new Date(date))
                  ? 'Yesterday'
                  : format(new Date(date), 'MMMM d, yyyy')
              }
              size="small"
              sx={{ backgroundColor: 'background.default' }}
            />
          </Box>
          
          {dateMessages.map((message) => {
            const isOwnMessage = message.sender_id === user?.id;
            
            return (
              <Box
                key={message.id}
                sx={{
                  display: 'flex',
                  justifyContent: isOwnMessage ? 'flex-end' : 'flex-start',
                  mb: 2,
                }}
              >
                <Box
                  sx={{
                    maxWidth: '70%',
                    display: 'flex',
                    flexDirection: isOwnMessage ? 'row-reverse' : 'row',
                    gap: 1,
                  }}
                >
                  {!isOwnMessage && (
                    <Avatar sx={{ width: 32, height: 32 }}>
                      {message.sender_type === 'fan' ? 'F' : 'M'}
                    </Avatar>
                  )}
                  
                  <Box>
                    <Paper
                      sx={{
                        p: 1.5,
                        backgroundColor: isOwnMessage ? 'primary.main' : 'background.paper',
                        color: isOwnMessage ? 'primary.contrastText' : 'text.primary',
                        borderRadius: 2,
                        position: 'relative',
                      }}
                    >
                      {message.is_automated && (
                        <Chip
                          label="Automated"
                          size="small"
                          sx={{ mb: 1 }}
                        />
                      )}
                      
                      <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                        {message.content}
                      </Typography>
                      
                      {message.attachments && message.attachments.length > 0 && (
                        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                          {message.attachments.map((attachment) => (
                            <Box key={attachment.id}>
                              {renderAttachment(attachment)}
                            </Box>
                          ))}
                        </Box>
                      )}
                      
                      <Box
                        sx={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                          mt: 0.5,
                          justifyContent: isOwnMessage ? 'flex-end' : 'flex-start',
                        }}
                      >
                        <Typography variant="caption" sx={{ opacity: 0.7 }}>
                          {formatMessageDate(message.created_at)}
                        </Typography>
                        
                        {isOwnMessage && (
                          <>
                            {message.read_at ? (
                              <DoneAll sx={{ fontSize: 16, opacity: 0.7 }} />
                            ) : message.delivered_at ? (
                              <Done sx={{ fontSize: 16, opacity: 0.7 }} />
                            ) : null}
                          </>
                        )}
                      </Box>
                      
                      <IconButton
                        size="small"
                        sx={{
                          position: 'absolute',
                          top: 4,
                          right: 4,
                          opacity: 0,
                          '&:hover': { opacity: 1 },
                        }}
                        onClick={(e) => handleMenuOpen(e, message)}
                      >
                        <MoreVert fontSize="small" />
                      </IconButton>
                    </Paper>
                  </Box>
                </Box>
              </Box>
            );
          })}
        </Box>
      ))}
      
      {/* Typing indicators */}
      {Object.entries(typingStatuses).map(([userId, isTyping]) => 
        isTyping && userId !== user?.id ? (
          <Box key={userId} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
            <Avatar sx={{ width: 32, height: 32 }}>U</Avatar>
            <Paper sx={{ p: 1, backgroundColor: 'background.paper' }}>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'text.secondary', animation: 'pulse 1.4s infinite' }} />
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'text.secondary', animation: 'pulse 1.4s infinite 0.2s' }} />
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: 'text.secondary', animation: 'pulse 1.4s infinite 0.4s' }} />
              </Box>
            </Paper>
          </Box>
        ) : null
      )}
      
      <div ref={messagesEndRef} />
      
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
      >
        <MenuItem onClick={handleMenuClose}>Copy</MenuItem>
        <MenuItem onClick={handleMenuClose}>Reply</MenuItem>
        {selectedMessage?.sender_id === user?.id && (
          <MenuItem onClick={handleMenuClose}>Edit</MenuItem>
        )}
        <MenuItem onClick={handleMenuClose} sx={{ color: 'error.main' }}>
          Delete
        </MenuItem>
      </Menu>
      
      <style>
        {`
          @keyframes pulse {
            0%, 60%, 100% {
              transform: scale(1);
              opacity: 1;
            }
            30% {
              transform: scale(1.3);
              opacity: 0.5;
            }
          }
        `}
      </style>
    </Box>
  );
};