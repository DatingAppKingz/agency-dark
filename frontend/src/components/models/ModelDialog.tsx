import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  IconButton,
  Box,
  Avatar,
  InputAdornment,
  FormControlLabel,
  Switch } from '@mui/material';
import { Close, PhotoCamera, AttachMoney } from '@mui/icons-material';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { ModelProfile, CreateModelProfileData, UpdateModelProfileData } from '@/types/models';
import { useUsers } from '@/hooks/useUsers';
import { UserRole } from '@/types/auth';

const createModelSchema = z.object({
  user_id: z.string().min(1, 'User is required'),
  stage_name: z.string().min(2, 'Stage name must be at least 2 characters'),
  bio: z.string().optional(),
  subscription_price: z.number().min(0, 'Price must be positive'),
  is_active: z.boolean() });

const updateModelSchema = z.object({
  stage_name: z.string().min(2, 'Stage name must be at least 2 characters'),
  bio: z.string().optional(),
  subscription_price: z.number().min(0, 'Price must be positive'),
  is_active: z.boolean() });

interface ModelDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateModelProfileData | UpdateModelProfileData) => void;
  model?: ModelProfile;
  loading?: boolean;
}

export const ModelDialog = ({ open, onClose, onSubmit, model, loading }: ModelDialogProps) => {
  const isEditing = !!model;
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  
  // Fetch users with MODEL role for selection
  const { data: usersData } = useUsers({
    size: 100, // Get all model users
    // TODO: Add role filter when backend supports it
  } as any);
  
  const availableUsers = usersData?.data?.filter((user: any) => 
    // Only show users that don't have a model profile yet (when creating)
    !isEditing || user.id === model.user_id
  ) || [];

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    watch } = useForm<CreateModelProfileData | UpdateModelProfileData>({
    resolver: zodResolver(isEditing ? updateModelSchema : createModelSchema),
    defaultValues: model ? {
      stage_name: model.stage_name,
      bio: model.bio || '',
      subscription_price: model.subscription_price,
      is_active: model.is_active } : {
      user_id: '',
      stage_name: '',
      bio: '',
      subscription_price: 9.99,
      is_active: true } });

  const subscriptionPrice = watch('subscription_price');

  useEffect(() => {
    if (model) {
      setAvatarPreview(model.avatar_url || null);
    }
  }, [model]);

  const handleClose = () => {
    reset();
    setAvatarPreview(null);
    onClose();
  };

  const onFormSubmit = (data: CreateModelProfileData | UpdateModelProfileData) => {
    // Ensure price is a number
    const formData = {
      ...data,
      subscription_price: Number(data.subscription_price) };
    onSubmit(formData);
    handleClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {isEditing ? 'Edit Model Profile' : 'Create Model Profile'}
        <IconButton
          aria-label="close"
          onClick={handleClose}
          sx={{ position: 'absolute', right: 8, top: 8 }}
        >
          <Close />
        </IconButton>
      </DialogTitle>
      <form onSubmit={handleSubmit(onFormSubmit)}>
        <DialogContent>
          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
            <Box sx={{ position: 'relative' }}>
              <Avatar
                src={avatarPreview || model?.avatar_url}
                sx={{ width: 120, height: 120 }}
              >
                {model?.stage_name?.[0] || 'M'}
              </Avatar>
              <IconButton
                color="primary"
                sx={{
                  position: 'absolute',
                  bottom: 0,
                  right: 0,
                  backgroundColor: 'background.paper' }}
                component="label"
              >
                <PhotoCamera />
                <input
                  type="file"
                  hidden
                  accept="image/*"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setAvatarPreview(URL.createObjectURL(file));
                      // In real implementation, you'd handle file upload here
                    }
                  }}
                />
              </IconButton>
            </Box>
          </Box>

          {!isEditing && (
            <FormControl fullWidth margin="normal" error={!!(errors as any).user_id}>
              <InputLabel>Select User</InputLabel>
              <Select
                {...register('user_id')}
                label="Select User"
                defaultValue=""
              >
                <MenuItem value="">
                  <em>Select a user...</em>
                </MenuItem>
                {availableUsers.map((user) => (
                  <MenuItem key={user.id} value={user.id}>
                    {user.full_name} ({user.email})
                  </MenuItem>
                ))}
              </Select>
              {(errors as any).user_id && (
                <Box sx={{ color: 'error.main', fontSize: '0.75rem', mt: 0.5 }}>
                  {(errors as any).user_id.message}
                </Box>
              )}
            </FormControl>
          )}

          <TextField
            {...register('stage_name')}
            fullWidth
            label="Stage Name"
            error={!!errors.stage_name}
            helperText={errors.stage_name?.message}
            margin="normal"
          />

          <TextField
            {...register('bio')}
            fullWidth
            label="Bio"
            multiline
            rows={4}
            error={!!errors.bio}
            helperText={errors.bio?.message}
            margin="normal"
            placeholder="Tell fans about yourself..."
          />

          <TextField
            {...register('subscription_price', { valueAsNumber: true })}
            fullWidth
            label="Subscription Price"
            type="number"
            error={!!errors.subscription_price}
            helperText={errors.subscription_price?.message}
            margin="normal"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <AttachMoney />
                </InputAdornment>
              ),
              inputProps: { min: 0, step: 0.01 } }}
          />

          <Box sx={{ mt: 2 }}>
            <FormControlLabel
              control={
                <Switch
                  {...register('is_active')}
                  defaultChecked={!isEditing || model?.is_active}
                />
              }
              label="Active Profile"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={loading}>
            {loading ? 'Saving...' : isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};
