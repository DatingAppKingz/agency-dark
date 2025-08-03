import { vi } from 'vitest';
import mockIcons from '../utils/mui-icon-mocks';

// Mock all @mui/icons-material imports
vi.mock('@mui/icons-material', () => mockIcons);

// Also mock individual icon imports
vi.mock('@mui/icons-material/TrendingUp', () => ({
  default: mockIcons.TrendingUp
}));

vi.mock('@mui/icons-material/TrendingDown', () => ({
  default: mockIcons.TrendingDown
}));

vi.mock('@mui/icons-material/AttachMoney', () => ({
  default: mockIcons.AttachMoney
}));

vi.mock('@mui/icons-material/People', () => ({
  default: mockIcons.People
}));

vi.mock('@mui/icons-material/Favorite', () => ({
  default: mockIcons.Favorite
}));

vi.mock('@mui/icons-material/Message', () => ({
  default: mockIcons.Message
}));

// Add more individual mocks as needed