import React, { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Avatar,
  Chip,
  Grid,
  Alert,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  CheckCircle,
  Cancel,
  Person,
  Email,
  Phone,
  LocationOn,
  Language,
  Category,
  Verified,
  Warning,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { ModelProfile } from '@/types/models';
import { useApproveModel } from '@/hooks/useModels';

interface ModelApprovalDialogProps {
  open: boolean;
  onClose: () => void;
  model: ModelProfile;
  onApprove?: () => void;
}

export const ModelApprovalDialog: React.FC<ModelApprovalDialogProps> = ({
  open,
  onClose,
  model,
  onApprove,
}) => {
  const [approved, setApproved] = useState<boolean | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [notes, setNotes] = useState('');

  const approveModel = useApproveModel();

  const handleSubmit = async () => {
    if (approved === null) return;

    await approveModel.mutateAsync({
      model_id: parseInt(model.id),
      approved,
      rejection_reason: !approved ? rejectionReason : undefined,
      notes: notes || undefined,
    });

    onApprove?.();
    handleClose();
  };

  const handleClose = () => {
    setApproved(null);
    setRejectionReason('');
    setNotes('');
    onClose();
  };

  const getCompletionStatus = () => {
    const required = [
      model.stage_name,
      model.platform,
      model.platform_username,
      model.bio,
      model.profile_photo_url,
    ];
    const completed = required.filter(Boolean).length;
    return {
      completed,
      total: required.length,
      percentage: Math.round((completed / required.length) * 100),
    };
  };

  const completionStatus = getCompletionStatus();

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>Review Model Application</DialogTitle>
      <DialogContent>
        {/* Model Overview */}
        <Box sx={{ mb: 3 }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={4}>
              <Box sx={{ textAlign: 'center' }}>
                <Avatar
                  src={model.profile_photo_url}
                  sx={{ width: 120, height: 120, mx: 'auto', mb: 2 }}
                >
                  {model.stage_name?.charAt(0)}
                </Avatar>
                <Typography variant="h6">{model.stage_name}</Typography>
                <Typography variant="body2" color="textSecondary">
                  {model.real_name}
                </Typography>
                <Chip
                  label={model.platform}
                  size="small"
                  sx={{ mt: 1 }}
                  color="primary"
                />
              </Box>
            </Grid>
            <Grid item xs={12} md={8}>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <Person />
                  </ListItemIcon>
                  <ListItemText
                    primary="Platform Username"
                    secondary={model.platform_username}
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Email />
                  </ListItemIcon>
                  <ListItemText primary="Email" secondary={model.email || 'Not provided'} />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Phone />
                  </ListItemIcon>
                  <ListItemText primary="Phone" secondary={model.phone || 'Not provided'} />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <Language />
                  </ListItemIcon>
                  <ListItemText
                    primary="Languages"
                    secondary={model.languages?.join(', ') || 'Not specified'}
                  />
                </ListItem>
              </List>
            </Grid>
          </Grid>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Profile Completion */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Profile Completion
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
            <Box sx={{ flex: 1, mr: 2 }}>
              <Box
                sx={{
                  height: 8,
                  borderRadius: 4,
                  bgcolor: 'grey.200',
                  position: 'relative',
                  overflow: 'hidden',
                }}
              >
                <Box
                  sx={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: `${completionStatus.percentage}%`,
                    bgcolor:
                      completionStatus.percentage === 100
                        ? 'success.main'
                        : 'warning.main',
                    transition: 'width 0.3s',
                  }}
                />
              </Box>
            </Box>
            <Typography variant="body2">
              {completionStatus.completed}/{completionStatus.total}
            </Typography>
          </Box>
        </Box>

        {/* Bio */}
        {model.bio && (
          <>
            <Typography variant="subtitle1" gutterBottom>
              Bio
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              {model.bio}
            </Typography>
          </>
        )}

        {/* Categories & Tags */}
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {model.categories && model.categories.length > 0 && (
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle1" gutterBottom>
                Categories
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {model.categories.map((category) => (
                  <Chip key={category} label={category} size="small" />
                ))}
              </Box>
            </Grid>
          )}
          {model.tags && model.tags.length > 0 && (
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle1" gutterBottom>
                Tags
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {model.tags.map((tag) => (
                  <Chip key={tag} label={tag} size="small" variant="outlined" />
                ))}
              </Box>
            </Grid>
          )}
        </Grid>

        <Divider sx={{ my: 2 }} />

        {/* Verification Status */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Verification Status
          </Typography>
          {model.id_document_url ? (
            <Alert severity="success" icon={<Verified />}>
              ID document uploaded and ready for review
            </Alert>
          ) : (
            <Alert severity="warning" icon={<Warning />}>
              ID document not uploaded - age verification pending
            </Alert>
          )}
        </Box>

        {/* Application Info */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Application Details
          </Typography>
          <Typography variant="body2">
            Applied: {format(new Date(model.created_at), 'PPP')}
          </Typography>
          <Typography variant="body2">
            Agency: {model.agency?.name || 'Not assigned'}
          </Typography>
        </Box>

        {/* Decision Section */}
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Decision
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
            <Button
              variant={approved === true ? 'contained' : 'outlined'}
              color="success"
              startIcon={<CheckCircle />}
              onClick={() => setApproved(true)}
              fullWidth
            >
              Approve
            </Button>
            <Button
              variant={approved === false ? 'contained' : 'outlined'}
              color="error"
              startIcon={<Cancel />}
              onClick={() => setApproved(false)}
              fullWidth
            >
              Reject
            </Button>
          </Box>

          {approved === false && (
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Rejection Reason (required)"
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              error={!rejectionReason}
              helperText={
                !rejectionReason
                  ? 'Please provide a reason for rejection'
                  : 'This will be sent to the applicant'
              }
              sx={{ mb: 2 }}
            />
          )}

          <TextField
            fullWidth
            multiline
            rows={2}
            label="Admin Notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            helperText="Internal notes, not visible to the model"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={
            approved === null ||
            (approved === false && !rejectionReason) ||
            approveModel.isPending
          }
          color={approved ? 'success' : 'error'}
        >
          {approved ? 'Approve Model' : 'Reject Model'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};