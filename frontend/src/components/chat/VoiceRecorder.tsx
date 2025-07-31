import { useState, useRef, useEffect } from 'react';
import {
  Box,
  IconButton,
  LinearProgress,
  Typography,
  Paper,
  Fade } from '@mui/material';
import {
  Mic,
  Stop,
  Send,
  Delete,
  PlayArrow,
  Pause } from '@mui/icons-material';


interface VoiceRecorderProps {
  onSendAudio: (audioBlob: Blob, duration: number) => void;
  disabled?: boolean;
}

export const VoiceRecorder = ({ onSendAudio, disabled }: VoiceRecorderProps) => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, [audioUrl]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus'
      });
      
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };
      
      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(audioBlob);
        setAudioUrl(URL.createObjectURL(audioBlob));
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      };
      
      mediaRecorder.start(100); // Collect data every 100ms
      setIsRecording(true);
      setRecordingTime(0);
      
      // Start timer
      intervalRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('Error starting recording:', error);
      // Handle permission denied or other errors
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    }
  };

  const deleteRecording = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    setAudioBlob(null);
    setAudioUrl(null);
    setRecordingTime(0);
    setIsPlaying(false);
  };

  const sendRecording = () => {
    if (audioBlob) {
      onSendAudio(audioBlob, recordingTime);
      deleteRecording();
    }
  };

  const togglePlayback = () => {
    if (!audioRef.current && audioUrl) {
      audioRef.current = new Audio(audioUrl);
      audioRef.current.onended = () => {
        setIsPlaying(false);
      };
    }

    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else {
        audioRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Recording UI
  if (isRecording) {
    return (
      <Fade in={true}>
        <Paper
          elevation={2}
          sx={{
            p: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 2,
            backgroundColor: 'error.main',
            color: 'white' }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: 'white',
                animation: 'pulse 1.5s infinite',
                '@keyframes pulse': {
                  '0%': { opacity: 1 },
                  '50%': { opacity: 0.3 },
                  '100%': { opacity: 1 } } }}
            />
            <Typography variant="body2">Recording</Typography>
          </Box>
          
          <Typography variant="body2" sx={{ minWidth: 45 }}>
            {formatTime(recordingTime)}
          </Typography>
          
          <Box sx={{ flexGrow: 1 }}>
            <LinearProgress
              variant="indeterminate"
              sx={{
                backgroundColor: 'rgba(255,255,255,0.3)',
                '& .MuiLinearProgress-bar': {
                  backgroundColor: 'white' } }}
            />
          </Box>
          
          <IconButton onClick={stopRecording} sx={{ color: 'white' }}>
            <Stop />
          </IconButton>
        </Paper>
      </Fade>
    );
  }

  // Recorded audio preview UI
  if (audioBlob && audioUrl) {
    return (
      <Fade in={true}>
        <Paper
          elevation={1}
          sx={{
            p: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 2 }}
        >
          <IconButton onClick={togglePlayback} color="primary">
            {isPlaying ? <Pause /> : <PlayArrow />}
          </IconButton>
          
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Voice message ({formatTime(recordingTime)})
            </Typography>
          </Box>
          
          <IconButton onClick={deleteRecording} color="error">
            <Delete />
          </IconButton>
          
          <IconButton onClick={sendRecording} color="primary" disabled={disabled}>
            <Send />
          </IconButton>
        </Paper>
      </Fade>
    );
  }

  // Default UI - Record button
  return (
    <IconButton 
      onClick={startRecording} 
      color="primary"
      disabled={disabled}
      sx={{ 
        position: 'absolute',
        right: 48,
        top: '50%',
        transform: 'translateY(-50%)' }}
    >
      <Mic />
    </IconButton>
  );
};
