import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Autocomplete,
  Chip,
  Box,
  Typography,
} from '@mui/material';
import { User } from '@/types/auth';
import { ChatUser } from '@/types/chat';
import { modelApi } from '@/services/api/models';
import { chatApi } from '@/services/api/chat';
import { useToast } from '@/components/common/Toaster';

interface FanAssignmentProps {
  open: boolean;
  onClose: () => void;
  fan: ChatUser;
  currentAssignee?: User;
  onAssignmentChange: (assignee: User | null) => void;
}

export const FanAssignment = ({ 
  open, 
  onClose, 
  fan, 
  currentAssignee,
  onAssignmentChange 
}: FanAssignmentProps) => {
  const { success, error } = useToast();
  const [selectedModel, setSelectedModel] = useState<User | null>(currentAssignee || null);
  const [models, setModels] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Load available models when dialog opens
  useState(() => {
    if (open) {
      const loadModels = async () => {
        try {
          setIsLoading(true);
          const data = await modelApi.getModels();
          setModels(data);
        } catch (err) {
          error('Failed to load models');
        } finally {
          setIsLoading(false);
        }
      };
      
      loadModels();
    }
  }, [open]);

  const handleAssign = async () => {
    try {
      setIsSaving(true);
      
      // Update fan assignment
      await chatApi.assignFanToModel(fan.id, selectedModel?.id || null);
      
      onAssignmentChange(selectedModel);
      success(selectedModel 
        ? `Fan assigned to ${selectedModel.name}` 
        : 'Fan assignment removed'
      );
      onClose();
    } catch (err) {
      error('Failed to update assignment');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemoveAssignment = async () => {
    setSelectedModel(null);
    await handleAssign();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        Assign Model to {fan.name}
      </DialogTitle>
      
      <DialogContent>
        <Box sx={{ mt: 2 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {currentAssignee 
              ? `Currently assigned to ${currentAssignee.name}`
              : 'No model assigned'
            }
          </Typography>

          <Autocomplete
            value={selectedModel}
            onChange={(_, newValue) => setSelectedModel(newValue)}
            options={models}
            getOptionLabel={(option) => option.name}
            renderOption={(props, option) => (
              <Box component="li" {...props}>
                <Box>
                  <Typography variant="body1">{option.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    {option.email}
                  </Typography>
                </Box>
              </Box>
            )}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Select Model"
                placeholder="Search for a model..."
              />
            )}
            loading={isLoading}
            disabled={isLoading || isSaving}
          />

        </Box>
      </DialogContent>

      <DialogActions>
        {currentAssignee && (
          <Button onClick={handleRemoveAssignment} color="error">
            Remove Assignment
          </Button>
        )}
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose}>Cancel</Button>
        <Button 
          onClick={handleAssign} 
          variant="contained" 
          disabled={isSaving || (selectedModel?.id === currentAssignee?.id)}
        >
          {isSaving ? 'Saving...' : 'Assign'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};