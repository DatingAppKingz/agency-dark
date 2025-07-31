import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  RadioGroup,
  FormControlLabel,
  Radio,
  TextField,
  Typography,
  Box,
  Alert,
  Checkbox,
  FormControl,
  FormLabel } from '@mui/material';
import {
  Block,
  Report,
  Warning } from '@mui/icons-material';
import { useToast } from '@/components/common/Toaster';
import { ChatUser } from '@/types/chat';

interface BlockReportDialogProps {
  open: boolean;
  onClose: () => void;
  user: ChatUser | null;
  onBlock?: (userId: string, reason: string) => Promise<void>;
  onReport?: (userId: string, reason: string, details: string) => Promise<void>;
}

const reportReasons = [
  { value: 'spam', label: 'Spam or unwanted messages' },
  { value: 'harassment', label: 'Harassment or bullying' },
  { value: 'inappropriate', label: 'Inappropriate content' },
  { value: 'scam', label: 'Scam or fraud attempt' },
  { value: 'impersonation', label: 'Impersonation' },
  { value: 'other', label: 'Other' },
];

export const BlockReportDialog = ({
  open,
  onClose,
  user,
  onBlock,
  onReport }: BlockReportDialogProps) => {
  const { error, success } = useToast();
  const [setAction] = useState<'block' | 'report'>('block');
  const [blockUser, setBlockUser] = useState(true);
  const [reportUser, setReportUser] = useState(false);
  const [reportReason, setReportReason] = useState('');
  const [reportDetails, setReportDetails] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!user) return;

    try {
      setIsSubmitting(true);

      if (reportUser) {
        if (!reportReason) {
          error('Please select a reason for reporting');
          return;
        }
        if (reportReason === 'other' && !reportDetails.trim()) {
          error('Please provide details for your report');
          return;
        }

        if (onReport) {
          await onReport(user.id, reportReason, reportDetails);
        }
      }

      if (blockUser && onBlock) {
        await onBlock(user.id, reportReason || 'user_blocked');
      }

      if (blockUser && reportUser) {
        success('User blocked and reported successfully');
      } else if (blockUser) {
        success('User blocked successfully');
      } else if (reportUser) {
        success('Report submitted successfully');
      }

      handleClose();
    } catch (err) {
      error('Failed to complete ');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setAction('block');
    setBlockUser(true);
    setReportUser(false);
    setReportReason('');
    setReportDetails('');
    onClose();
  };

  if (!user) return null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box display="flex" alignItems="center" gap={1}>
          <Warning color="warning" />
          <Typography variant="h6">Block or Report User</Typography>
        </Box>
      </DialogTitle>

      <DialogContent dividers>
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            You are taking against <strong>{user.name}</strong>
          </Typography>
        </Alert>

        <FormControl component="fieldset" sx={{ mb: 3 }}>
          <FormLabel component="legend">What would you like to do?</FormLabel>
          <Box sx={{ mt: 1 }}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={blockUser}
                  onChange={(e) => setBlockUser(e.target.checked)}
                  disabled={!onBlock}
                />
              }
              label={
                <Box display="flex" alignItems="center" gap={1}>
                  <Block />
                  <Box>
                    <Typography variant="subtitle2">Block this user</Typography>
                    <Typography variant="caption" color="text.secondary">
                      They won't be able to message you or see your content
                    </Typography>
                  </Box>
                </Box>
              }
            />

            <FormControlLabel
              control={
                <Checkbox
                  checked={reportUser}
                  onChange={(e) => setReportUser(e.target.checked)}
                  disabled={!onReport}
                />
              }
              label={
                <Box display="flex" alignItems="center" gap={1}>
                  <Report />
                  <Box>
                    <Typography variant="subtitle2">Report this user</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Flag this user for violating community guidelines
                    </Typography>
                  </Box>
                </Box>
              }
              sx={{ mt: 2 }}
            />
          </Box>
        </FormControl>

        {reportUser && (
          <>
            <FormControl component="fieldset" sx={{ mb: 2 }}>
              <FormLabel component="legend">Reason for reporting</FormLabel>
              <RadioGroup
                value={reportReason}
                onChange={(e) => setReportReason(e.target.value)}
                sx={{ mt: 1 }}
              >
                {reportReasons.map((reason) => (
                  <FormControlLabel
                    key={reason.value}
                    value={reason.value}
                    control={<Radio />}
                    label={reason.label}
                  />
                ))}
              </RadioGroup>
            </FormControl>

            {(reportReason === 'other' || reportReason) && (
              <TextField
                fullWidth
                multiline
                rows={3}
                label="Additional details"
                placeholder="Please provide more information about this issue..."
                value={reportDetails}
                onChange={(e) => setReportDetails(e.target.value)}
                required={reportReason === 'other'}
              />
            )}
          </>
        )}

        {blockUser && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            <Typography variant="body2">
              <strong>Note:</strong> Blocking is permanent. You will need to contact support to unblock this user.
            </Typography>
          </Alert>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color="error"
          disabled={
            isSubmitting ||
            (!blockUser && !reportUser) ||
            (reportUser && !reportReason) ||
            (reportUser && reportReason === 'other' && !reportDetails.trim())
          }
        >
          {blockUser && reportUser
            ? 'Block & Report'
            : blockUser
            ? 'Block User'
            : 'Submit Report'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
