import { Box, Typography, Button, SvgIcon } from '@mui/material';
import {
  Inbox,
  SearchOff,
  CloudOff,
  FolderOff,
  ReceiptLong,
  ChatBubbleOutline,
  GroupOff,
  AssignmentLateOutlined,
} from '@mui/icons-material';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
}

const EmptyStateBase = ({ icon, title, description, action, secondaryAction }: EmptyStateProps) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        py: 8,
        px: 3,
        maxWidth: 400,
        mx: 'auto',
      }}
    >
      {icon && (
        <Box sx={{ color: 'text.disabled', mb: 3 }}>
          {icon}
        </Box>
      )}
      
      <Typography variant="h6" gutterBottom color="text.primary">
        {title}
      </Typography>
      
      {description && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          {description}
        </Typography>
      )}
      
      {(action || secondaryAction) && (
        <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
          {action && (
            <Button variant="contained" onClick={action.onClick}>
              {action.label}
            </Button>
          )}
          {secondaryAction && (
            <Button variant="outlined" onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </Button>
          )}
        </Box>
      )}
    </Box>
  );
};

// Specific empty states
export const NoDataEmpty = (props: Omit<EmptyStateProps, 'icon'>) => (
  <EmptyStateBase
    icon={<Inbox sx={{ fontSize: 64 }} />}
    {...props}
  />
);

export const NoSearchResultsEmpty = (props: Omit<EmptyStateProps, 'icon' | 'title'>) => (
  <EmptyStateBase
    icon={<SearchOff sx={{ fontSize: 64 }} />}
    title="No results found"
    description="Try adjusting your search or filters to find what you're looking for"
    {...props}
  />
);

export const NoConnectionEmpty = (props: Omit<EmptyStateProps, 'icon' | 'title'>) => (
  <EmptyStateBase
    icon={<CloudOff sx={{ fontSize: 64 }} />}
    title="No internet connection"
    description="Please check your internet connection and try again"
    {...props}
  />
);

export const NoFilesEmpty = (props: Omit<EmptyStateProps, 'icon' | 'title'>) => (
  <EmptyStateBase
    icon={<FolderOff sx={{ fontSize: 64 }} />}
    title="No files yet"
    description="Upload your first file to get started"
    {...props}
  />
);

export const NoTransactionsEmpty = (props: Omit<EmptyStateProps, 'icon' | 'title'>) => (
  <EmptyStateBase
    icon={<ReceiptLong sx={{ fontSize: 64 }} />}
    title="No transactions"
    description="Your transaction history will appear here"
    {...props}
  />
);

export const NoMessagesEmpty = (props: Omit<EmptyStateProps, 'icon' | 'title'>) => (
  <EmptyStateBase
    icon={<ChatBubbleOutline sx={{ fontSize: 64 }} />}
    title="No messages yet"
    description="Start a conversation to see messages here"
    {...props}
  />
);

export const NoUsersEmpty = (props: Omit<EmptyStateProps, 'icon' | 'title'>) => (
  <EmptyStateBase
    icon={<GroupOff sx={{ fontSize: 64 }} />}
    title="No users found"
    description="Add users to your team to see them here"
    {...props}
  />
);

export const NoTasksEmpty = (props: Omit<EmptyStateProps, 'icon' | 'title'>) => (
  <EmptyStateBase
    icon={<AssignmentLateOutlined sx={{ fontSize: 64 }} />}
    title="All caught up!"
    description="You have no pending tasks at the moment"
    {...props}
  />
);

// Custom empty state with illustration
export const CustomEmpty = ({
  illustration,
  ...props
}: EmptyStateProps & { illustration?: string }) => {
  return (
    <EmptyStateBase
      icon={
        illustration ? (
          <Box
            component="img"
            src={illustration}
            alt="Empty state"
            sx={{ width: 200, height: 150, objectFit: 'contain' }}
          />
        ) : undefined
      }
      {...props}
    />
  );
};