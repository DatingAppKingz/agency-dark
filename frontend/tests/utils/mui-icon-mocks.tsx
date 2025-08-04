import React from 'react';

// Comprehensive MUI Icon mocks
export const mockIcons = {
  // Layout & Navigation
  Dashboard: () => <div data-testid="dashboard-icon" />,
  People: () => <div data-testid="people-icon" />,
  Person: () => <div data-testid="person-icon" />,
  Chat: () => <div data-testid="chat-icon" />,
  Analytics: () => <div data-testid="analytics-icon" />,
  AttachMoney: () => <div data-testid="attach-money-icon" />,
  Settings: () => <div data-testid="settings-icon" />,
  Business: () => <div data-testid="business-icon" />,
  AdminPanelSettings: () => <div data-testid="admin-panel-settings-icon" />,
  CloudSync: () => <div data-testid="cloud-sync-icon" />,
  Group: () => <div data-testid="group-icon" />,
  Assessment: () => <div data-testid="assessment-icon" />,
  ChevronLeft: () => <div data-testid="chevron-left-icon" />,
  ChevronRight: () => <div data-testid="chevron-right-icon" />,
  
  // Actions
  Close: () => <div data-testid="close-icon" />,
  Visibility: () => <div data-testid="visibility-icon" />,
  VisibilityOff: () => <div data-testid="visibility-off-icon" />,
  Add: () => <div data-testid="add-icon" />,
  Edit: () => <div data-testid="edit-icon" />,
  Delete: () => <div data-testid="delete-icon" />,
  Save: () => <div data-testid="save-icon" />,
  Cancel: () => <div data-testid="cancel-icon" />,
  Send: () => <div data-testid="send-icon" />,
  Search: () => <div data-testid="search-icon" />,
  FilterList: () => <div data-testid="filter-list-icon" />,
  Clear: () => <div data-testid="clear-icon" />,
  ViewModule: () => <div data-testid="view-module-icon" />,
  ViewList: () => <div data-testid="view-list-icon" />,
  
  // Status & Feedback
  TrendingUp: () => <div data-testid="trending-up-icon" />,
  TrendingDown: () => <div data-testid="trending-down-icon" />,
  Check: () => <div data-testid="check-icon" />,
  Done: () => <div data-testid="done-icon" />,
  DoneAll: () => <div data-testid="done-all-icon" />,
  ErrorOutline: () => <div data-testid="error-outline-icon" />,
  Warning: () => <div data-testid="warning-icon" />,
  Info: () => <div data-testid="info-icon" />,
  
  // Media
  PhotoCamera: () => <div data-testid="photo-camera-icon" />,
  AttachFile: () => <div data-testid="attach-file-icon" />,
  PlayCircleOutline: () => <div data-testid="play-circle-icon" />,
  PlayArrow: () => <div data-testid="play-arrow-icon" />,
  Pause: () => <div data-testid="pause-icon" />,
  Stop: () => <div data-testid="stop-icon" />,
  Mic: () => <div data-testid="mic-icon" />,
  VolumeUp: () => <div data-testid="volume-up-icon" />,
  VolumeOff: () => <div data-testid="volume-off-icon" />,
  
  // Communication
  Message: () => <div data-testid="message-icon" />,
  Email: () => <div data-testid="email-icon" />,
  Phone: () => <div data-testid="phone-icon" />,
  Favorite: () => <div data-testid="favorite-icon" />,
  FavoriteBorder: () => <div data-testid="favorite-border-icon" />,
  Share: () => <div data-testid="share-icon" />,
  
  // File & Content
  ContentCopy: () => <div data-testid="content-copy-icon" />,
  ContentPaste: () => <div data-testid="content-paste-icon" />,
  Description: () => <div data-testid="description-icon" />,
  Folder: () => <div data-testid="folder-icon" />,
  FolderOpen: () => <div data-testid="folder-open-icon" />,
  
  // UI Controls
  ExpandMore: () => <div data-testid="expand-more-icon" />,
  ExpandLess: () => <div data-testid="expand-less-icon" />,
  MoreVert: () => <div data-testid="more-vert-icon" />,
  MoreHoriz: () => <div data-testid="more-horiz-icon" />,
  Menu: () => <div data-testid="menu-icon" />,
  
  // Location & Navigation
  Home: () => <div data-testid="home-icon" />,
  Language: () => <div data-testid="language-icon" />,
  DateRange: () => <div data-testid="date-range-icon" />,
  Schedule: () => <div data-testid="schedule-icon" />,
  
  // Misc
  Refresh: () => <div data-testid="refresh-icon" />,
  Calculate: () => <div data-testid="calculate-icon" />,
  Download: () => <div data-testid="download-icon" />,
  Upload: () => <div data-testid="upload-icon" />,
  Lock: () => <div data-testid="lock-icon" />,
  LockOpen: () => <div data-testid="lock-open-icon" />,
  
  // Financial
  MoneyOff: () => <div data-testid="money-off-icon" />,
  AccountBalance: () => <div data-testid="account-balance-icon" />,
  Receipt: () => <div data-testid="receipt-icon" />,
  
  // Default fallback for any unmocked icon
  default: (props: any) => {
    const iconName = props?.iconName || 'UnknownIcon';
    return <div data-testid={`${iconName.toLowerCase()}-icon`} />;
  }
};

// Export all icons
export default mockIcons;