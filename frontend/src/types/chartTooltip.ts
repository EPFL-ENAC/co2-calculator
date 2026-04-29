export type TooltipRow = {
  label: string;
  value: string;
  color: string;
};

export type TooltipState = {
  title?: string;
  rows: TooltipRow[];
  separatorRow?: TooltipRow;
  footer?: string;
  tone?: 'default' | 'muted';
} | null;

