import { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  AppBar,
  Toolbar,
  Avatar,
  IconButton,
  Chip,
  Badge,
  Menu,
  MenuItem,
  Divider,
} from '@mui/material';
import {
  VideoCall,
  Call,
  Info,
  Star,
  StarBorder,
  ArrowBack,
  Search,
  MoreVert,
  Block,
  Report,
  Download,
} from '@mui/icons-material';
import { ConversationList } from '@/components/chat/ConversationList';
import { MessageThread } from '@/components/chat/MessageThread';
import { MessageInput } from '@/components/chat/MessageInput';
import { ChatFilters } from '@/components/chat/ChatFilters';
import { MessageSearch } from '@/components/chat/MessageSearch';
import { CannedResponses } from '@/components/chat/CannedResponses';
import { BlockReportDialog } from '@/components/chat/BlockReportDialog';
import { ExportConversation } from '@/components/chat/ExportConversation';
import { useChatStore } from '@/store/chatStore';
import { useSocket } from '@/providers/SocketProvider';
import { chatApi } from '@/services/api/chat';
import { useToast } from '@/components/common/Toaster';
import { Conversation, Message, NewMessage } from '@/types/chat';

const ChatPage = () => {
  const { error, success } = useToast();
  const socket = useSocket();
  const {
    conversations,
    activeConversationId,
    setConversations,
    setActiveConversation,
    getConversation,
    getMessages,
    setMessages,
    addMessage,
    updateMessage,
    updateConversation,
    setTypingStatus,
    setUserOnline,
    onlineUsers,
    filters,
    setFilters,
    getUnreadCount,
  } = useChatStore();

  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [isSendingMessage, setIsSendingMessage] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [messageInputValue, setMessageInputValue] = useState('');
  const [blockReportOpen, setBlockReportOpen] = useState(false);
  const [chatMenuAnchor, setChatMenuAnchor] = useState<null | HTMLElement>(null);
  const [exportOpen, setExportOpen] = useState(false);

  const activeConversation = activeConversationId ? getConversation(activeConversationId) : null;
  const messages = activeConversationId ? getMessages(activeConversationId) : [];

  // Load conversations
  useEffect(() => {
    const loadConversations = async () => {
      try {
        setIsLoadingConversations(true);
        const data = await chatApi.getConversations();
        setConversations(data);
      } catch (err) {
        error('Failed to load conversations');
      } finally {
        setIsLoadingConversations(false);
      }
    };

    loadConversations();
  }, []);

  // Load messages when conversation changes
  useEffect(() => {
    if (!activeConversationId) return;

    const loadMessages = async () => {
      try {
        setIsLoadingMessages(true);
        const data = await chatApi.getMessages(activeConversationId);
        setMessages(activeConversationId, data);

        // Mark messages as read
        await chatApi.markAsRead(activeConversationId);

        // Update conversation unread count
        const conversation = getConversation(activeConversationId);
        if (conversation && conversation.unread_count > 0) {
          updateConversation({ ...conversation, unread_count: 0 });
        }
      } catch (err) {
        error('Failed to load messages');
      } finally {
        setIsLoadingMessages(false);
      }
    };

    loadMessages();

    // Join conversation room
    socket.emit('join_conversation', { conversation_id: activeConversationId });

    return () => {
      // Leave conversation room
      socket.emit('leave_conversation', { conversation_id: activeConversationId });
    };
  }, [activeConversationId]);

  // Socket event handlers
  useEffect(() => {
    socket.on('new_message', (message: Message) => {
      addMessage(message);

      // Update conversation's last message
      const conversation = getConversation(message.conversation_id);
      if (conversation) {
        updateConversation({
          ...conversation,
          last_message: message,
          updated_at: message.created_at,
          unread_count:
            message.conversation_id === activeConversationId
              ? 0
              : conversation.unread_count + 1,
        });
      }
    });

    socket.on('message_updated', (message: Message) => {
      updateMessage(message);
    });

    socket.on('message_deleted', ({ conversation_id, message_id }: any) => {
      const { deleteMessage } = useChatStore.getState();
      deleteMessage(conversation_id, message_id);
    });

    socket.on('typing_status', setTypingStatus);

    socket.on('user_online', ({ user_id }: any) => {
      setUserOnline(user_id, true);
    });

    socket.on('user_offline', ({ user_id }: any) => {
      setUserOnline(user_id, false);
    });

    socket.on('message_delivered', ({ message_id, delivered_at }: any) => {
      const message = messages.find((m) => m.id === message_id);
      if (message) {
        updateMessage({ ...message, delivered_at });
      }
    });

    socket.on('message_read', ({ message_id, read_at }: any) => {
      const message = messages.find((m) => m.id === message_id);
      if (message) {
        updateMessage({ ...message, read_at });
      }
    });

    return () => {
      socket.off('new_message');
      socket.off('message_updated');
      socket.off('message_deleted');
      socket.off('typing_status');
      socket.off('user_online');
      socket.off('user_offline');
      socket.off('message_delivered');
      socket.off('message_read');
    };
  }, [messages]);

  const handleConversationSelect = (conversation: Conversation) => {
    setActiveConversation(conversation.id);
  };

  const handleSendMessage = async (content: string, attachments?: File[]) => {
    if (!activeConversationId || !activeConversation) return;

    try {
      setIsSendingMessage(true);

      const newMessage: NewMessage = {
        conversation_id: activeConversationId,
        content,
        attachments: attachments ? await uploadAttachments(attachments) : undefined,
      };

      const message = await chatApi.sendMessage(newMessage);
      
      // Message will be added via socket event
      success('Message sent');
      setMessageInputValue(''); // Reset input after sending
    } catch (err) {
      error('Failed to send message');
    } finally {
      setIsSendingMessage(false);
    }
  };

  const handleTyping = (isTyping: boolean) => {
    if (!activeConversationId) return;

    socket.emit('typing', {
      conversation_id: activeConversationId,
      is_typing: isTyping,
    });
  };

  const uploadAttachments = async (files: File[]) => {
    // TODO: Implement file upload
    // This would upload files to your storage service and return attachment metadata
    return [];
  };

  const handleToggleFavorite = async () => {
    if (!activeConversation) return;

    try {
      const updated = await chatApi.updateConversation(activeConversation.id, {
        is_favorite: !activeConversation.is_favorite,
      });
      updateConversation(updated);
    } catch (err) {
      error('Failed to update conversation');
    }
  };

  const handleBlockUser = async (userId: string, reason: string) => {
    try {
      await chatApi.blockUser(userId, reason);
      // Remove conversation from list
      if (activeConversation) {
        setConversations(conversations.filter(c => c.id !== activeConversation.id));
        setActiveConversation(null);
      }
    } catch (err) {
      error('Failed to block user');
      throw err;
    }
  };

  const handleReportUser = async (userId: string, reason: string, details: string) => {
    try {
      await chatApi.reportUser(userId, reason, details);
    } catch (err) {
      error('Failed to report user');
      throw err;
    }
  };

  return (
    <Box sx={{ height: 'calc(100vh - 64px - 48px)', display: 'flex', flexDirection: 'column' }}>
      <Grid container sx={{ flexGrow: 1, height: 0 }}>
        {/* Conversation List */}
        <Grid item xs={12} md={4} lg={3} sx={{ display: { xs: activeConversationId ? 'none' : 'block', md: 'block' } }}>
          <Paper
            elevation={0}
            sx={{
              height: '100%',
              borderRight: 1,
              borderColor: 'divider',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <ChatFilters
              filters={filters}
              onFiltersChange={setFilters}
              unreadCount={getUnreadCount()}
            />
            <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
              <ConversationList
                conversations={conversations}
                onConversationSelect={handleConversationSelect}
                selectedConversationId={activeConversationId || undefined}
              />
            </Box>
          </Paper>
        </Grid>

        {/* Chat Area */}
        <Grid item xs={12} md={8} lg={9} sx={{ display: { xs: activeConversationId ? 'block' : 'none', md: 'block' } }}>
          <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            {activeConversation ? (
              <>
                {/* Chat Header */}
                <AppBar position="static" color="default" elevation={0}>
                  <Toolbar>
                    <IconButton
                      edge="start"
                      onClick={() => setActiveConversation(null)}
                      sx={{ mr: 2, display: { md: 'none' } }}
                    >
                      <ArrowBack />
                    </IconButton>
                    <Avatar src={activeConversation.fan.avatar_url}>
                      {activeConversation.fan.name[0]}
                    </Avatar>
                    <Box sx={{ ml: 2, flexGrow: 1 }}>
                      <Typography variant="h6">
                        {activeConversation.fan.name}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {onlineUsers.has(activeConversation.fan.id)
                          ? 'Online'
                          : 'Offline'}
                      </Typography>
                    </Box>
                    
                    {activeConversation.fan.subscription_tier && (
                      <Chip
                        label={activeConversation.fan.subscription_tier}
                        size="small"
                        color="primary"
                        sx={{ mr: 2 }}
                      />
                    )}
                    
                    <IconButton onClick={handleToggleFavorite}>
                      {activeConversation.is_favorite ? (
                        <Star color="primary" />
                      ) : (
                        <StarBorder />
                      )}
                    </IconButton>
                    <IconButton onClick={() => setSearchOpen(true)}>
                      <Search />
                    </IconButton>
                    <IconButton>
                      <Call />
                    </IconButton>
                    <IconButton>
                      <VideoCall />
                    </IconButton>
                    <IconButton
                      onClick={(e) => setChatMenuAnchor(e.currentTarget)}
                    >
                      <MoreVert />
                    </IconButton>
                  </Toolbar>
                </AppBar>

                {/* Messages */}
                <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
                  <MessageThread
                    messages={messages}
                    conversationId={activeConversationId}
                    isLoading={isLoadingMessages}
                  />
                </Box>

                {/* Message Input */}
                <Box sx={{ position: 'relative' }}>
                  <MessageInput
                    onSendMessage={handleSendMessage}
                    onTyping={handleTyping}
                    disabled={isSendingMessage}
                    value={messageInputValue}
                    onValueChange={setMessageInputValue}
                  />
                  <CannedResponses
                    onSelectResponse={(response) => {
                      setMessageInputValue(response);
                    }}
                  />
                </Box>
              </>
            ) : (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  height: '100%',
                }}
              >
                <Typography variant="h6" color="text.secondary">
                  Select a conversation to start chatting
                </Typography>
              </Box>
            )}
          </Box>
        </Grid>
      </Grid>
      
      {/* Message Search Dialog */}
      <MessageSearch
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        conversationId={activeConversationId || undefined}
        onMessageSelect={(message) => {
          // TODO: Implement scroll to message in thread
          setSearchOpen(false);
        }}
      />

      {/* Chat Menu */}
      <Menu
        anchorEl={chatMenuAnchor}
        open={Boolean(chatMenuAnchor)}
        onClose={() => setChatMenuAnchor(null)}
      >
        <MenuItem onClick={() => {
          setChatMenuAnchor(null);
          // TODO: Implement conversation info
        }}>
          <Info sx={{ mr: 1 }} /> Conversation Info
        </MenuItem>
        <MenuItem onClick={() => {
          setChatMenuAnchor(null);
          setExportOpen(true);
        }}>
          <Download sx={{ mr: 1 }} /> Export Conversation
        </MenuItem>
        <Divider />
        <MenuItem onClick={() => {
          setChatMenuAnchor(null);
          setBlockReportOpen(true);
        }} sx={{ color: 'error.main' }}>
          <Block sx={{ mr: 1 }} /> Block or Report User
        </MenuItem>
      </Menu>

      {/* Block/Report Dialog */}
      <BlockReportDialog
        open={blockReportOpen}
        onClose={() => setBlockReportOpen(false)}
        user={activeConversation?.fan || null}
        onBlock={handleBlockUser}
        onReport={handleReportUser}
      />

      {/* Export Conversation Dialog */}
      <ExportConversation
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        conversation={activeConversation}
      />
    </Box>
  );
};

export default ChatPage;