import { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  TextField,
  Button,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  InputAdornment,
  CircularProgress,
  Grid } from '@mui/material';
import { Calculate, TrendingUp } from '@mui/icons-material';
import { useQuery, useMutation } from '@tanstack/react-query';
import { financialApi } from '@/services/api/financial';
import type { CommissionTier } from '@/types/financial';

interface CommissionCalculatorProps {
  modelId?: string;
  agencyId?: string;
}

export const CommissionCalculator = ({ modelId, agencyId }: CommissionCalculatorProps) => {
  const [amount, setAmount] = useState<string>('');
  const [calculatedCommission, setCalculatedCommission] = useState<{
    commission: number;
    rate: number;
  } | null>(null);

  const { data: commissionRates, isPending } = useQuery({
    queryKey: ['commission-rates', modelId, agencyId],
    queryFn: () => financialApi.getCommissionRules({ model_id: modelId, agency_id: agencyId }) });

  const calculateMutation = useMutation({
    mutationFn: financialApi.calculateCommission,
    onSuccess: (data) => {
      setCalculatedCommission(data.data);
    } });

  const handleCalculate = () => {
    const numAmount = parseFloat(amount);
    if (!isNaN(numAmount) && numAmount > 0) {
      calculateMutation.mutate({
        gross_amount: numAmount,
        model_id: modelId || '',
        calculation_date: new Date().toISOString() });
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD' }).format(value);
  };

  const formatPercentage = (value: number) => {
    return `${(value * 100).toFixed(2)}%`;
  };

  const currentRate = commissionRates?.[0];
  const hasTiers = currentRate?.tiers && currentRate.tiers.length > 0;

  const getApplicableTier = (revenue: number) => {
    if (!hasTiers || !currentRate?.tiers) return null;
    
    return currentRate.tiers.find((tier: CommissionTier) => {
      const minOk = revenue >= tier.min_revenue;
      const maxOk = !tier.max_revenue || revenue <= tier.max_revenue;
      return minOk && maxOk;
    });
  };

  if (isPending) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight={300}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h5" mb={3}>Commission Calculator</Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Calculate Commission
              </Typography>
              
              <Box display="flex" flexDirection="column" gap={2}>
                <TextField
                  label="Revenue Amount"
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  fullWidth
                  InputProps={{
                    startAdornment: <InputAdornment position="start">$</InputAdornment> }}
                  helperText="Enter the revenue amount to calculate commission"
                />
                
                <Button
                  variant="contained"
                  startIcon={<Calculate />}
                  onClick={handleCalculate}
                  disabled={!amount || parseFloat(amount) <= 0 || calculateMutation.isPending}
                  fullWidth
                >
                  Calculate Commission
                </Button>

                {calculatedCommission && (
                  <Box mt={2}>
                    <Alert severity="info" icon={<TrendingUp />}>
                      <Box>
                        <Typography variant="body2">
                          Commission Rate: <strong>{formatPercentage(calculatedCommission.rate)}</strong>
                        </Typography>
                        <Typography variant="body2">
                          Commission Amount: <strong>{formatCurrency(calculatedCommission.commission)}</strong>
                        </Typography>
                        <Typography variant="body2">
                          Net Revenue: <strong>{formatCurrency(parseFloat(amount) - calculatedCommission.commission)}</strong>
                        </Typography>
                      </Box>
                    </Alert>
                  </Box>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Current Commission Structure
              </Typography>
              
              {currentRate ? (
                <Box>
                  <Typography variant="body2" color="textSecondary" gutterBottom>
                    Effective Date: {new Date(currentRate.effective_date).toLocaleDateString()}
                  </Typography>
                  
                  {hasTiers ? (
                    <>
                      <Typography variant="body2" gutterBottom>
                        Tiered Commission Structure:
                      </Typography>
                      <TableContainer component={Paper} variant="outlined" sx={{ mt: 2 }}>
                        <Table size="small">
                          <TableHead>
                            <TableRow>
                              <TableCell>Revenue Range</TableCell>
                              <TableCell align="right">Commission Rate</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {currentRate.tiers!.map((tier: CommissionTier, index: number) => {
                              const isApplicable = amount && getApplicableTier(parseFloat(amount))?.min_revenue === tier.min_revenue;
                              return (
                                <TableRow 
                                  key={index}
                                  sx={{
                                    backgroundColor: isApplicable ? 'action.selected' : undefined }}
                                >
                                  <TableCell>
                                    {formatCurrency(tier.min_revenue)} - {tier.max_revenue ? formatCurrency(tier.max_revenue) : 'Above'}
                                  </TableCell>
                                  <TableCell align="right">
                                    {formatPercentage(tier.rate)}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </>
                  ) : (
                    <Box mt={2}>
                      <Typography variant="h4" color="primary">
                        {formatPercentage(currentRate.rate)}
                      </Typography>
                      <Typography variant="body2" color="textSecondary">
                        Flat commission rate
                      </Typography>
                    </Box>
                  )}
                </Box>
              ) : (
                <Alert severity="warning">
                  No commission structure found. Please contact support.
                </Alert>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Commission Examples
              </Typography>
              
              <TableContainer component={Paper} variant="outlined">
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Revenue</TableCell>
                      <TableCell align="right">Commission Rate</TableCell>
                      <TableCell align="right">Commission</TableCell>
                      <TableCell align="right">Net Revenue</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {[100, 500, 1000, 5000, 10000].map((exampleAmount) => {
                      const tier = hasTiers ? getApplicableTier(exampleAmount) : null;
                      const rate = tier ? tier.rate : (currentRate?.rate || 0);
                      const commission = exampleAmount * rate;
                      const net = exampleAmount - commission;
                      
                      return (
                        <TableRow key={exampleAmount}>
                          <TableCell>{formatCurrency(exampleAmount)}</TableCell>
                          <TableCell align="right">{formatPercentage(rate)}</TableCell>
                          <TableCell align="right">{formatCurrency(commission)}</TableCell>
                          <TableCell align="right">{formatCurrency(net)}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};
