import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Grid,
  Button,
  TextField,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  LinearProgress,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider } from '@mui/material';
import {
  Download,
  Description,
  PictureAsPdf,
  Email,
  Visibility,
  Schedule,
  Info,
  Upload,
  Close } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { useToast } from '@/components/common/Toaster';


interface TaxDocumentsProps {
  modelId?: string;
  agencyId?: string;
}

interface TaxDocument {
  id: string;
  type: '1099-NEC' | '1099-K' | 'W-9' | 'W-8BEN' | 'Other';
  year: number;
  status: 'pending' | 'generated' | 'signed' | 'submitted';
  created_at: string;
  signed_at?: string;
  file_url?: string;
  file_size?: number;
  deadline?: string;
}

interface TaxSummary {
  total_income: number;
  total_expenses: number;
  taxable_income: number;
  estimated_tax: number;
  quarterly_payments: {
    q1: number;
    q2: number;
    q3: number;
    q4: number;
  };
}

export const TaxDocuments = ({ modelId, agencyId }: TaxDocumentsProps) => {
  const { error, success } = useToast();
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [previewDialog, setPreviewDialog] = useState<{ open: boolean; document?: TaxDocument }>({
    open: false });
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadType, setUploadType] = useState<TaxDocument['type']>('W-9');
  const [isGenerating, setIsGenerating] = useState(false);

  // Mock data - replace with actual API calls
  const { data: documents, isPending: isDocumentsLoading, refetch } = useQuery({
    queryKey: ['tax-documents', selectedYear, modelId, agencyId],
    queryFn: async () => {
      // Mock data
      return [
        {
          id: '1',
          type: '1099-NEC' as const,
          year: selectedYear,
          status: 'generated' as const,
          created_at: new Date().toISOString(),
          file_url: '/documents/1099-nec-2024.pdf',
          file_size: 245000,
          deadline: '2025-01-31' },
        {
          id: '2',
          type: 'W-9' as const,
          year: selectedYear,
          status: 'signed' as const,
          created_at: new Date().toISOString(),
          signed_at: new Date().toISOString(),
          file_url: '/documents/w9-signed.pdf',
          file_size: 189000 },
        {
          id: '3',
          type: '1099-K' as const,
          year: selectedYear,
          status: 'pending' as const,
          created_at: new Date().toISOString(),
          deadline: '2025-01-31' },
      ];
    } });

  const { data: taxSummary, isPending: isSummaryPending } = useQuery({
    queryKey: ['tax-summary', selectedYear, modelId, agencyId],
    queryFn: async () => {
      // Mock data
      return {
        total_income: 125000,
        total_expenses: 25000,
        taxable_income: 100000,
        estimated_tax: 28000,
        quarterly_payments: {
          q1: 7000,
          q2: 7000,
          q3: 7000,
          q4: 7000 } };
    } });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD' }).format(amount);
  };

  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  const getStatusColor = (status: TaxDocument['status']) => {
    switch (status) {
      case 'signed':
      case 'submitted':
        return 'success';
      case 'generated':
        return 'warning';
      case 'pending':
        return 'default';
      default:
        return 'default';
    }
  };

  const getDocumentIcon = (type: TaxDocument['type']) => {
    switch (type) {
      case '1099-NEC':
      case '1099-K':
        return <Description />;
      case 'W-9':
      case 'W-8BEN':
        return <PictureAsPdf />;
      default:
        return <Description />;
    }
  };

  const handleGenerateDocument = async (type: TaxDocument['type']) => {
    try {
      setIsGenerating(true);
      // TODO: Implement generation
      await new Promise(resolve => setTimeout(resolve, 2000));
      success(`${type} generated successfully`);
      refetch();
    } catch (err) {
      error('Failed to generate ');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownloadDocument = async (event: TaxDocument) => {
    try {
      // TODO: Implement download
      success('Document downloaded successfully');
    } catch (err) {
      error('Failed to download ');
    }
  };

  const handleUploadDocument = async () => {
    if (!uploadFile) return;

    try {
      setIsGenerating(true);
      // TODO: Implement upload
      await new Promise(resolve => setTimeout(resolve, 2000));
      success('Document uploaded successfully');
      setUploadDialogOpen(false);
      setUploadFile(null);
      refetch();
    } catch (err) {
      error('Failed to upload ');
    } finally {
      setIsGenerating(false);
    }
  };

  const TaxSummaryCards = () => (
    <Grid container spacing={3} sx={{ mb: 3 }}>
      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Total Income
            </Typography>
            <Typography variant="h5">
              {formatCurrency(taxSummary?.total_income || 0)}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              For tax year {selectedYear}
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Deductible Expenses
            </Typography>
            <Typography variant="h5">
              {formatCurrency(taxSummary?.total_expenses || 0)}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Business expenses
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Taxable Income
            </Typography>
            <Typography variant="h5">
              {formatCurrency(taxSummary?.taxable_income || 0)}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              After deductions
            </Typography>
          </CardContent>
        </Card>
      </Grid>

      <Grid item xs={12} sm={6} md={3}>
        <Card>
          <CardContent>
            <Typography color="textSecondary" gutterBottom>
              Estimated Tax
            </Typography>
            <Typography variant="h5" color="error.main">
              {formatCurrency(taxSummary?.estimated_tax || 0)}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
              Federal tax estimate
            </Typography>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const QuarterlyPayments = () => (
    <Card sx={{ mb: 3 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Quarterly Tax Payments
        </Typography>
        <Typography variant="body2" color="textSecondary" paragraph>
          Estimated quarterly tax payments for {selectedYear}
        </Typography>
        <Grid container spacing={2}>
          {Object.entries(taxSummary?.quarterly_payments || {}).map(([quarter, amount]) => (
            <Grid item xs={6} sm={3} key={quarter}>
              <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="subtitle2" color="textSecondary">
                  {quarter.toUpperCase()}
                </Typography>
                <Typography variant="h6" sx={{ mt: 1 }}>
                  {formatCurrency(amount)}
                </Typography>
                <Chip
                  label={quarter === 'q1' || quarter === 'q2' ? 'Paid' : 'Due'}
                  color={quarter === 'q1' || quarter === 'q2' ? 'success' : 'warning'}
                  size="small"
                  sx={{ mt: 1 }}
                />
              </Paper>
            </Grid>
          ))}
        </Grid>
      </CardContent>
    </Card>
  );

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5">Tax Documents</Typography>
        <Box display="flex" gap={2} alignItems="center">
          <LocalizationProvider dateAdapter={AdapterDateFns}>
            <DatePicker
              views={['year']}
              label="Tax Year"
              value={new Date(selectedYear, 0)}
              onChange={(date) => date && setSelectedYear(date.getFullYear())}
              slotProps={{
                textField: { size: 'small' }
              }}
            />
          </LocalizationProvider>
          <Button
            variant="outlined"
            startIcon={<Upload />}
            onClick={() => setUploadDialogOpen(true)}
          >
            Upload Document
          </Button>
        </Box>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2">
          <strong>Important:</strong> Keep all tax documents for at least 7 years. 
          Consult with a tax professional for accurate tax advice.
        </Typography>
      </Alert>

      <TaxSummaryCards />
      <QuarterlyPayments />

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Tax Forms & Documents
          </Typography>

          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Document Type</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Deadline</TableCell>
                  <TableCell>Size</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {isDocumentsLoading ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <LinearProgress />
                    </TableCell>
                  </TableRow>
                ) : documents?.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} align="center">
                      <Typography variant="body2" color="textSecondary">
                        No tax documents found for {selectedYear}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ) : (
                  documents?.map((doc) => (
                    <TableRow key={doc.id}>
                      <TableCell>
                        <Box display="flex" alignItems="center" gap={1}>
                          {getDocumentIcon(doc.type)}
                          <Typography variant="body2">{doc.type}</Typography>
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={doc.status.toUpperCase()}
                          color={getStatusColor(doc.status)}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {format(new Date(doc.created_at), 'MMM dd, yyyy')}
                      </TableCell>
                      <TableCell>
                        {doc.deadline ? (
                          <Box display="flex" alignItems="center" gap={0.5}>
                            <Schedule fontSize="small" />
                            {format(new Date(doc.deadline), 'MMM dd, yyyy')}
                          </Box>
                        ) : (
                          '-'
                        )}
                      </TableCell>
                      <TableCell>
                        {doc.file_size ? formatFileSize(doc.file_size) : '-'}
                      </TableCell>
                      <TableCell align="right">
                        <Box display="flex" justifyContent="flex-end" gap={1}>
                          {doc.status === 'pending' ? (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => handleGenerateDocument(doc.type)}
                              disabled={isGenerating}
                            >
                              Generate
                            </Button>
                          ) : (
                            <>
                              <IconButton
                                size="small"
                                onClick={() => setPreviewDialog({ open: true, document: doc })}
                              >
                                <Visibility />
                              </IconButton>
                              <IconButton
                                size="small"
                                onClick={() => handleDownloadDocument(doc)}
                              >
                                <Download />
                              </IconButton>
                              <IconButton size="small">
                                <Email />
                              </IconButton>
                            </>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Additional Information */}
      <Card sx={{ mt: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Tax Information & Resources
          </Typography>
          <List>
            <ListItem>
              <ListItemIcon>
                <Info />
              </ListItemIcon>
              <ListItemText
                primary="Form 1099-NEC"
                secondary="Reports nonemployee compensation of $600 or more"
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemIcon>
                <Info />
              </ListItemIcon>
              <ListItemText
                primary="Form 1099-K"
                secondary="Reports payment card and third-party network transactions"
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemIcon>
                <Info />
              </ListItemIcon>
              <ListItemText
                primary="Form W-9"
                secondary="Request for Taxpayer Identification Number and Certification"
              />
            </ListItem>
            <Divider component="li" />
            <ListItem>
              <ListItemIcon>
                <Info />
              </ListItemIcon>
              <ListItemText
                primary="Quarterly Estimated Taxes"
                secondary="Due April 15, June 15, September 15, and January 15"
              />
            </ListItem>
          </List>
        </CardContent>
      </Card>

      {/* Upload Dialog */}
      <Dialog open={uploadDialogOpen} onClose={() => setUploadDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          Upload Tax Document
        </DialogTitle>
        <DialogContent>
          <Box sx={{ mt: 2 }}>
            <TextField
              select
              fullWidth
              label="Document Type"
              value={uploadType}
              onChange={ (e) => setUploadType(e.target.value as TaxDocument['type'])    }
              margin="normal"
            >
              <MenuItem value="W-9">W-9</MenuItem>
              <MenuItem value="W-8BEN">W-8BEN</MenuItem>
              <MenuItem value="1099-NEC">1099-NEC</MenuItem>
              <MenuItem value="1099-K">1099-K</MenuItem>
              <MenuItem value="Other">Other</MenuItem>
            </TextField>

            <Box
              sx={{
                mt: 2,
                p: 3,
                border: '2px dashed',
                borderColor: 'divider',
                borderRadius: 1,
                textAlign: 'center',
                cursor: 'pointer',
                '&:hover': {
                  borderColor: 'primary.main',
                  backgroundColor: 'action.hover' } }}
              onClick={() => {
                const input = document.createElement('input');
                input.type = 'file';
                input.accept = '.pdf,.jpg,.jpeg,.png';
                input.onchange = (e) => { const file = (e.target as HTMLInputElement).files?.[0];
                  if (file) setUploadFile(file);
                    };
                input.click();
              }}
            >
              <Upload sx={{ fontSize: 48, color: 'text.secondary', mb: 1 }} />
              <Typography variant="body1">
                Click to upload or drag and drop
              </Typography>
              <Typography variant="body2" color="textSecondary">
                PDF, JPG, PNG (max 10MB)
              </Typography>
            </Box>

            {uploadFile && (
              <Alert severity="success" sx={{ mt: 2 }} onClose={() => setUploadFile(null)}>
                Selected: {uploadFile.name} ({formatFileSize(uploadFile.size)})
              </Alert>
            )}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUploadDialogOpen(false)}>Cancel</Button>
          <Button
            variant="contained"
            onClick={handleUploadDocument}
            disabled={!uploadFile || isGenerating}
          >
            Upload
          </Button>
        </DialogActions>
      </Dialog>

      {/* Preview Dialog */}
      <Dialog
        open={previewDialog.open}
        onClose={() => setPreviewDialog({ open: false })}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              {previewDialog.document?.type} Preview
            </Typography>
            <IconButton onClick={() => setPreviewDialog({ open: false })}>
              <Close />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Box
            sx={{
              height: 600,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'grey.100' }}
          >
            <Typography variant="body1" color="textSecondary">
              Document preview would be displayed here
            </Typography>
          </Box>
        </DialogContent>
      </Dialog>
    </Box>
  );
};
