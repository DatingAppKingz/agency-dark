import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TableSortLabel, Box } from '@mui/material';
import { visuallyHidden } from '@mui/utils';
import { AriaAnnouncer } from '@/utils/accessibility';

interface Column {
  id: string;
  label: string;
  numeric?: boolean;
  sortable?: boolean;
}

interface AccessibleTableProps {
  columns: Column[];
  rows: any[];
  orderBy?: string;
  order?: 'asc' | 'desc';
  onSort?: (property: string) => void;
  caption?: string;
  summary?: string;
  rowKeyField: string;
}

export const AccessibleTable = ({
  columns,
  rows,
  orderBy,
  order = 'asc',
  onSort,
  caption,
  summary,
  rowKeyField,
}: AccessibleTableProps) => {
  const announcer = AriaAnnouncer.getInstance();

  const handleSort = (property: string) => {
    if (onSort) {
      onSort(property);
      const column = columns.find(col => col.id === property);
      const newOrder = orderBy === property && order === 'asc' ? 'desc' : 'asc';
      announcer.announce(
        `Table sorted by ${column?.label} in ${newOrder === 'asc' ? 'ascending' : 'descending'} order`
      );
    }
  };

  return (
    <TableContainer>
      <Table aria-label={caption || 'Data table'}>
        {caption && (
          <caption>
            {caption}
            {summary && <Box component="span" sx={visuallyHidden}>{summary}</Box>}
          </caption>
        )}
        <TableHead>
          <TableRow>
            {columns.map((column) => (
              <TableCell
                key={column.id}
                align={column.numeric ? 'right' : 'left'}
                sortDirection={orderBy === column.id ? order : false}
              >
                {column.sortable ? (
                  <TableSortLabel
                    active={orderBy === column.id}
                    direction={orderBy === column.id ? order : 'asc'}
                    onClick={() => handleSort(column.id)}
                  >
                    {column.label}
                    {orderBy === column.id ? (
                      <Box component="span" sx={visuallyHidden}>
                        {order === 'desc' ? 'sorted descending' : 'sorted ascending'}
                      </Box>
                    ) : null}
                  </TableSortLabel>
                ) : (
                  column.label
                )}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => (
            <TableRow
              key={row[rowKeyField]}
              hover
              tabIndex={-1}
              sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
            >
              {columns.map((column) => (
                <TableCell
                  key={column.id}
                  align={column.numeric ? 'right' : 'left'}
                  component={column.id === rowKeyField ? 'th' : 'td'}
                  scope={column.id === rowKeyField ? 'row' : undefined}
                >
                  {row[column.id]}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
};
