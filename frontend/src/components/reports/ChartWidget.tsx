import React, {  } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper } from '@mui/material';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart } from 'recharts';
import { ReportWidget, ChartType } from '@/types/reports';
import { formatCurrency, formatNumber, formatPercentage } from '@/utils/formatters';

interface ChartWidgetProps {
  widget: ReportWidget;
  onUpdate: (updates: Partial<ReportWidget>) => void;
  fullscreen?: boolean;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8', '#82CA9D', '#FFC658', '#8DD1E1'];

const ChartWidget: React.FC<ChartWidgetProps> = ({ widget, fullscreen }) => {
  const { chartConfig, data, loading, error } = widget;

  const formatValue = (value: any, format?: string) => {
    if (value === null || value === undefined) return '-';
    
    switch (format) {
      case 'currency':
        return formatCurrency(value);
      case 'percentage':
        return formatPercentage(value);
      case 'number':
        return formatNumber(value);
      default:
        return value;
    }
  };

  const renderChart = () => {
    if (!data || data.length === 0) {
      return (
        <Box
          sx={{
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center' }}
        >
          <Typography variant="body2" color="text.secondary">
            No data available
          </Typography>
        </Box>
      );
    }

    switch (chartConfig.type) {
      case ChartType.LINE:
        return (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              {chartConfig.options?.showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={chartConfig.dimensions[0]?.field || 'name'} />
              <YAxis />
              {chartConfig.options?.showTooltip && <Tooltip />}
              {chartConfig.options?.showLegend && <Legend />}
              {chartConfig.metrics.map((metric, index) => (
                <Line
                  key={metric.id}
                  type={chartConfig.options?.smooth ? 'monotone' : 'linear'}
                  dataKey={metric.field}
                  name={metric.name}
                  stroke={metric.color || COLORS[index % COLORS.length]}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        );

      case ChartType.BAR:
        return (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              {chartConfig.options?.showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={chartConfig.dimensions[0]?.field || 'name'} />
              <YAxis />
              {chartConfig.options?.showTooltip && <Tooltip />}
              {chartConfig.options?.showLegend && <Legend />}
              {chartConfig.metrics.map((metric, index) => (
                <Bar
                  key={metric.id}
                  dataKey={metric.field}
                  name={metric.name}
                  fill={metric.color || COLORS[index % COLORS.length]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        );

      case ChartType.PIE:
        return (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey={chartConfig.metrics[0]?.field || 'value'}
                nameKey={chartConfig.dimensions[0]?.field || 'name'}
                cx="50%"
                cy="50%"
                outerRadius="80%"
                label={chartConfig.options?.showDataLabels}
              >
                {data.map((_entry: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              {chartConfig.options?.showTooltip && <Tooltip />}
              {chartConfig.options?.showLegend && <Legend />}
            </PieChart>
          </ResponsiveContainer>
        );

      case ChartType.AREA:
        return (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              {chartConfig.options?.showGrid && <CartesianGrid strokeDasharray="3 3" />}
              <XAxis dataKey={chartConfig.dimensions[0]?.field || 'name'} />
              <YAxis />
              {chartConfig.options?.showTooltip && <Tooltip />}
              {chartConfig.options?.showLegend && <Legend />}
              {chartConfig.metrics.map((metric, index) => (
                <Area
                  key={metric.id}
                  type={chartConfig.options?.smooth ? 'monotone' : 'linear'}
                  dataKey={metric.field}
                  name={metric.name}
                  stroke={metric.color || COLORS[index % COLORS.length]}
                  fill={metric.color || COLORS[index % COLORS.length]}
                  fillOpacity={0.6}
                  stackId={chartConfig.options?.stacked ? 'stack' : undefined}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        );

      case ChartType.TABLE:
        const columns = [
          ...chartConfig.dimensions.map(d => ({ field: d.field, label: d.name, format: undefined })),
          ...chartConfig.metrics.map(m => ({ field: m.field, label: m.name, format: m.format })),
        ];

        return (
          <TableContainer component={Paper} sx={{ height: '100%' }}>
            <Table stickyHeader size="small">
              <TableHead>
                <TableRow>
                  {columns.map((col) => (
                    <TableCell key={col.field}>{col.label}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {data.map((row: any, index: number) => (
                  <TableRow key={index}>
                    {columns.map((col) => (
                      <TableCell key={col.field}>
                        {formatValue(row[col.field], col.format)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        );

      case ChartType.METRIC_CARD:
        const metric = chartConfig.metrics[0];
        const value = data[0]?.[metric?.field];
        const formattedValue = formatValue(value, metric?.format);

        return (
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              p: 2 }}
          >
            <Box textAlign="center">
              <Typography variant="h6" color="text.secondary" gutterBottom>
                {metric?.name || 'Metric'}
              </Typography>
              <Typography
                variant={fullscreen ? 'h1' : 'h3'}
                color="primary"
                sx={{ fontWeight: 'bold' }}
              >
                {formattedValue}
              </Typography>
              {data[0]?.comparison && (
                <Typography
                  variant="body2"
                  color={data[0].comparison > 0 ? 'success.main' : 'error.main'}
                  sx={{ mt: 1 }}
                >
                  {data[0].comparison > 0 ? '+' : ''}{formatPercentage(data[0].comparison)} vs previous period
                </Typography>
              )}
            </Box>
          </Box>
        );

      default:
        return (
          <Box
            sx={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center' }}
          >
            <Typography variant="body2" color="text.secondary">
              Unsupported chart type: {chartConfig.type}
            </Typography>
          </Box>
        );
    }
  };

  if (loading) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center' }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', position: 'relative' }}>
      {renderChart()}
    </Box>
  );
};

export default ChartWidget;
