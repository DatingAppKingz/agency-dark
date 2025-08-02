import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@mui/material';
import { MediaUploader } from '../media/MediaUploader';

interface MediaUploadDialogProps {
  open: boolean;
  onClose: () => void;
  onUploadComplete?: (files: File[]) => void;
  folderId?: string;
}

export const MediaUploadDialog: React.FC<MediaUploadDialogProps> = ({
  open,
  onClose,
  onUploadComplete,
  folderId
}) => {
  const handleUploadComplete = (files: File[]) => {
    onUploadComplete?.(files);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>Upload Media</DialogTitle>
      <DialogContent>
        <MediaUploader 
          onUploadComplete={handleUploadComplete}
          folderId={folderId}
        />
      </DialogContent>
    </Dialog>
  );
};