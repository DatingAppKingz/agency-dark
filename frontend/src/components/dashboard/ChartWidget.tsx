import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  ButtonGroup,
  Button,
  Skeleton,
  useTheme } from '@mui/material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend } from 'recharts';

type ChartType = 'line' | 'area' | 'bar' | 'pie';
type TimeRange = 'week' | 'month' | 'quarter' | 'year';

interface ChartData {
  label: string;
  value: number;
  [key: string]: any;
}

interface ChartWidgetProps {
  title: string;
  data: ChartData[];
  type?: ChartType;
  height?: number;
  showTimeRangeSelector?: boolean;
  onTimeRangeChange?: (range: TimeRange) => void;
  dataKey?: string;
  color?: string;
  colors?: string[];
  loading?: boolean;
  valueFormatter?: (value: number) => string;
}

export const ChartWidget: React.FC<ChartWidgetProps> = ({
  title,
  data,
  type = 'line',
  height = 300,
  showTimeRangeSelector = false,
  onTimeRangeChange,
  dataKey = 'value',
  color,
  colors,
  loading = false,
  valueFormatter = (value) => value.toLocaleString() }) => {
  const theme = useTheme();
  const [selectedRange, setSelectedRange] = React.useState<TimeRange>('month');

  const defaultColor = color || theme.palette.primary.main;
  const chartColors = colors || [
    theme.palette.primary.main,
    theme.palette.secondary.main,
    theme.palette.success.main,
    theme.palette.warning.main,
    theme.palette.error.main,
  ];

  const handleRangeChange = (range: TimeRange) => {
    setSelectedRange(range);
    onTimeRangeChange?.(range);
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Skeleton variant="text" width="30%" height={32} />
            {showTimeRangeSelector && (
              <Skeleton variant="rectangular" width={200} height={36} />
            )}
          </Box>
          <Skeleton variant="rectangular" height={height} />
        </CardContent>
      </Card>
    );
  }

  const renderChart = () => {
    switch (type) {
      case 'area':
        return (
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
            <XAxis 
              dataKey="label" 
              stroke={theme.palette.text.secondary}
              style={{ fontSize: 12 }}
            />
            <YAxis 
              stroke={theme.palette.text.secondary}
              style={{ fontSize: 12 }}
              tickFormatter={valueFormatter}
            />
            <Tooltip 
              formatter={valueFormatter}
              contentStyle={{
                backgroundColor: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}` }}
            />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={defaultColor}
              fill={defaultColor}
              fillOpacity={0.6}
            />
          </AreaChart>
        );

      case 'bar':
        return (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
            <XAxis 
              dataKey="label" 
              stroke={theme.palette.text.secondary}
              style={{ fontSize: 12 }}
            />
            <YAxis 
              stroke={theme.palette.text.secondary}
              style={{ fontSize: 12 }}
              tickFormatter={valueFormatter}
            />
            <Tooltip 
              formatter={valueFormatter}
              contentStyle={{
                backgroundColor: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}` }}
            />
            <Bar dataKey={dataKey} fill={defaultColor} />
          </BarChart>
        );

      case 'pie':
        return (
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={(entry) => `${entry.label}: ${valueFormatter(entry[dataKey])}`}
              outerRadius={80}
              fill={defaultColor}
              dataKey={dataKey}
            >
              {data.map((_entry, index) => (
                <Cell key={`cell-${index}`} fill={chartColors[index % chartColors.length]} />
              ))}
            </Pie>
            <Tooltip 
              formatter={valueFormatter}
              contentStyle={{
                backgroundColor: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}` }}
            />
            <Legend />
          </PieChart>
        );

      case 'line':
      default:
        return (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
            <XAxis 
              dataKey="label" 
              stroke={theme.palette.text.secondary}
              style={{ fontSize: 12 }}
            />
            <YAxis 
              stroke={theme.palette.text.secondary}
              style={{ fontSize: 12 }}
              tickFormatter={valueFormatter}
            />
            <Tooltip 
              formatter={valueFormatter}
              contentStyle={{
                backgroundColor: theme.palette.background.paper,
                border: `1px solid ${theme.palette.divider}` }}
            />
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={defaultColor}
              strokeWidth={2}
              dot={{ fill: defaultColor }}
            />
          </LineChart>
        );
    }
  };

  return (
    <Card>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6">{title}</Typography>
          
          {showTimeRangeSelector && (
            <ButtonGroup size="small">
              <Button
                variant={selectedRange === 'week' ? 'contained' : 'outlined'}
                onClick={() => handleRangeChange('week')}
              >
                Week
              </Button>
              <Button
                variant={selectedRange === 'month' ? 'contained' : 'outlined'}
                onClick={() => handleRangeChange('month')}
              >
                Month
              </Button>
              <Button
                variant={selectedRange === 'quarter' ? 'contained' : 'outlined'}
                onClick={() => handleRangeChange('quarter')}
              >
                Quarter
              </Button>
              <Button
                variant={selectedRange === 'year' ? 'contained' : 'outlined'}
                onClick={() => handleRangeChange('year')}
              >
                Year
              </Button>
            </ButtonGroup>
          )}
        </Box>

        <Box height={height}>
          <ResponsiveContainer width="100%" height="100%">
            {renderChart()}
          </ResponsiveContainer>
        </Box>
      </CardContent>
    </Card>
  );
};
