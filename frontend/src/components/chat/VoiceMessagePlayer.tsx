import { useState, useRef, useEffect } from 'react';
import {
  Box,
  IconButton,
  LinearProgress,
  Typography,
  Paper,
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Download,
} from '@mui/icons-material';
import { MessageAttachment } from '@/types/chat';

interface VoiceMessagePlayerProps {
  attachment: MessageAttachment;
  compact?: boolean;
}

export const VoiceMessagePlayer = ({ attachment, compact = false }: VoiceMessagePlayerProps) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(attachment.duration || 0);
  const [loading, setLoading] = useState(false);
  
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const initAudio = () => {
    if (!audioRef.current) {
      audioRef.current = new Audio(attachment.url);
      audioRef.current.addEventListener('loadedmetadata', () => {
        setDuration(audioRef.current!.duration);
        setLoading(false);
      });
      audioRef.current.addEventListener('ended', () => {
        setIsPlaying(false);
        setCurrentTime(0);
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
        }
      });
      audioRef.current.addEventListener('error', () => {
        setLoading(false);
        setIsPlaying(false);
      });
    }
  };

  const togglePlayback = async () => {
    initAudio();
    
    if (!audioRef.current) return;

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    } else {
      setLoading(true);
      try {
        await audioRef.current.play();
        setIsPlaying(true);
        setLoading(false);
        
        // Update progress
        progressIntervalRef.current = setInterval(() => {
          if (audioRef.current) {
            setCurrentTime(audioRef.current.currentTime);
          }
        }, 100);
      } catch (error) {
        console.error('Error playing audio:', error);
        setLoading(false);
      }
    }
  };

  const handleDownload = () => {
    const a = document.createElement('a');
    a.href = attachment.url;
    a.download = attachment.filename || 'voice-message.webm';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  if (compact) {
    return (
      <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}>
        <IconButton 
          size="small" 
          onClick={togglePlayback} 
          disabled={loading}
          sx={{ 
            backgroundColor: 'action.hover',
            '&:hover': { backgroundColor: 'action.selected' }
          }}
        >
          {isPlaying ? <Pause fontSize="small" /> : <PlayArrow fontSize="small" />}
        </IconButton>
        <Typography variant="caption" color="text.secondary">
          {formatTime(currentTime)} / {formatTime(duration)}
        </Typography>
      </Box>
    );
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        p: 1.5,
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        maxWidth: 300,
      }}
    >
      <IconButton 
        onClick={togglePlayback} 
        disabled={loading}
        color="primary"
        sx={{ 
          backgroundColor: 'primary.light',
          '&:hover': { backgroundColor: 'primary.main', color: 'white' }
        }}
      >
        {isPlaying ? <Pause /> : <PlayArrow />}
      </IconButton>
      
      <Box sx={{ flexGrow: 1 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
          <Typography variant="caption" color="text.secondary">
            Voice Message
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {formatTime(currentTime)} / {formatTime(duration)}
          </Typography>
        </Box>
        <LinearProgress 
          variant="determinate" 
          value={progress} 
          sx={{ height: 4, borderRadius: 2 }}
        />
      </Box>
      
      <IconButton size="small" onClick={handleDownload}>
        <Download fontSize="small" />
      </IconButton>
    </Paper>
  );
};
