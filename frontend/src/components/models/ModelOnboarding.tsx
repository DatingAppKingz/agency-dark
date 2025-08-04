import React, { useState } from 'react';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  Button,
  Paper,
  Typography,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Avatar,
  IconButton,
  Alert,
  Chip,
  Grid,
  Card,
  CardContent,
  LinearProgress,
} from '@mui/material';
import {
  CloudUpload,
  Check,
  NavigateNext,
  NavigateBefore,
  Person,
  Badge,
  Link,
  Description,
  PhotoCamera,
  Verified,
} from '@mui/icons-material';
import { Platform, CreateModelProfileData } from '@/types/models';
import { useCreateModel, useUploadAvatar, useUploadCover } from '@/hooks/useModels';
import { useNavigate } from 'react-router-dom';

const steps = [
  {
    label: 'Basic Information',
    description: 'Tell us about yourself',
    icon: <Person />,
  },
  {
    label: 'Platform Details',
    description: 'Connect your platform account',
    icon: <Link />,
  },
  {
    label: 'Profile Setup',
    description: 'Create your profile',
    icon: <Description />,
  },
  {
    label: 'Media Upload',
    description: 'Add profile and cover photos',
    icon: <PhotoCamera />,
  },
  {
    label: 'Verification',
    description: 'Upload verification documents',
    icon: <Verified />,
  },
];

export const ModelOnboarding: React.FC = () => {
  const navigate = useNavigate();
  const [activeStep, setActiveStep] = useState(0);
  const [formData, setFormData] = useState<Partial<CreateModelProfileData>>({
    platform: Platform.ONLYFANS,
    languages: ['en'],
    categories: [],
    tags: [],
  });
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [idDocumentFile, setIdDocumentFile] = useState<File | null>(null);

  const createModel = useCreateModel();
  const uploadAvatar = useUploadAvatar();
  const uploadCover = useUploadCover();

  const handleNext = () => {
    setActiveStep((prevActiveStep) => prevActiveStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const handleInputChange = (field: string, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleFileUpload = (
    event: React.ChangeEvent<HTMLInputElement>,
    type: 'avatar' | 'cover' | 'id'
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onloadend = () => {
      const preview = reader.result as string;
      if (type === 'avatar') {
        setAvatarFile(file);
        setAvatarPreview(preview);
      } else if (type === 'cover') {
        setCoverFile(file);
        setCoverPreview(preview);
      } else {
        setIdDocumentFile(file);
      }
    };
    reader.readAsDataURL(file);
  };

  const handleSubmit = async () => {
    try {
      // Create model profile
      const model = await createModel.mutateAsync(formData as CreateModelProfileData);

      // Upload avatar if provided
      if (avatarFile) {
        await uploadAvatar.mutateAsync({ modelId: model.id, file: avatarFile });
      }

      // Upload cover if provided
      if (coverFile) {
        await uploadCover.mutateAsync({ modelId: model.id, file: coverFile });
      }

      // Navigate to success page or model dashboard
      navigate(`/dashboard/models/${model.id}`);
    } catch (error) {
      console.error('Failed to complete onboarding:', error);
    }
  };

  const isStepValid = (step: number): boolean => {
    switch (step) {
      case 0:
        return !!(formData.stage_name && formData.real_name);
      case 1:
        return !!(formData.platform && formData.platform_username);
      case 2:
        return !!(formData.bio && formData.categories?.length);
      case 3:
        return !!(avatarFile || coverFile);
      case 4:
        return !!idDocumentFile;
      default:
        return false;
    }
  };

  const getStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
          <Box sx={{ mt: 2 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Stage Name"
                  required
                  value={formData.stage_name || ''}
                  onChange={(e) => handleInputChange('stage_name', e.target.value)}
                  helperText="Your professional name"
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Real Name"
                  required
                  value={formData.real_name || ''}
                  onChange={(e) => handleInputChange('real_name', e.target.value)}
                  helperText="For verification purposes only"
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Email"
                  type="email"
                  value={formData.email || ''}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Phone"
                  value={formData.phone || ''}
                  onChange={(e) => handleInputChange('phone', e.target.value)}
                />
              </Grid>
            </Grid>
          </Box>
        );

      case 1:
        return (
          <Box sx={{ mt: 2 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <FormControl fullWidth required>
                  <InputLabel>Platform</InputLabel>
                  <Select
                    value={formData.platform}
                    label="Platform"
                    onChange={(e) => handleInputChange('platform', e.target.value)}
                  >
                    <MenuItem value={Platform.ONLYFANS}>OnlyFans</MenuItem>
                    <MenuItem value={Platform.FANSLY}>Fansly</MenuItem>
                    <MenuItem value={Platform.FANVUE}>FanVue</MenuItem>
                    <MenuItem value={Platform.CUSTOM}>Custom</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Platform Username"
                  required
                  value={formData.platform_username || ''}
                  onChange={(e) => handleInputChange('platform_username', e.target.value)}
                  helperText="Your username on the platform"
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Platform URL"
                  value={formData.platform_url || ''}
                  onChange={(e) => handleInputChange('platform_url', e.target.value)}
                  helperText="Direct link to your profile"
                />
              </Grid>
            </Grid>
          </Box>
        );

      case 2:
        return (
          <Box sx={{ mt: 2 }}>
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  label="Bio"
                  required
                  value={formData.bio || ''}
                  onChange={(e) => handleInputChange('bio', e.target.value)}
                  helperText="Tell fans about yourself"
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Categories (comma separated)"
                  value={formData.categories?.join(', ') || ''}
                  onChange={(e) =>
                    handleInputChange(
                      'categories',
                      e.target.value.split(',').map((c) => c.trim()).filter(Boolean)
                    )
                  }
                  helperText="e.g., Fitness, Fashion, Gaming"
                />
                <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {formData.categories?.map((cat) => (
                    <Chip key={cat} label={cat} size="small" />
                  ))}
                </Box>
              </Grid>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Tags (comma separated)"
                  value={formData.tags?.join(', ') || ''}
                  onChange={(e) =>
                    handleInputChange(
                      'tags',
                      e.target.value.split(',').map((t) => t.trim()).filter(Boolean)
                    )
                  }
                  helperText="Keywords to help fans find you"
                />
                <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {formData.tags?.map((tag) => (
                    <Chip key={tag} label={tag} size="small" variant="outlined" />
                  ))}
                </Box>
              </Grid>
            </Grid>
          </Box>
        );

      case 3:
        return (
          <Box sx={{ mt: 2 }}>
            <Grid container spacing={3}>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Profile Photo
                    </Typography>
                    <Box sx={{ textAlign: 'center', my: 2 }}>
                      <Avatar
                        src={avatarPreview || undefined}
                        sx={{ width: 120, height: 120, mx: 'auto', mb: 2 }}
                      >
                        <Person sx={{ fontSize: 60 }} />
                      </Avatar>
                      <input
                        accept="image/*"
                        style={{ display: 'none' }}
                        id="avatar-upload"
                        type="file"
                        onChange={(e) => handleFileUpload(e, 'avatar')}
                      />
                      <label htmlFor="avatar-upload">
                        <Button
                          variant="outlined"
                          component="span"
                          startIcon={<CloudUpload />}
                        >
                          Upload Photo
                        </Button>
                      </label>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={6}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Cover Photo
                    </Typography>
                    <Box sx={{ textAlign: 'center', my: 2 }}>
                      <Box
                        sx={{
                          width: '100%',
                          height: 120,
                          bgcolor: 'grey.200',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: 1,
                          mb: 2,
                          backgroundImage: coverPreview
                            ? `url(${coverPreview})`
                            : undefined,
                          backgroundSize: 'cover',
                          backgroundPosition: 'center',
                        }}
                      >
                        {!coverPreview && <PhotoCamera sx={{ fontSize: 40 }} />}
                      </Box>
                      <input
                        accept="image/*"
                        style={{ display: 'none' }}
                        id="cover-upload"
                        type="file"
                        onChange={(e) => handleFileUpload(e, 'cover')}
                      />
                      <label htmlFor="cover-upload">
                        <Button
                          variant="outlined"
                          component="span"
                          startIcon={<CloudUpload />}
                        >
                          Upload Cover
                        </Button>
                      </label>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Box>
        );

      case 4:
        return (
          <Box sx={{ mt: 2 }}>
            <Alert severity="info" sx={{ mb: 3 }}>
              For age verification, please upload a government-issued ID. This information
              will be kept strictly confidential and used only for verification purposes.
            </Alert>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  ID Document
                </Typography>
                <Box sx={{ textAlign: 'center', my: 2 }}>
                  {idDocumentFile ? (
                    <Alert severity="success" icon={<Check />}>
                      Document uploaded: {idDocumentFile.name}
                    </Alert>
                  ) : (
                    <Box
                      sx={{
                        p: 4,
                        border: '2px dashed',
                        borderColor: 'grey.300',
                        borderRadius: 2,
                      }}
                    >
                      <Badge sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
                      <Typography variant="body2" color="textSecondary">
                        Upload a clear photo of your ID
                      </Typography>
                    </Box>
                  )}
                  <input
                    accept="image/*,application/pdf"
                    style={{ display: 'none' }}
                    id="id-upload"
                    type="file"
                    onChange={(e) => handleFileUpload(e, 'id')}
                  />
                  <label htmlFor="id-upload">
                    <Button
                      variant="contained"
                      component="span"
                      startIcon={<CloudUpload />}
                      sx={{ mt: 2 }}
                    >
                      {idDocumentFile ? 'Change Document' : 'Upload Document'}
                    </Button>
                  </label>
                </Box>
              </CardContent>
            </Card>
          </Box>
        );

      default:
        return null;
    }
  };

  return (
    <Box sx={{ maxWidth: 800, mx: 'auto', p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Model Onboarding
      </Typography>
      <Typography variant="body1" color="textSecondary" sx={{ mb: 4 }}>
        Welcome! Let's get your profile set up so you can start earning.
      </Typography>

      <Stepper activeStep={activeStep} orientation="vertical">
        {steps.map((step, index) => (
          <Step key={step.label}>
            <StepLabel
              optional={
                index === steps.length - 1 ? (
                  <Typography variant="caption">Last step</Typography>
                ) : null
              }
              icon={step.icon}
            >
              {step.label}
            </StepLabel>
            <StepContent>
              <Typography>{step.description}</Typography>
              {getStepContent(index)}
              <Box sx={{ mb: 2, mt: 3 }}>
                <Button
                  variant="contained"
                  onClick={index === steps.length - 1 ? handleSubmit : handleNext}
                  disabled={
                    !isStepValid(index) ||
                    (index === steps.length - 1 &&
                      (createModel.isPending ||
                        uploadAvatar.isPending ||
                        uploadCover.isPending))
                  }
                  endIcon={index === steps.length - 1 ? <Check /> : <NavigateNext />}
                >
                  {index === steps.length - 1 ? 'Complete' : 'Continue'}
                </Button>
                <Button
                  disabled={index === 0}
                  onClick={handleBack}
                  sx={{ mt: 1, ml: 1 }}
                  startIcon={<NavigateBefore />}
                >
                  Back
                </Button>
              </Box>
            </StepContent>
          </Step>
        ))}
      </Stepper>

      {activeStep === steps.length && (
        <Paper sx={{ p: 3, mt: 3 }}>
          <Typography variant="h5" gutterBottom>
            Application Submitted!
          </Typography>
          <Typography variant="body1">
            Your profile has been created and is now under review. We'll notify you once
            it's approved, usually within 24-48 hours.
          </Typography>
          <Button
            variant="contained"
            onClick={() => navigate('/dashboard')}
            sx={{ mt: 2 }}
          >
            Go to Dashboard
          </Button>
        </Paper>
      )}
    </Box>
  );
};