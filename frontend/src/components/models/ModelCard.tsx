import {
  Card,
  CardContent,
  CardMedia,
  Typography,
  Box,
  Chip,
  IconButton,
  Menu,
  MenuItem,
  Avatar,
} from '@mui/material';
import {
  MoreVert,
  AttachMoney,
  People,
  TrendingUp,
  Edit,
  Delete,
  Visibility,
  Block,
} from '@mui/icons-material';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ModelProfile } from '@/types/models';

interface ModelCardProps {
  model: ModelProfile;
  onEdit?: (model: ModelProfile) => void;
  onDelete?: (modelId: string) => void;
  onToggleStatus?: (modelId: string, isActive: boolean) => void;
}

export const ModelCard = ({ model, onEdit, onDelete, onToggleStatus }: ModelCardProps) => {
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleEdit = () => {
    handleMenuClose();
    onEdit?.(model);
  };

  const handleDelete = () => {
    handleMenuClose();
    onDelete?.(model.id);
  };

  const handleToggleStatus = () => {
    handleMenuClose();
    onToggleStatus?.(model.id, !model.is_active);
  };

  const handleCardClick = () => {
    navigate(`/dashboard/models/${model.id}`);
  };

  return (
    <Card 
      sx={{ 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column',
        cursor: 'pointer',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-4px)',
          boxShadow: 4,
        },
      }}
      onClick={handleCardClick}
    >
      <Box sx={{ position: 'relative' }}>
        <CardMedia
          component="div"
          sx={{
            height: 200,
            backgroundColor: 'grey.200',
            backgroundImage: model.cover_image_url ? `url(${model.cover_image_url})` : 'none',
            backgroundSize: 'cover',
            backgroundPosition: 'center',
          }}
        />
        <Avatar
          src={model.avatar_url}
          sx={{
            width: 80,
            height: 80,
            position: 'absolute',
            bottom: -40,
            left: 16,
            border: '4px solid',
            borderColor: 'background.paper',
          }}
        >
          {model.stage_name[0]}
        </Avatar>
        <IconButton
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            backgroundColor: 'background.paper',
            '&:hover': {
              backgroundColor: 'background.paper',
            },
          }}
          size="small"
          onClick={handleMenuOpen}
        >
          <MoreVert />
        </IconButton>
        <Chip
          label={model.is_active ? 'Active' : 'Inactive'}
          size="small"
          color={model.is_active ? 'success' : 'default'}
          sx={{
            position: 'absolute',
            top: 8,
            left: 8,
          }}
        />
      </Box>

      <CardContent sx={{ flexGrow: 1, pt: 6 }}>
        <Typography variant="h6" gutterBottom>
          {model.stage_name}
        </Typography>
        {model.user && (
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {model.user.full_name}
          </Typography>
        )}
        
        <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
          <Chip
            icon={<AttachMoney />}
            label={`$${model.subscription_price}/mo`}
            size="small"
            variant="outlined"
          />
          {model.total_fans !== undefined && (
            <Chip
              icon={<People />}
              label={`${model.total_fans} fans`}
              size="small"
              variant="outlined"
            />
          )}
          {model.total_earnings !== undefined && (
            <Chip
              icon={<TrendingUp />}
              label={`$${model.total_earnings.toLocaleString()}`}
              size="small"
              variant="outlined"
              color="success"
            />
          )}
        </Box>

        {model.bio && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{
              mt: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}
          >
            {model.bio}
          </Typography>
        )}
      </CardContent>

      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleMenuClose}
        onClick={(e) => e.stopPropagation()}
      >
        <MenuItem onClick={handleEdit}>
          <Edit fontSize="small" sx={{ mr: 1 }} /> Edit Profile
        </MenuItem>
        <MenuItem onClick={() => navigate(`/dashboard/models/${model.id}`)}>
          <Visibility fontSize="small" sx={{ mr: 1 }} /> View Details
        </MenuItem>
        <MenuItem onClick={handleToggleStatus}>
          <Block fontSize="small" sx={{ mr: 1 }} /> 
          {model.is_active ? 'Deactivate' : 'Activate'}
        </MenuItem>
        <MenuItem onClick={handleDelete} sx={{ color: 'error.main' }}>
          <Delete fontSize="small" sx={{ mr: 1 }} /> Delete
        </MenuItem>
      </Menu>
    </Card>
  );
};