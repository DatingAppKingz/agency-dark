import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogActions,
  Button,
  Typography,
  Box
} from '@mui/material';
import { Media } from '../../types/media';

interface MediaDetailDialogProps {
  open: boolean;
  onClose: () => void;
  media: Media | null;
  onEdit?: (media: Media) => void;
  onDelete?: (mediaId: string) => void;
  onUpdate?: () => void;
}

export const MediaDetailDialog: React.FC<MediaDetailDialogProps> = ({
  open,
  onClose,
  media,
  onEdit,
  onDelete,
  onUpdate: _onUpdate
}) => {
  if (!media) return null;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{media.title || media.original_filename}</DialogTitle>
      <DialogContent>
        <Box sx={{ mb: 2 }}>
          {media.mime_type.startsWith('image/') ? (
            <img 
              src={media.cdn_url || media.file_path} 
              alt={media.title || media.original_filename}
              style={{ maxWidth: '100%', height: 'auto' }}
            />
          ) : media.mime_type.startsWith('video/') ? (
            <video 
              src={media.cdn_url || media.file_path} 
              controls
              style={{ maxWidth: '100%', height: 'auto' }}
            />
          ) : (
            <Typography>Preview not available for this file type</Typography>
          )}
        </Box>
        <Typography variant="body2" color="text.secondary">
          Type: {media.mime_type}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Size: {(media.file_size / 1024 / 1024).toFixed(2)} MB
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Created: {new Date(media.created_at || '').toLocaleString()}
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
        <Button onClick={onClose}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};