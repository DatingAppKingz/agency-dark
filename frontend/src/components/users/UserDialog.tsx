import { useState } from 'react';
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
  InputAdornment,
  FormHelperText,
} from '@mui/material';
import { Close, Visibility, VisibilityOff } from '@mui/icons-material';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { UserRole } from '@/types/auth';
import { CreateUserData, UpdateUserData } from '@/services/api/users';

const createUserSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  full_name: z.string().min(2, 'Name must be at least 2 characters'),
  role: z.nativeEnum(UserRole),
});

const updateUserSchema = z.object({
  full_name: z.string().min(2, 'Name must be at least 2 characters'),
  role: z.nativeEnum(UserRole),
});

interface UserDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: CreateUserData | UpdateUserData) => void;
  user?: any; // User to edit
  loading?: boolean;
}

export const UserDialog = ({ open, onClose, onSubmit, user, loading }: UserDialogProps) => {
  const [showPassword, setShowPassword] = useState(false);
  const isEditing = !!user;

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<CreateUserData | UpdateUserData>({
    resolver: zodResolver(isEditing ? updateUserSchema : createUserSchema) as any,
    defaultValues: user || {
      role: UserRole.AGENCY_MEMBER,
    },
  });

  const handleClose = () => {
    reset();
    onClose();
  };

  const onFormSubmit = (data: CreateUserData | UpdateUserData) => {
    onSubmit(data);
    handleClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {isEditing ? 'Edit User' : 'Create New User'}
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
          <TextField
            {...register('full_name')}
            fullWidth
            label="Full Name"
            error={!!errors.full_name}
            helperText={errors.full_name?.message}
            margin="normal"
          />

          {!isEditing && (
            <>
              <TextField
                {...register('email')}
                fullWidth
                label="Email Address"
                type="email"
                error={!!errors.email}
                helperText={errors.email?.message}
                margin="normal"
              />

              <TextField
                {...register('password')}
                fullWidth
                label="Password"
                type={showPassword ? 'text' : 'password'}
                error={!!(errors as any).password}
                helperText={(errors as any).password?.message}
                margin="normal"
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword(!showPassword)}
                        edge="end"
                      >
                        {showPassword ? <VisibilityOff /> : <Visibility />}
                      </IconButton>
                    </InputAdornment>
                  ),
                }}
              />
            </>
          )}

          <FormControl fullWidth margin="normal" error={!!errors.role}>
            <InputLabel>Role</InputLabel>
            <Select {...register('role')} label="Role" defaultValue={user?.role || UserRole.AGENCY_MEMBER}>
              <MenuItem value={UserRole.AGENCY_OWNER}>Agency Owner</MenuItem>
              <MenuItem value={UserRole.AGENCY_ADMIN}>Agency Admin</MenuItem>
              <MenuItem value={UserRole.MODEL}>Model</MenuItem>
              <MenuItem value={UserRole.CHATTER}>Chatter</MenuItem>
              <MenuItem value={UserRole.AGENCY_MEMBER}>Agency Member</MenuItem>
            </Select>
            {errors.role && (
              <FormHelperText>{errors.role.message}</FormHelperText>
            )}
          </FormControl>
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
