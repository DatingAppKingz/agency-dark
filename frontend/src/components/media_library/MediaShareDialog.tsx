import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  IconButton,
  InputAdornment
} from '@mui/material';
import { ContentCopy } from '@mui/icons-material';

interface MediaShareDialogProps {
  open: boolean;
  onClose: () => void;
  mediaUrl: string;
  mediaName: string;
}

export const MediaShareDialog: React.FC<MediaShareDialogProps> = ({
  open,
  onClose,
  mediaUrl,
  mediaName
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyLink = () => {
    navigator.clipboard.writeText(mediaUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Share {mediaName}</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" gutterBottom>
            Share this link:
          </Typography>
          <TextField
            fullWidth
            value={mediaUrl}
            InputProps={{
              readOnly: true,
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={handleCopyLink} edge="end">
                    <ContentCopy />
                  </IconButton>
                </InputAdornment>
              ),
            }}
            helperText={copied ? "Copied to clipboard!" : "Click the copy button to copy link"}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};