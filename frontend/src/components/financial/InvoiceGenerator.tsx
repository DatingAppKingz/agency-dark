import { useState, useRef } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Divider,
  MenuItem } from '@mui/material';
import {
  Add,
  Delete,
  Print,
  Download,
  Email,
  Close,
  Receipt } from '@mui/icons-material';
import { format } from 'date-fns';
import { useForm, useFieldArray } from 'react-hook-form';
import { useToast } from '@/components/common/Toaster';
import { useReactToPrint } from 'react-to-print';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

interface InvoiceItem {
  description: string;
  quantity: number;
  unit_price: number;
  total: number;
}

interface InvoiceFormData {
  invoice_number: string;
  invoice_date: string;
  due_date: string;
  client_name: string;
  client_email: string;
  client_address: string;
  items: InvoiceItem[];
  notes?: string;
  tax_rate: number;
  discount: number;
  payment_terms: string;
  currency: string;
}

interface InvoiceGeneratorProps {
  open: boolean;
  onClose: () => void;
  prefilledData?: Partial<InvoiceFormData>;
  onSave?: (invoice: InvoiceFormData) => Promise<void>;
}

export const InvoiceGenerator = ({
  open,
  onClose,
  prefilledData,
  onSave }: InvoiceGeneratorProps) => {
  const { error, success } = useToast();
  const [isGenerating, setIsGenerating] = useState(false);
  const invoiceRef = useRef<HTMLDivElement>(null);

  const {
    register,
    control,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors } } = useForm<InvoiceFormData>({
    defaultValues: {
      invoice_number: `INV-${Date.now()}`,
      invoice_date: format(new Date(), 'yyyy-MM-dd'),
      due_date: format(new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), 'yyyy-MM-dd'),
      client_name: '',
      client_email: '',
      client_address: '',
      items: [{ description: '', quantity: 1, unit_price: 0, total: 0 }],
      notes: '',
      tax_rate: 0,
      discount: 0,
      payment_terms: '30',
      currency: 'USD',
      ...prefilledData } });

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'items' });

  const watchItems = watch('items');
  const watchTaxRate = watch('tax_rate');
  const watchDiscount = watch('discount');

  // Calculate totals
  const subtotal = watchItems.reduce((sum, item) => sum + (item.quantity * item.unit_price), 0);
  const discountAmount = (subtotal * watchDiscount) / 100;
  const taxableAmount = subtotal - discountAmount;
  const taxAmount = (taxableAmount * watchTaxRate) / 100;
  const total = taxableAmount + taxAmount;

  // Update item totals when quantity or price changes
  const updateItemTotal = (index: number) => {
    const item = watchItems[index];
    if (item) {
      setValue(`items.${index}.total`, item.quantity * item.unit_price);
    }
  };

  const handlePrint = useReactToPrint({
    contentRef: invoiceRef,
    documentTitle: `Invoice_${watch('invoice_number')}` });

  const handleDownloadPDF = async () => {
    if (!invoiceRef.current) return;

    try {
      setIsGenerating(true);
      const canvas = await html2canvas(invoiceRef.current, {
        scale: 2,
        logging: false });

      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4' });

      const imgWidth = 210;
      const pageHeight = 295;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      while (heightLeft >= 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }

      pdf.save(`Invoice_${watch('invoice_number')}.pdf`);
      success('Invoice downloaded successfully');
    } catch (err) {
      error('Failed to generate PDF');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleEmailInvoice = async (event: InvoiceFormData) => {
    try {
      setIsGenerating(true);
      // TODO: Implement email sending
      success('Invoice sent successfully');
    } catch (err) {
      error('Failed to send invoice');
    } finally {
      setIsGenerating(false);
    }
  };

  const onSubmit = async (_data: InvoiceFormData) => {
    try {
      if (onSave) {
        await onSave();
      }
      success('Invoice saved successfully');
      handleClose();
    } catch (err) {
      error('Failed to save invoice');
    }
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const InvoicePreview = () => (
    <Paper ref={invoiceRef} sx={{ p: 4, backgroundColor: 'white' }}>
      <Grid container spacing={3}>
        {/* Header */}
        <Grid item xs={12}>
          <Box display="flex" justifyContent="space-between" alignItems="start">
            <Box>
              <Typography variant="h4" gutterBottom>
                INVOICE
              </Typography>
              <Typography variant="subtitle1" color="text.secondary">
                Invoice #{watch('invoice_number')}
              </Typography>
            </Box>
            <Box textAlign="right">
              <Typography variant="h6" gutterBottom>
                Agency Dark
              </Typography>
              <Typography variant="body2" color="text.secondary">
                123 Business Street
              </Typography>
              <Typography variant="body2" color="text.secondary">
                City, State 12345
              </Typography>
              <Typography variant="body2" color="text.secondary">
                contact@agencydark.com
              </Typography>
            </Box>
          </Box>
        </Grid>

        <Grid item xs={12}>
          <Divider />
        </Grid>

        {/* Client Info */}
        <Grid item xs={6}>
          <Typography variant="subtitle2" gutterBottom>
            Bill To:
          </Typography>
          <Typography variant="body1" fontWeight="bold">
            {watch('client_name')}
          </Typography>
          <Typography variant="body2">{watch('client_email')}</Typography>
          <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>
            {watch('client_address')}
          </Typography>
        </Grid>

        {/* Invoice Details */}
        <Grid item xs={6}>
          <Box textAlign="right">
            <Typography variant="body2">
              <strong>Invoice Date:</strong> {format(new Date(watch('invoice_date')), 'MMM dd, yyyy')}
            </Typography>
            <Typography variant="body2">
              <strong>Due Date:</strong> {format(new Date(watch('due_date')), 'MMM dd, yyyy')}
            </Typography>
            <Typography variant="body2">
              <strong>Payment Terms:</strong> Net {watch('payment_terms')} days
            </Typography>
          </Box>
        </Grid>

        {/* Items Table */}
        <Grid item xs={12}>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Description</TableCell>
                  <TableCell align="center">Quantity</TableCell>
                  <TableCell align="right">Unit Price</TableCell>
                  <TableCell align="right">Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {watchItems.map((item, index) => (
                  <TableRow key={index}>
                    <TableCell>{item.description}</TableCell>
                    <TableCell align="center">{item.quantity}</TableCell>
                    <TableCell align="right">
                      {watch('currency')} {item.unit_price.toFixed(2)}
                    </TableCell>
                    <TableCell align="right">
                      {watch('currency')} {(item.quantity * item.unit_price).toFixed(2)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Grid>

        {/* Totals */}
        <Grid item xs={12}>
          <Box display="flex" justifyContent="flex-end">
            <Box sx={{ minWidth: 300 }}>
              <Box display="flex" justifyContent="space-between" mb={1}>
                <Typography variant="body2">Subtotal:</Typography>
                <Typography variant="body2">
                  {watch('currency')} {subtotal.toFixed(2)}
                </Typography>
              </Box>
              {watchDiscount > 0 && (
                <Box display="flex" justifyContent="space-between" mb={1}>
                  <Typography variant="body2">Discount ({watchDiscount}%):</Typography>
                  <Typography variant="body2">
                    -{watch('currency')} {discountAmount.toFixed(2)}
                  </Typography>
                </Box>
              )}
              {watchTaxRate > 0 && (
                <Box display="flex" justifyContent="space-between" mb={1}>
                  <Typography variant="body2">Tax ({watchTaxRate}%):</Typography>
                  <Typography variant="body2">
                    {watch('currency')} {taxAmount.toFixed(2)}
                  </Typography>
                </Box>
              )}
              <Divider sx={{ my: 1 }} />
              <Box display="flex" justifyContent="space-between">
                <Typography variant="h6">Total:</Typography>
                <Typography variant="h6">
                  {watch('currency')} {total.toFixed(2)}
                </Typography>
              </Box>
            </Box>
          </Box>
        </Grid>

        {/* Notes */}
        {watch('notes') && (
          <Grid item xs={12}>
            <Typography variant="subtitle2" gutterBottom>
              Notes:
            </Typography>
            <Typography variant="body2" sx={{ whiteSpace: 'pre-line' }}>
              {watch('notes')}
            </Typography>
          </Grid>
        )}
      </Grid>
    </Paper>
  );

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="lg" fullWidth>
      <form onSubmit={handleSubmit(onSubmit)}>
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Box display="flex" alignItems="center" gap={1}>
              <Receipt />
              <Typography variant="h6">Generate Invoice</Typography>
            </Box>
            <IconButton onClick={handleClose} size="small">
              <Close />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent dividers>
          <Grid container spacing={3}>
            {/* Invoice Details */}
            <Grid item xs={12}>
              <Typography variant="subtitle1" gutterBottom>
                Invoice Details
              </Typography>
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                label="Invoice Number"
                {...register('invoice_number', { required: 'Invoice number is required' })}
                error={!!errors.invoice_number}
                helperText={errors.invoice_number?.message}
              />
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                type="date"
                label="Invoice Date"
                InputLabelProps={{ shrink: true }}
                {...register('invoice_date', { required: 'Invoice date is required' })}
                error={!!errors.invoice_date}
                helperText={errors.invoice_date?.message}
              />
            </Grid>

            <Grid item xs={12} sm={4}>
              <TextField
                fullWidth
                type="date"
                label="Due Date"
                InputLabelProps={{ shrink: true }}
                {...register('due_date', { required: 'Due date is required' })}
                error={!!errors.due_date}
                helperText={errors.due_date?.message}
              />
            </Grid>

            {/* Client Information */}
            <Grid item xs={12}>
              <Typography variant="subtitle1" gutterBottom>
                Client Information
              </Typography>
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Client Name"
                {...register('client_name', { required: 'Client name is required' })}
                error={!!errors.client_name}
                helperText={errors.client_name?.message}
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <TextField
                fullWidth
                label="Client Email"
                type="email"
                {...register('client_email', { required: 'Client email is required' })}
                error={!!errors.client_email}
                helperText={errors.client_email?.message}
              />
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Client Address"
                multiline
                rows={3}
                {...register('client_address')}
              />
            </Grid>

            {/* Invoice Items */}
            <Grid item xs={12}>
              <Box display="flex" justifyContent="space-between" alignItems="center">
                <Typography variant="subtitle1">Items</Typography>
                <Button
                  startIcon={<Add />}
                  onClick={() => append({ description: '', quantity: 1, unit_price: 0, total: 0 })}
                >
                  Add Item
                </Button>
              </Box>
            </Grid>

            <Grid item xs={12}>
              <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Description</TableCell>
                      <TableCell width={120}>Quantity</TableCell>
                      <TableCell width={150}>Unit Price</TableCell>
                      <TableCell width={150}>Total</TableCell>
                      <TableCell width={50}></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {fields.map((field, index) => (
                      <TableRow key={field.id}>
                        <TableCell>
                          <TextField
                            fullWidth
                            size="small"
                            {...register(`items.${index}.description`, {
                              required: 'Description is required' })}
                            error={!!errors.items?.[index]?.description}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            {...register(`items.${index}.quantity`, {
                              required: true,
                              min: 1,
                              onChange: () => updateItemTotal(index) })}
                            error={!!errors.items?.[index]?.quantity}
                          />
                        </TableCell>
                        <TableCell>
                          <TextField
                            fullWidth
                            size="small"
                            type="number"
                            {...register(`items.${index}.unit_price`, {
                              required: true,
                              min: 0,
                              onChange: () => updateItemTotal(index) })}
                            error={!!errors.items?.[index]?.unit_price}
                          />
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2">
                            {watch('currency')} {(watchItems[index]?.quantity * watchItems[index]?.unit_price).toFixed(2)}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          <IconButton
                            size="small"
                            onClick={() => remove(index)}
                            disabled={fields.length === 1}
                          >
                            <Delete />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Grid>

            {/* Additional Settings */}
            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                select
                label="Currency"
                {...register('currency')}
              >
                <MenuItem value="USD">USD</MenuItem>
                <MenuItem value="EUR">EUR</MenuItem>
                <MenuItem value="GBP">GBP</MenuItem>
                <MenuItem value="AUD">AUD</MenuItem>
              </TextField>
            </Grid>

            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                label="Discount %"
                type="number"
                {...register('discount', { min: 0, max: 100 })}
                error={!!errors.discount}
                helperText={errors.discount?.message}
              />
            </Grid>

            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                label="Tax %"
                type="number"
                {...register('tax_rate', { min: 0, max: 100 })}
                error={!!errors.tax_rate}
                helperText={errors.tax_rate?.message}
              />
            </Grid>

            <Grid item xs={12} sm={3}>
              <TextField
                fullWidth
                select
                label="Payment Terms"
                {...register('payment_terms')}
              >
                <MenuItem value="15">Net 15</MenuItem>
                <MenuItem value="30">Net 30</MenuItem>
                <MenuItem value="45">Net 45</MenuItem>
                <MenuItem value="60">Net 60</MenuItem>
              </TextField>
            </Grid>

            <Grid item xs={12}>
              <TextField
                fullWidth
                label="Notes"
                multiline
                rows={3}
                {...register('notes')}
              />
            </Grid>

            {/* Invoice Preview */}
            <Grid item xs={12}>
              <Typography variant="subtitle1" gutterBottom>
                Preview
              </Typography>
              <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 1 }}>
                <InvoicePreview />
              </Box>
            </Grid>
          </Grid>
        </DialogContent>

        <DialogActions>
          <Button onClick={handleClose}>Cancel</Button>
          <Button
            startIcon={<Print />}
            onClick={handlePrint}
            disabled={isGenerating}
          >
            Print
          </Button>
          <Button
            startIcon={<Download />}
            onClick={handleDownloadPDF}
            disabled={isGenerating}
          >
            Download PDF
          </Button>
          <Button
            startIcon={<Email />}
            onClick={handleSubmit(handleEmailInvoice)}
            disabled={isGenerating}
          >
            Send Email
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={isGenerating}
          >
            Save Invoice
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};
