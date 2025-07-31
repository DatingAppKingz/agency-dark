import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  IconButton,
  Box,
  Typography,
  CircularProgress,
  Fade,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Close,
  ZoomIn,
  ZoomOut,
  Download,
  RotateRight,
  PlayArrow,
  Pause,
  VolumeUp,
  VolumeOff,
} from '@mui/icons-material';
import { MessageAttachment } from '@/types/chat';

interface MediaPreviewProps {
  attachment: MessageAttachment;
  open: boolean;
  onClose: () => void;
}

export const MediaPreview = ({ attachment, open, onClose }: MediaPreviewProps) => {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down('md'));
  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState(0);
  const [isPending, setIsLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [videoRef, setVideoRef] = useState<HTMLVideoElement | null>(null);

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.25, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.25, 0.5));
  };

  const handleRotate = () => {
    setRotation(prev => (prev + 90) % 360);
  };

  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = attachment.url;
    link.download = attachment.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handlePlayPause = () => {
    if (videoRef) {
      if (isPlaying) {
        videoRef.pause();
      } else {
        videoRef.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleMuteToggle = () => {
    if (videoRef) {
      videoRef.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const renderMedia = () => {
    if (attachment.type === 'image') {
      return (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
            overflow: 'hidden',
            cursor: zoom > 1 ? 'move' : 'default',
          }}
        >
          <img
            src={attachment.url}
            alt={attachment.filename}
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              transform: `scale(${zoom}) rotate(${rotation}deg)`,
              transition: 'transform 0.3s ease',
              display: isPending ? 'none' : 'block',
            }}
            onLoad={() => setIsLoading(false)}
            draggable={false}
          />
          {isPending && <CircularProgress />}
        </Box>
      );
    }

    if (attachment.type === 'video') {
      return (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100%',
            position: 'relative',
          }}
        >
          <video
            ref={setVideoRef}
            src={attachment.url}
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              display: isPending ? 'none' : 'block',
            }}
            onLoadedData={() => setIsLoading(false)}
            onEnded={() => setIsPlaying(false)}
            controls={false}
          />
          {isPending && <CircularProgress />}
          
          {/* Video Controls Overlay */}
          <Box
            sx={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 100%)',
              p: 2,
              display: 'flex',
              alignItems: 'center',
              gap: 1,
            }}
          >
            <IconButton onClick={handlePlayPause} sx={{ color: 'white' }}>
              {isPlaying ? <Pause /> : <PlayArrow />}
            </IconButton>
            <IconButton onClick={handleMuteToggle} sx={{ color: 'white' }}>
              {isMuted ? <VolumeOff /> : <VolumeUp />}
            </IconButton>
            <Box sx={{ flex: 1 }} />
            <IconButton onClick={handleDownload} sx={{ color: 'white' }}>
              <Download />
            </IconButton>
          </Box>
        </Box>
      );
    }

    return null;
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={false}
      fullScreen={fullScreen}
      PaperProps={{
        sx: {
          backgroundColor: 'rgba(0, 0, 0, 0.9)',
          maxWidth: '90vw',
          maxHeight: '90vh',
          width: 'auto',
          height: 'auto',
        },
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          p: 2,
          background: 'linear-gradient(to bottom, rgba(0,0,0,0.7) 0%, transparent 100%)',
          zIndex: 1,
        }}
      >
        <Typography variant="h6" sx={{ color: 'white' }}>
          {attachment.filename}
        </Typography>
        <Box display="flex" gap={1}>
          {attachment.type === 'image' && (
            <>
              <IconButton onClick={handleZoomIn} sx={{ color: 'white' }}>
                <ZoomIn />
              </IconButton>
              <IconButton onClick={handleZoomOut} sx={{ color: 'white' }}>
                <ZoomOut />
              </IconButton>
              <IconButton onClick={handleRotate} sx={{ color: 'white' }}>
                <RotateRight />
              </IconButton>
            </>
          )}
          <IconButton onClick={handleDownload} sx={{ color: 'white' }}>
            <Download />
          </IconButton>
          <IconButton onClick={onClose} sx={{ color: 'white' }}>
            <Close />
          </IconButton>
        </Box>
      </Box>

      <DialogContent
        sx={{
          p: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: fullScreen ? '100vh' : '60vh',
          minWidth: fullScreen ? '100vw' : '60vw',
        }}
      >
        <Fade in={open}>
          <Box sx={{ width: '100%', height: '100%' }}>
            {renderMedia()}
          </Box>
        </Fade>
      </DialogContent>
    </Dialog>
  );
};
