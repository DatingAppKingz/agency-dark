import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogActions,
  Button,
  TextField,
  Box
} from '@mui/material';

interface FolderCreateDialogProps {
  open: boolean;
  onClose: () => void;
  onCreateFolder: (folderName: string) => void;
  parentFolderId?: string;
}

export const FolderCreateDialog: React.FC<FolderCreateDialogProps> = ({
  open,
  onClose,
  onCreateFolder
  // parentFolderId - unused for now
}) => {
  const [folderName, setFolderName] = useState('');
  const [error, setError] = useState('');

  const handleCreate = () => {
    if (!folderName.trim()) {
      setError('Folder name is required');
      return;
    }
    
    onCreateFolder(folderName.trim());
    setFolderName('');
    setError('');
    onClose();
  };

  const handleClose = () => {
    setFolderName('');
    setError('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Create New Folder</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <TextField
            fullWidth
            label="Folder Name"
            value={folderName}
            onChange={(e) => {
              setFolderName(e.target.value);
              setError('');
            }}
            error={!!error}
            helperText={error}
            autoFocus
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleCreate();
              }
            }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button onClick={handleCreate} variant="contained">
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
};