import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Tab,
  Tabs,
  Button,
  Alert,
  LinearProgress,
  Chip,
  IconButton,
  Tooltip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  People,
  AttachMoney,
  Lightbulb,
  Refresh,
  ModelTraining,
  Analytics,
  ErrorOutline,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { mlInsightsService } from '@/services/api/mlInsights';
import { useAuthStore } from '@/store/authStore';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip as ChartTooltip,
  Legend,
  Filler,
} from 'chart.js';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  ChartTooltip,
  Legend,
  Filler
);

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`ml-tabpanel-${index}`}
      aria-labelledby={`ml-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ py: 3 }}>{children}</Box>}
    </div>
  );
}

export const MLInsightsDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [forecastPeriod, setForecastPeriod] = useState(30);
  const queryClient = useQueryClient();
  const { user } = useAuthStore();
  const agencyId = user?.agency_id;

  // Queries
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['ml-insights-summary', agencyId],
    queryFn: () => mlInsightsService.getInsightsSummary(agencyId),
    refetchInterval: 60000, // Refresh every minute
  });

  const { data: forecast, isLoading: forecastLoading } = useQuery({
    queryKey: ['revenue-forecast', forecastPeriod, agencyId],
    queryFn: () => mlInsightsService.getRevenueForecast(forecastPeriod, agencyId),
    enabled: activeTab === 0,
  });

  const { data: churnData, isLoading: churnLoading } = useQuery({
    queryKey: ['churn-predictions', agencyId],
    queryFn: () => mlInsightsService.getChurnPredictions(agencyId),
    enabled: activeTab === 1,
  });

  const { data: contentRecs, isLoading: contentLoading } = useQuery({
    queryKey: ['content-recommendations', agencyId],
    queryFn: () => mlInsightsService.getContentRecommendations(agencyId),
    enabled: activeTab === 2,
  });

  const { data: anomalies, isLoading: anomaliesLoading } = useQuery({
    queryKey: ['anomalies', agencyId],
    queryFn: () => mlInsightsService.getAnomalies(agencyId),
    enabled: activeTab === 3,
  });

  // Mutations for training models
  const trainRevenueMutation = useMutation({
    mutationFn: () => mlInsightsService.trainRevenueModel(agencyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revenue-forecast'] });
    },
  });

  const trainChurnMutation = useMutation({
    mutationFn: () => mlInsightsService.trainChurnModel(agencyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['churn-predictions'] });
    },
  });

  const handleTabChange = (_: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  };

  // Revenue chart data
  const revenueChartData = {
    labels: forecast?.forecasts.map((f) => format(new Date(f.date), 'MMM dd')) || [],
    datasets: [
      {
        label: 'Predicted Revenue',
        data: forecast?.forecasts.map((f) => f.predicted_revenue) || [],
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        tension: 0.1,
      },
      {
        label: 'Upper Bound',
        data: forecast?.forecasts.map((f) => f.upper_bound) || [],
        borderColor: 'rgba(75, 192, 192, 0.3)',
        borderDash: [5, 5],
        fill: false,
      },
      {
        label: 'Lower Bound',
        data: forecast?.forecasts.map((f) => f.lower_bound) || [],
        borderColor: 'rgba(75, 192, 192, 0.3)',
        borderDash: [5, 5],
        fill: false,
      },
    ],
  };

  // Churn distribution chart
  const churnChartData = {
    labels: ['Low Risk', 'Medium Risk', 'High Risk', 'Critical'],
    datasets: [
      {
        data: [
          churnData?.risk_distribution.low || 0,
          churnData?.risk_distribution.medium || 0,
          churnData?.risk_distribution.high || 0,
          churnData?.risk_distribution.critical || 0,
        ],
        backgroundColor: ['#4caf50', '#ff9800', '#ff5722', '#d32f2f'],
      },
    ],
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'error';
      case 'high':
        return 'warning';
      case 'medium':
        return 'info';
      default:
        return 'success';
    }
  };

  if (summaryLoading) {
    return (
      <Box sx={{ p: 3 }}>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>
        ML Insights Dashboard
      </Typography>

      {/* Summary Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <AttachMoney color="primary" sx={{ mr: 1 }} />
                <Typography color="textSecondary" gutterBottom>
                  Revenue Forecast
                </Typography>
              </Box>
              <Typography variant="h5">
                ${summary?.revenue_forecast.next_30_days.toLocaleString()}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                {summary?.revenue_forecast.trend === 'up' ? (
                  <TrendingUp color="success" />
                ) : summary?.revenue_forecast.trend === 'down' ? (
                  <TrendingDown color="error" />
                ) : (
                  <TrendingUp color="action" />
                )}
                <Typography variant="body2" sx={{ ml: 1 }}>
                  {summary?.revenue_forecast.confidence}% confidence
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <People color="warning" sx={{ mr: 1 }} />
                <Typography color="textSecondary" gutterBottom>
                  At-Risk Fans
                </Typography>
              </Box>
              <Typography variant="h5">
                {summary?.churn_risk.at_risk_count}
              </Typography>
              <Typography variant="body2" color="error">
                ${summary?.churn_risk.potential_revenue_loss.toLocaleString()} at risk
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Lightbulb color="info" sx={{ mr: 1 }} />
                <Typography color="textSecondary" gutterBottom>
                  Content Opportunities
                </Typography>
              </Box>
              <Typography variant="h5">
                {summary?.content_performance.optimization_opportunities}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                {summary?.content_performance.engagement_trend === 'up' ? (
                  <TrendingUp color="success" />
                ) : summary?.content_performance.engagement_trend === 'down' ? (
                  <TrendingDown color="error" />
                ) : (
                  <TrendingUp color="action" />
                )}
                <Typography variant="body2" sx={{ ml: 1 }}>
                  Engagement trend
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <Warning color="error" sx={{ mr: 1 }} />
                <Typography color="textSecondary" gutterBottom>
                  Active Anomalies
                </Typography>
              </Box>
              <Typography variant="h5">
                {summary?.anomalies.active_count}
              </Typography>
              <Typography variant="body2" color="error">
                {summary?.anomalies.critical_count} critical
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Tabs */}
      <Paper sx={{ mb: 3 }}>
        <Tabs value={activeTab} onChange={handleTabChange}>
          <Tab label="Revenue Forecast" icon={<TrendingUp />} iconPosition="start" />
          <Tab label="Churn Prediction" icon={<People />} iconPosition="start" />
          <Tab label="Content Recommendations" icon={<Lightbulb />} iconPosition="start" />
          <Tab label="Anomaly Detection" icon={<Warning />} iconPosition="start" />
        </Tabs>
      </Paper>

      {/* Revenue Forecast Tab */}
      <TabPanel value={activeTab} index={0}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6">Revenue Forecast</Typography>
                <Box sx={{ display: 'flex', gap: 2 }}>
                  <FormControl size="small">
                    <InputLabel>Period</InputLabel>
                    <Select
                      value={forecastPeriod}
                      label="Period"
                      onChange={(e) => setForecastPeriod(e.target.value as number)}
                    >
                      <MenuItem value={7}>7 days</MenuItem>
                      <MenuItem value={30}>30 days</MenuItem>
                      <MenuItem value={90}>90 days</MenuItem>
                    </Select>
                  </FormControl>
                  <Button
                    variant="outlined"
                    startIcon={<ModelTraining />}
                    onClick={() => trainRevenueMutation.mutate()}
                    disabled={trainRevenueMutation.isPending}
                  >
                    Retrain Model
                  </Button>
                </Box>
              </Box>
              {forecastLoading ? (
                <LinearProgress />
              ) : (
                <>
                  <Box sx={{ height: 400 }}>
                    <Line
                      data={revenueChartData}
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: {
                            position: 'top',
                          },
                          title: {
                            display: false,
                          },
                        },
                      }}
                    />
                  </Box>
                  <Grid container spacing={2} sx={{ mt: 3 }}>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" color="textSecondary">
                        Total Predicted Revenue
                      </Typography>
                      <Typography variant="h4">
                        ${forecast?.summary.total_predicted.toLocaleString()}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" color="textSecondary">
                        Average Daily Revenue
                      </Typography>
                      <Typography variant="h4">
                        ${forecast?.summary.average_daily.toLocaleString()}
                      </Typography>
                    </Grid>
                    <Grid item xs={12} md={4}>
                      <Typography variant="subtitle2" color="textSecondary">
                        Growth Rate
                      </Typography>
                      <Typography variant="h4">
                        {forecast?.summary.growth_rate}%
                      </Typography>
                    </Grid>
                  </Grid>
                </>
              )}
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Churn Prediction Tab */}
      <TabPanel value={activeTab} index={1}>
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
                <Typography variant="h6">Risk Distribution</Typography>
                <IconButton
                  size="small"
                  onClick={() => trainChurnMutation.mutate()}
                  disabled={trainChurnMutation.isPending}
                >
                  <Refresh />
                </IconButton>
              </Box>
              {churnLoading ? (
                <LinearProgress />
              ) : (
                <Box sx={{ height: 300 }}>
                  <Doughnut
                    data={churnChartData}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                    }}
                  />
                </Box>
              )}
            </Paper>
          </Grid>
          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                High Risk Fans
              </Typography>
              {churnLoading ? (
                <LinearProgress />
              ) : (
                <Box sx={{ maxHeight: 400, overflow: 'auto' }}>
                  {churnData?.high_risk_fans.map((fan) => (
                    <Box
                      key={fan.fan_id}
                      sx={{
                        p: 2,
                        mb: 2,
                        border: '1px solid',
                        borderColor: 'divider',
                        borderRadius: 1,
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="subtitle1">{fan.fan_username}</Typography>
                        <Chip
                          label={`${fan.risk_level} risk`}
                          color={getSeverityColor(fan.risk_level)}
                          size="small"
                        />
                      </Box>
                      <Typography variant="body2" color="textSecondary">
                        Risk Score: {fan.risk_score}% | LTV: ${fan.lifetime_value}
                      </Typography>
                      <Typography variant="body2" sx={{ mt: 1 }}>
                        Factors: {fan.factors.join(', ')}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Content Recommendations Tab */}
      <TabPanel value={activeTab} index={2}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Content Recommendations
              </Typography>
              {contentLoading ? (
                <LinearProgress />
              ) : (
                <Grid container spacing={2}>
                  {contentRecs?.recommendations.map((rec, index) => (
                    <Grid item xs={12} md={6} key={index}>
                      <Card variant="outlined">
                        <CardContent>
                          <Typography variant="h6">{rec.title}</Typography>
                          <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                            {rec.description}
                          </Typography>
                          <Grid container spacing={1}>
                            <Grid item xs={6}>
                              <Typography variant="caption" color="textSecondary">
                                Predicted Engagement
                              </Typography>
                              <Typography variant="body1">
                                {rec.predicted_engagement}%
                              </Typography>
                            </Grid>
                            <Grid item xs={6}>
                              <Typography variant="caption" color="textSecondary">
                                Predicted Revenue
                              </Typography>
                              <Typography variant="body1">
                                ${rec.predicted_revenue}
                              </Typography>
                            </Grid>
                          </Grid>
                          <Box sx={{ mt: 2 }}>
                            <Typography variant="caption" color="textSecondary">
                              Best Time: {format(new Date(rec.optimal_time), 'MMM dd, h:mm a')}
                            </Typography>
                          </Box>
                          <Box sx={{ mt: 1 }}>
                            {rec.target_segments.map((segment) => (
                              <Chip
                                key={segment}
                                label={segment}
                                size="small"
                                sx={{ mr: 1, mb: 1 }}
                              />
                            ))}
                          </Box>
                        </CardContent>
                      </Card>
                    </Grid>
                  ))}
                </Grid>
              )}
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>

      {/* Anomaly Detection Tab */}
      <TabPanel value={activeTab} index={3}>
        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Detected Anomalies
              </Typography>
              {anomaliesLoading ? (
                <LinearProgress />
              ) : anomalies?.anomalies.length === 0 ? (
                <Alert severity="success">No anomalies detected</Alert>
              ) : (
                <Box>
                  {anomalies?.anomalies.map((anomaly, index) => (
                    <Alert
                      key={index}
                      severity={getSeverityColor(anomaly.severity)}
                      sx={{ mb: 2 }}
                      action={
                        anomaly.action_required && (
                          <Button color="inherit" size="small">
                            Take Action
                          </Button>
                        )
                      }
                    >
                      <Typography variant="subtitle1">{anomaly.anomaly_type}</Typography>
                      <Typography variant="body2">{anomaly.description}</Typography>
                      <Typography variant="caption" display="block" sx={{ mt: 1 }}>
                        Detected: {format(new Date(anomaly.detected_at), 'MMM dd, h:mm a')} |
                        Entity: {anomaly.affected_entity}
                      </Typography>
                      {anomaly.suggested_action && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          Suggested Action: {anomaly.suggested_action}
                        </Typography>
                      )}
                    </Alert>
                  ))}
                </Box>
              )}
            </Paper>
          </Grid>
        </Grid>
      </TabPanel>
    </Box>
  );
};