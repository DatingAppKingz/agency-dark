import { useState, useRef, KeyboardEvent, useEffect } from 'react';
import {
  Box,
  TextField,
  IconButton,
  Menu,
  MenuItem,
  Chip,
  LinearProgress,
  InputAdornment,
} from '@mui/material';
import {
  Send,
  AttachFile,
  Image,
  VideoCall,
  Mic,
  Close,
  EmojiEmotions,
} from '@mui/icons-material';
import { useToast } from '@/components/common/Toaster';
import { VoiceRecorder } from './VoiceRecorder';

interface MessageInputProps {
  onSendMessage: (content: string, attachments?: File[]) => void;
  onTyping: (isTyping: boolean) => void;
  disabled?: boolean;
  value?: string;
  onValueChange?: (value: string) => void;
  onSendVoiceMessage?: (audioBlob: Blob, duration: number) => void;
}

export const MessageInput = ({ onSendMessage, onTyping, disabled, value, onValueChange, onSendVoiceMessage }: MessageInputProps) => {
  const { error } = useToast();
  const [message, setMessage] = useState(value || '');
  const [attachments, setAttachments] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    if (value !== undefined && value !== message) {
      setMessage(value);
    }
  }, [value]);

  const handleSend = () => {
    if (message.trim() || attachments.length > 0) {
      onSendMessage(message.trim(), attachments);
      setMessage('');
      setAttachments([]);
      onTyping(false);
      onValueChange?.(''); // Clear external value
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleMessageChange = (value: string) => {
    setMessage(value);
    onValueChange?.(value);
    
    // Handle typing indicator
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    
    if (value.trim()) {
      onTyping(true);
      typingTimeoutRef.current = setTimeout(() => {
        onTyping(false);
      }, 3000);
    } else {
      onTyping(false);
    }
  };

  const handleAttachmentClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleAttachmentClose = () => {
    setAnchorEl(null);
  };

  const handleFileSelect = (accept: string) => {
    handleAttachmentClose();
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = accept;
    input.multiple = true;
    input.onchange = (e) => {
      const files = Array.from((e.target as HTMLInputElement).files || []);
      handleFilesSelected(files);
    };
    input.click();
  };

  const handleFilesSelected = (files: File[]) => {
    const maxSize = 50 * 1024 * 1024; // 50MB
    const validFiles = files.filter((file) => {
      if (file.size > maxSize) {
        error(`${file.name} is too large. Maximum size is 50MB.`);
        return false;
      }
      return true;
    });
    
    setAttachments([...attachments, ...validFiles]);
  };

  const handleRemoveAttachment = (index: number) => {
    setAttachments(attachments.filter((_, i) => i !== index));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    handleFilesSelected(files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  return (
    <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider' }}>
      {isUploading && <LinearProgress sx={{ mb: 1 }} />}
      
      {attachments.length > 0 && (
        <Box sx={{ mb: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {attachments.map((file, index) => (
            <Chip
              key={index}
              label={file.name}
              size="small"
              onDelete={() => handleRemoveAttachment(index)}
              icon={
                file.type.startsWith('image/') ? <Image /> :
                file.type.startsWith('video/') ? <VideoCall /> :
                <AttachFile />
              }
            />
          ))}
        </Box>
      )}
      
      <Box 
        sx={{ display: 'flex', gap: 1, alignItems: 'flex-end', position: 'relative' }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
      >
        <IconButton
          onClick={handleAttachmentClick}
          disabled={disabled}
        >
          <AttachFile />
        </IconButton>
        
        <TextField
          fullWidth
          multiline
          maxRows={4}
          placeholder="Type a message..."
          value={message}
          onChange={(e) => handleMessageChange(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={disabled}
          sx={{ pr: onSendVoiceMessage ? 8 : 0 }}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton size="small" disabled>
                  <EmojiEmotions />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />
        
        {onSendVoiceMessage && !message.trim() && attachments.length === 0 && (
          <VoiceRecorder
            onSendAudio={onSendVoiceMessage}
            disabled={disabled}
          />
        )}
        
        <IconButton
          color="primary"
          onClick={handleSend}
          disabled={disabled || (!message.trim() && attachments.length === 0)}
          sx={{ visibility: (!message.trim() && attachments.length === 0 && onSendVoiceMessage) ? 'hidden' : 'visible' }}
        >
          <Send />
        </IconButton>
      </Box>
      
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleAttachmentClose}
      >
        <MenuItem onClick={() => handleFileSelect('image/*')}>
          <Image sx={{ mr: 1 }} /> Photos
        </MenuItem>
        <MenuItem onClick={() => handleFileSelect('video/*')}>
          <VideoCall sx={{ mr: 1 }} /> Videos
        </MenuItem>
        <MenuItem onClick={() => handleFileSelect('audio/*')}>
          <Mic sx={{ mr: 1 }} /> Audio
        </MenuItem>
        <MenuItem onClick={() => handleFileSelect('*')}>
          <AttachFile sx={{ mr: 1 }} /> Files
        </MenuItem>
      </Menu>
    </Box>
  );
};