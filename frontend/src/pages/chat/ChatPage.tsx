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
  Menu,
  MenuItem,
  Divider } from '@mui/material';
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
  Download } from '@mui/icons-material';
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
import { usePushNotifications } from '@/providers/PushNotificationProvider';
import { useAuthStore } from '@/store/authStore';

const ChatPage = () => {
  const { error, success } = useToast();
  const socket = useSocket();
  const { user } = useAuthStore();
  const { permission, isSubscribed } = usePushNotifications();
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
    getUnreadCount } = useChatStore();

  const [, setIsLoadingConversations] = useState(true);
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
        const data = await chatApi.getConversations(user?.id || '');
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
    socket.joinConversation(activeConversationId);

    return () => {
      // Leave conversation room
      socket.leaveConversation(activeConversationId);
    };
  }, [activeConversationId]);

  // Socket event handlers
  useEffect(() => {
    // Store callback functions so we can properly remove them later
    const handleNewMessage = (message: Message) => {
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
              : conversation.unread_count + 1 });
      }

      // Send push notification if is from another user and tab is not active
      if (
        message.sender_id !== user?.id &&
        message.conversation_id !== activeConversationId &&
        permission === 'granted' &&
        isSubscribed &&
        document.hidden
      ) {
        const notificationTitle = conversation?.fan.name || 'New Message';
        const notificationBody = message.content.substring(0, 100);
        
        if ('serviceWorker' in navigator && 'PushManager' in window) {
          navigator.serviceWorker.ready.then((registration) => {
            registration.showNotification(notificationTitle, {
              body: notificationBody,
              icon: '/icon-192x192.png',
              badge: '/icon-72x72.png',
              tag: `message-${message.id}`,
              data: {
                url: `/chat?conversation=${message.conversation_id}`,
                conversationId: message.conversation_id } });
          });
        }
      }
    };

    const handleMessageUpdated = (message: Message) => {
      updateMessage(message);
    };

    const handleMessageDeleted = ({ conversation_id, message_id }: { conversation_id: string; message_id: string }) => {
      const { deleteMessage } = useChatStore.getState();
      deleteMessage(conversation_id, message_id);
    };

    const handleUserOnline = (user_id: string) => {
      setUserOnline(user_id, true);
    };

    const handleUserOffline = (user_id: string) => {
      setUserOnline(user_id, false);
    };

    const handleMessageDelivered = ({ message_id, delivered_at }: { message_id: string; delivered_at: string }) => {
      const message = messages.find((m) => m.id === message_id);
      if (message) {
        updateMessage({ ...message, delivered_at });
      }
    };

    const handleMessageRead = ({ message_id, read_at }: { message_id: string; read_at: string }) => {
      const message = messages.find((m) => m.id === message_id);
      if (message) {
        updateMessage({ ...message, read_at });
      }
    };

    // Subscribe to events
    socket.on('message:new', handleNewMessage);
    socket.on('message:updated', handleMessageUpdated);
    socket.on('message:deleted', handleMessageDeleted);
    socket.on('typing:status', setTypingStatus);
    socket.on('user:online', handleUserOnline);
    socket.on('user:offline', handleUserOffline);
    socket.on('message:delivered', handleMessageDelivered);
    socket.on('message:read', handleMessageRead);

    return () => {
      // Unsubscribe from events
      socket.off('message:new', handleNewMessage);
      socket.off('message:updated', handleMessageUpdated);
      socket.off('message:deleted', handleMessageDeleted);
      socket.off('typing:status', setTypingStatus);
      socket.off('user:online', handleUserOnline);
      socket.off('user:offline', handleUserOffline);
      socket.off('message:delivered', handleMessageDelivered);
      socket.off('message:read', handleMessageRead);
    };
  }, [messages, activeConversationId, user, permission, isSubscribed, addMessage, updateMessage, getConversation, updateConversation, setTypingStatus, setUserOnline]);

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
        attachments: attachments ? await uploadAttachments(attachments) : undefined };

      await chatApi.sendMessage(newMessage);
      
      // Message will be added via socket event
      success('Message sent');
      setMessageInputValue(''); // Reset input after sending
    } catch (err) {
      error('Failed to send ');
    } finally {
      setIsSendingMessage(false);
    }
  };

  const handleSendVoiceMessage = async (audioBlob: Blob, duration: number) => {
    if (!activeConversationId || !activeConversation) return;

    try {
      setIsSendingMessage(true);

      // Convert blob to file
      const audioFile = new File([audioBlob], `voice_${Date.now()}.webm`, {
        type: 'audio/webm' });

      const attachments = await uploadAttachments([audioFile]);

      const newMessage: NewMessage = {
        conversation_id: activeConversationId,
        content: `🎤 Voice (${Math.floor(duration / 60)}:${(duration % 60).toString().padStart(2, '0')})`,
        attachments,
        message_type: 'voice' };

      await chatApi.sendMessage(newMessage);
      
      // Message will be added via socket event
      success('Voice sent');
    } catch (err) {
      error('Failed to send voice ');
    } finally {
      setIsSendingMessage(false);
    }
  };

  const handleTyping = (isTyping: boolean) => {
    if (!activeConversationId) return;

    socket.emitTyping(activeConversationId, isTyping);
  };

  const uploadAttachments = async (_files: File[]) => {
    // TODO: Implement file upload
    // This would upload to your storage service and return attachment metadata
    return [];
  };

  const handleToggleFavorite = async () => {
    if (!activeConversation) return;

    try {
      const updated = await chatApi.updateConversation(activeConversation.id, {
        is_favorite: !activeConversation.is_favorite });
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
              flexDirection: 'column' }}
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
                      onClick={(event) => setChatMenuAnchor(event.currentTarget)}
                    >
                      <MoreVert />
                    </IconButton>
                  </Toolbar>
                </AppBar>

                {/* Messages */}
                <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
                  <MessageThread
                    messages={messages}
                    conversationId={activeConversationId || ''}
                    isPending={isLoadingMessages}
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
                    onSendVoiceMessage={handleSendVoiceMessage}
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
                  height: '100%' }}
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
        onMessageSelect={() => {
          // TODO: Implement scroll to in thread
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
          <Block sx={{ mr: 1 }} /> Block or User
        </MenuItem>
      </Menu>

      {/* Block/Dialog */}
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
        conversation={activeConversation || null}
      />
    </Box>
  );
};

export default ChatPage;
