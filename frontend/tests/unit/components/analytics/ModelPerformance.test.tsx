import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ModelPerformance } from '@/components/analytics/ModelPerformance';
import { format } from 'date-fns';

// Mock recharts components
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  LineChart: ({ children }: any) => <div data-testid="line-chart">{children}</div>,
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  PieChart: ({ children }: any) => <div data-testid="pie-chart">{children}</div>,
  Line: () => <div data-testid="line" />,
  Area: () => <div data-testid="area" />,
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div data-testid="cell" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="tooltip" />,
  Legend: () => <div data-testid="legend" />
}));

// Mock MUI icons
vi.mock('@mui/icons-material', () => ({
  TrendingUp: () => <div data-testid="trending-up-icon" />,
  AttachMoney: () => <div data-testid="attach-money-icon" />,
  People: () => <div data-testid="people-icon" />,
  Favorite: () => <div data-testid="favorite-icon" />,
  Message: () => <div data-testid="message-icon" />
}));

describe('ModelPerformance Component', () => {
  let queryClient: QueryClient;

  const defaultProps = {
    dateRange: {
      start: new Date('2024-01-01'),
      end: new Date('2024-01-31')
    },
    refreshKey: 0
  };

  const mockPerformanceData = {
    summary: {
      totalEarnings: 45000,
      earningsChange: 18.5,
      totalSubscribers: 850,
      newSubscribers: 125,
      totalMessages: 12500,
      avgResponseTime: 3.2,
      contentPieces: 156,
      fanEngagement: 78.5
    },
    earningsChart: [
      {
        date: 'Jan 1',
        earnings: 1500,
        tips: 300,
        subscriptions: 800
      },
      {
        date: 'Jan 2',
        earnings: 1800,
        tips: 400,
        subscriptions: 900
      }
    ],
    subscriberGrowth: [
      {
        date: 'Jan 1',
        total: 600,
        new: 5,
        lost: 1
      },
      {
        date: 'Jan 2',
        total: 604,
        new: 6,
        lost: 2
      }
    ],
    topFans: [
      {
        name: 'JohnDoe123',
        spent: 2500,
        messages: 450,
        joinDate: '2023-06-15',
        tier: 'VIP'
      },
      {
        name: 'MikeSmith',
        spent: 1800,
        messages: 320,
        joinDate: '2023-08-20',
        tier: 'Premium'
      }
    ],
    contentPerformance: [
      { type: 'Photos', count: 85, revenue: 15000 },
      { type: 'Videos', count: 45, revenue: 18000 }
    ],
    engagementMetrics: [
      { hour: '12 PM', messages: 45, views: 320 },
      { hour: '8 PM', messages: 65, views: 450 }
    ],
    goals: [
      { name: 'Monthly Earnings', target: 50000, current: 45000 },
      { name: 'New Subscribers', target: 150, current: 125 }
    ]
  };

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false
        }
      }
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = (props = {}) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <ModelPerformance {...defaultProps} {...props} />
      </QueryClientProvider>
    );
  };

  describe('Summary Section', () => {
    it('should display loading state initially', () => {
      renderComponent();
      expect(screen.getAllByRole('progressbar')).toHaveLength(6);
    });

    it('should display performance summary metrics', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('$45,000')).toBeInTheDocument();
        expect(screen.getByText('+18.5%')).toBeInTheDocument();
        expect(screen.getByText('850')).toBeInTheDocument();
        expect(screen.getByText('125 new')).toBeInTheDocument();
        expect(screen.getByText('12,500')).toBeInTheDocument();
        expect(screen.getByText('3.2 min avg')).toBeInTheDocument();
        expect(screen.getByText('156')).toBeInTheDocument();
        expect(screen.getByText('78.5%')).toBeInTheDocument();
      });
    });

    it('should display metric labels correctly', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Total Earnings')).toBeInTheDocument();
        expect(screen.getByText('Total Subscribers')).toBeInTheDocument();
        expect(screen.getByText('Total Messages')).toBeInTheDocument();
        expect(screen.getByText('Content Pieces')).toBeInTheDocument();
      });
    });
  });

  describe('Model Selection', () => {
    it('should display model selector dropdown', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        const select = screen.getByLabelText('Select Model');
        expect(select).toBeInTheDocument();
      });
    });

    it('should change selected model when dropdown value changes', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        const select = screen.getByLabelText('Select Model');
        fireEvent.mouseDown(select);
      });

      const option = screen.getByRole('option', { name: 'All Models' });
      fireEvent.click(option);

      expect(screen.getByDisplayValue('All Models')).toBeInTheDocument();
    });
  });

  describe('Charts', () => {
    it('should render earnings chart', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Earnings Breakdown')).toBeInTheDocument();
        expect(screen.getByTestId('area-chart')).toBeInTheDocument();
      });
    });

    it('should render subscriber growth chart', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Subscriber Growth')).toBeInTheDocument();
        expect(screen.getByTestId('line-chart')).toBeInTheDocument();
      });
    });

    it('should render content performance pie chart', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Content Performance')).toBeInTheDocument();
        expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
      });
    });

    it('should render engagement metrics chart', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Fan Engagement by Hour')).toBeInTheDocument();
        const lineCharts = screen.getAllByTestId('line-chart');
        expect(lineCharts).toHaveLength(2); // Both subscriber and engagement charts
      });
    });
  });

  describe('Top Fans List', () => {
    it('should display top fans section', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Top Fans')).toBeInTheDocument();
      });
    });

    it('should display fan details correctly', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('JohnDoe123')).toBeInTheDocument();
        expect(screen.getByText('$2,500 spent')).toBeInTheDocument();
        expect(screen.getByText('450 messages')).toBeInTheDocument();
        expect(screen.getByText('VIP')).toBeInTheDocument();

        expect(screen.getByText('MikeSmith')).toBeInTheDocument();
        expect(screen.getByText('$1,800 spent')).toBeInTheDocument();
        expect(screen.getByText('320 messages')).toBeInTheDocument();
        expect(screen.getByText('Premium')).toBeInTheDocument();
      });
    });

    it('should display fan tier chips with correct styling', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        const vipChip = screen.getByText('VIP');
        const premiumChip = screen.getByText('Premium');
        
        expect(vipChip).toHaveClass('MuiChip-root');
        expect(premiumChip).toHaveClass('MuiChip-root');
      });
    });
  });

  describe('Goals Progress', () => {
    it('should display goals section', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Monthly Goals')).toBeInTheDocument();
      });
    });

    it('should display goal progress correctly', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Monthly Earnings')).toBeInTheDocument();
        expect(screen.getByText('$45,000 / $50,000')).toBeInTheDocument();
        expect(screen.getByText('90%')).toBeInTheDocument();

        expect(screen.getByText('New Subscribers')).toBeInTheDocument();
        expect(screen.getByText('125 / 150')).toBeInTheDocument();
        expect(screen.getByText('83%')).toBeInTheDocument();
      });
    });

    it('should display progress bars', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        const progressBars = screen.getAllByRole('progressbar');
        // 6 loading indicators initially replaced by 2 goal progress bars
        expect(progressBars.length).toBeGreaterThanOrEqual(2);
      });
    });
  });

  describe('Data Refresh', () => {
    it('should refetch data when refreshKey changes', async () => {
      const { rerender } = renderComponent();

      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      await waitFor(() => {
        expect(screen.getByText('$45,000')).toBeInTheDocument();
      });

      // Update with new refresh key
      const newData = {
        ...mockPerformanceData,
        summary: {
          ...mockPerformanceData.summary,
          totalEarnings: 50000
        }
      };

      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 1, 'all'],
        newData
      );

      rerender(
        <QueryClientProvider client={queryClient}>
          <ModelPerformance {...defaultProps} refreshKey={1} />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('$50,000')).toBeInTheDocument();
      });
    });

    it('should refetch data when date range changes', async () => {
      const { rerender } = renderComponent();

      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      await waitFor(() => {
        expect(screen.getByText('$45,000')).toBeInTheDocument();
      });

      const newDateRange = {
        start: new Date('2024-02-01'),
        end: new Date('2024-02-28')
      };

      const newData = {
        ...mockPerformanceData,
        summary: {
          ...mockPerformanceData.summary,
          totalEarnings: 55000
        }
      };

      queryClient.setQueryData(
        ['model-performance', newDateRange, 0, 'all'],
        newData
      );

      rerender(
        <QueryClientProvider client={queryClient}>
          <ModelPerformance dateRange={newDateRange} refreshKey={0} />
        </QueryClientProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('$55,000')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      queryClient.setQueryFn(['model-performance'], () => {
        throw new Error('API Error');
      });

      renderComponent();

      await waitFor(() => {
        // Component should still render, possibly with loading state
        expect(screen.getAllByRole('progressbar')).toHaveLength(6);
      });

      consoleError.mockRestore();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible labels for all sections', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        expect(screen.getByText('Model Performance Dashboard')).toBeInTheDocument();
        expect(screen.getByLabelText('Select Model')).toBeInTheDocument();
      });
    });

    it('should use semantic HTML elements', async () => {
      queryClient.setQueryData(
        ['model-performance', defaultProps.dateRange, 0, 'all'],
        mockPerformanceData
      );

      renderComponent();

      await waitFor(() => {
        const headings = screen.getAllByRole('heading');
        expect(headings.length).toBeGreaterThan(0);
      });
    });
  });
});