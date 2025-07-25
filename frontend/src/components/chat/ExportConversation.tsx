import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Checkbox,
  Typography,
  Box,
  LinearProgress,
  Alert,
  TextField,
  Chip,
} from '@mui/material';
import {
  Download,
  Description,
  PictureAsPdf,
  TableChart,
  Image as ImageIcon,
} from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { format } from 'date-fns';
import { useToast } from '@/components/common/Toaster';
import { Conversation, Message } from '@/types/chat';
import { chatApi } from '@/services/api/chat';
import jsPDF from 'jspdf';

interface ExportConversationProps {
  open: boolean;
  onClose: () => void;
  conversation: Conversation | null;
}

interface ExportOptions {
  format: 'pdf' | 'txt' | 'csv' | 'json';
  includeMedia: boolean;
  includeMetadata: boolean;
  dateRange: 'all' | 'custom';
  startDate: Date | null;
  endDate: Date | null;
}

export const ExportConversation = ({ open, onClose, conversation }: ExportConversationProps) => {
  const { error, success } = useToast();
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [options, setOptions] = useState<ExportOptions>({
    format: 'pdf',
    includeMedia: false,
    includeMetadata: true,
    dateRange: 'all',
    startDate: null,
    endDate: null,
  });

  const handleExport = async () => {
    if (!conversation) return;

    try {
      setIsExporting(true);
      setExportProgress(10);

      // Fetch all messages
      const messages = await chatApi.getMessages(conversation.id, {
        size: 1000, // Get all messages
      });
      setExportProgress(40);

      // Filter by date if needed
      let filteredMessages = messages;
      if (options.dateRange === 'custom' && options.startDate && options.endDate) {
        filteredMessages = messages.filter(msg => {
          const msgDate = new Date(msg.created_at);
          return msgDate >= options.startDate! && msgDate <= options.endDate!;
        });
      }
      setExportProgress(60);

      // Export based on format
      switch (options.format) {
        case 'pdf':
          await exportToPDF(filteredMessages);
          break;
        case 'txt':
          await exportToTXT(filteredMessages);
          break;
        case 'csv':
          await exportToCSV(filteredMessages);
          break;
        case 'json':
          await exportToJSON(filteredMessages);
          break;
      }

      setExportProgress(100);
      success(`Conversation exported successfully as ${options.format.toUpperCase()}`);
      handleClose();
    } catch (err) {
      error('Failed to export conversation');
    } finally {
      setIsExporting(false);
    }
  };

  const exportToPDF = async (messages: Message[]) => {
    const pdf = new jsPDF();
    const pageHeight = pdf.internal.pageSize.height;
    let y = 20;

    // Header
    pdf.setFontSize(18);
    pdf.text('Chat Conversation Export', 20, y);
    y += 10;

    pdf.setFontSize(12);
    pdf.text(`Conversation with: ${conversation?.fan.name}`, 20, y);
    y += 10;
    pdf.text(`Exported on: ${format(new Date(), 'PPP')}`, 20, y);
    y += 15;

    // Messages
    pdf.setFontSize(10);
    messages.forEach((message) => {
      if (y > pageHeight - 30) {
        pdf.addPage();
        y = 20;
      }

      const sender = message.sender_type === 'fan' ? conversation?.fan.name : 'Model';
      const timestamp = format(new Date(message.created_at), 'PPp');
      
      // Sender and timestamp
      pdf.setFont(undefined, 'bold');
      pdf.text(`${sender} - ${timestamp}`, 20, y);
      y += 5;

      // Message content
      pdf.setFont(undefined, 'normal');
      const lines = pdf.splitTextToSize(message.content, 170);
      lines.forEach((line: string) => {
        if (y > pageHeight - 20) {
          pdf.addPage();
          y = 20;
        }
        pdf.text(line, 20, y);
        y += 5;
      });

      // Attachments
      if (message.attachments && message.attachments.length > 0) {
        pdf.setFont(undefined, 'italic');
        pdf.text(`[${message.attachments.length} attachment(s)]`, 20, y);
        y += 5;
      }

      y += 5; // Space between messages
    });

    pdf.save(`conversation_${conversation?.id}_${format(new Date(), 'yyyyMMdd')}.pdf`);
  };

  const exportToTXT = async (messages: Message[]) => {
    let content = `Chat Conversation Export\n`;
    content += `========================\n\n`;
    content += `Conversation with: ${conversation?.fan.name}\n`;
    content += `Exported on: ${format(new Date(), 'PPP')}\n\n`;
    content += `Messages:\n`;
    content += `---------\n\n`;

    messages.forEach((message) => {
      const sender = message.sender_type === 'fan' ? conversation?.fan.name : 'Model';
      const timestamp = format(new Date(message.created_at), 'PPp');
      
      content += `[${timestamp}] ${sender}:\n`;
      content += `${message.content}\n`;
      
      if (message.attachments && message.attachments.length > 0) {
        content += `[${message.attachments.length} attachment(s)]\n`;
      }
      
      content += '\n';
    });

    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conversation_${conversation?.id}_${format(new Date(), 'yyyyMMdd')}.txt`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  const exportToCSV = async (messages: Message[]) => {
    let csv = 'Timestamp,Sender,Message,Attachments,Status\n';

    messages.forEach((message) => {
      const sender = message.sender_type === 'fan' ? conversation?.fan.name : 'Model';
      const timestamp = format(new Date(message.created_at), 'yyyy-MM-dd HH:mm:ss');
      const content = `"${message.content.replace(/"/g, '""')}"`;
      const attachments = message.attachments?.length || 0;
      const status = message.read_at ? 'Read' : 'Unread';

      csv += `${timestamp},${sender},${content},${attachments},${status}\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conversation_${conversation?.id}_${format(new Date(), 'yyyyMMdd')}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  const exportToJSON = async (messages: Message[]) => {
    const data = {
      conversation: {
        id: conversation?.id,
        fan: conversation?.fan,
        model: conversation?.model,
        created_at: conversation?.created_at,
        exported_at: new Date().toISOString(),
      },
      messages: options.includeMetadata ? messages : messages.map(msg => ({
        content: msg.content,
        sender_type: msg.sender_type,
        created_at: msg.created_at,
        attachments: msg.attachments?.map(att => ({
          type: att.type,
          filename: att.filename,
        })),
      })),
      total_messages: messages.length,
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `conversation_${conversation?.id}_${format(new Date(), 'yyyyMMdd')}.json`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  };

  const handleClose = () => {
    setOptions({
      format: 'pdf',
      includeMedia: false,
      includeMetadata: true,
      dateRange: 'all',
      startDate: null,
      endDate: null,
    });
    setExportProgress(0);
    onClose();
  };

  const getFormatIcon = (format: ExportOptions['format']) => {
    switch (format) {
      case 'pdf':
        return <PictureAsPdf />;
      case 'txt':
        return <Description />;
      case 'csv':
        return <TableChart />;
      case 'json':
        return <Description />;
    }
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>Export Conversation</DialogTitle>
      
      <DialogContent dividers>
        {conversation && (
          <Alert severity="info" sx={{ mb: 3 }}>
            Exporting conversation with <strong>{conversation.fan.name}</strong>
          </Alert>
        )}

        <FormControl component="fieldset" sx={{ mb: 3, width: '100%' }}>
          <FormLabel component="legend">Export Format</FormLabel>
          <RadioGroup
            value={options.format}
            onChange={(e) => setOptions({ ...options, format: e.target.value as ExportOptions['format'] })}
            sx={{ mt: 1 }}
          >
            <FormControlLabel
              value="pdf"
              control={<Radio />}
              label={
                <Box display="flex" alignItems="center" gap={1}>
                  <PictureAsPdf />
                  <Box>
                    <Typography variant="body2">PDF Document</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Best for printing and sharing
                    </Typography>
                  </Box>
                </Box>
              }
            />
            <FormControlLabel
              value="txt"
              control={<Radio />}
              label={
                <Box display="flex" alignItems="center" gap={1}>
                  <Description />
                  <Box>
                    <Typography variant="body2">Plain Text</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Simple format, universal compatibility
                    </Typography>
                  </Box>
                </Box>
              }
            />
            <FormControlLabel
              value="csv"
              control={<Radio />}
              label={
                <Box display="flex" alignItems="center" gap={1}>
                  <TableChart />
                  <Box>
                    <Typography variant="body2">CSV Spreadsheet</Typography>
                    <Typography variant="caption" color="text.secondary">
                      For data analysis in Excel/Sheets
                    </Typography>
                  </Box>
                </Box>
              }
            />
            <FormControlLabel
              value="json"
              control={<Radio />}
              label={
                <Box display="flex" alignItems="center" gap={1}>
                  <Description />
                  <Box>
                    <Typography variant="body2">JSON Data</Typography>
                    <Typography variant="caption" color="text.secondary">
                      For developers and data processing
                    </Typography>
                  </Box>
                </Box>
              }
            />
          </RadioGroup>
        </FormControl>

        <FormControl component="fieldset" sx={{ mb: 3, width: '100%' }}>
          <FormLabel component="legend">Date Range</FormLabel>
          <RadioGroup
            value={options.dateRange}
            onChange={(e) => setOptions({ ...options, dateRange: e.target.value as 'all' | 'custom' })}
            sx={{ mt: 1 }}
          >
            <FormControlLabel value="all" control={<Radio />} label="All messages" />
            <FormControlLabel value="custom" control={<Radio />} label="Custom date range" />
          </RadioGroup>
          
          {options.dateRange === 'custom' && (
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Box display="flex" gap={2} mt={2}>
                <DatePicker
                  label="Start Date"
                  value={options.startDate}
                  onChange={(date) => setOptions({ ...options, startDate: date })}
                  slotProps={{
                    textField: { size: 'small', fullWidth: true }
                  }}
                />
                <DatePicker
                  label="End Date"
                  value={options.endDate}
                  onChange={(date) => setOptions({ ...options, endDate: date })}
                  slotProps={{
                    textField: { size: 'small', fullWidth: true }
                  }}
                />
              </Box>
            </LocalizationProvider>
          )}
        </FormControl>

        <FormControl component="fieldset" sx={{ width: '100%' }}>
          <FormLabel component="legend">Options</FormLabel>
          <Box sx={{ mt: 1 }}>
            {options.format === 'json' && (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={options.includeMetadata}
                    onChange={(e) => setOptions({ ...options, includeMetadata: e.target.checked })}
                  />
                }
                label="Include metadata (IDs, timestamps, etc.)"
              />
            )}
            <FormControlLabel
              control={
                <Checkbox
                  checked={options.includeMedia}
                  onChange={(e) => setOptions({ ...options, includeMedia: e.target.checked })}
                  disabled
                />
              }
              label={
                <Box>
                  <Typography variant="body2">Include media files</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Coming soon
                  </Typography>
                </Box>
              }
            />
          </Box>
        </FormControl>

        {isExporting && (
          <Box sx={{ mt: 3 }}>
            <Typography variant="body2" gutterBottom>
              Exporting conversation...
            </Typography>
            <LinearProgress variant="determinate" value={exportProgress} />
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        <Button onClick={handleClose} disabled={isExporting}>
          Cancel
        </Button>
        <Button
          onClick={handleExport}
          variant="contained"
          startIcon={<Download />}
          disabled={isExporting || !conversation}
        >
          Export
        </Button>
      </DialogActions>
    </Dialog>
  );
};