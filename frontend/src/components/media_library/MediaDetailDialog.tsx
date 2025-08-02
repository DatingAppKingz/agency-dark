import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogActions,
  Button,
  Typography,
  Box
} from '@mui/material';

interface MediaItem {
  id: string;
  name: string;
  type: string;
  url: string;
  size: number;
  created_at: string;
  tags?: string[];
}

interface MediaDetailDialogProps {
  open: boolean;
  onClose: () => void;
  media: MediaItem | null;
  onEdit?: (media: MediaItem) => void;
  onDelete?: (mediaId: string) => void;
}

export const MediaDetailDialog: React.FC<MediaDetailDialogProps> = ({
  open,
  onClose,
  media,
  onEdit,
  onDelete
}) => {
  if (!media) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{media.name}</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 2 }}>
          {media.type.startsWith('image/') ? (
            <img 
              src={media.url} 
              alt={media.name}
              style={{ maxWidth: '100%', height: 'auto' }}
            />
          ) : media.type.startsWith('video/') ? (
            <video 
              src={media.url} 
              controls
              style={{ maxWidth: '100%', height: 'auto' }}
            />
          ) : (
            <Typography>Preview not available for this file type</Typography>
          )}
        </Box>
        <Typography variant="body2" color="text.secondary">
          Type: {media.type}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Size: {(media.size / 1024 / 1024).toFixed(2)} MB
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Created: {new Date(media.created_at).toLocaleString()}
        </Typography>
        {media.tags && media.tags.length > 0 && (
          <Typography variant="body2" color="text.secondary">
            Tags: {media.tags.join(', ')}
          </Typography>
        )}
      </DialogContent>
      <DialogActions>
        {onDelete && (
          <Button onClick={() => onDelete(media.id)} color="error">
            Delete
          </Button>
        )}
        {onEdit && (
          <Button onClick={() => onEdit(media)}>
            Edit
          </Button>
        )}
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};