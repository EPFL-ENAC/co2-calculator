export type TooltipRow = {
  label: string;
  value: string;
  color?: string;
  /** Optional module icon name (uses existing `ModuleIcon` system). */
  icon?: string;
  /** A section header (e.g. one bar's label and total) above its rows. */
  heading?: boolean;
};

export type TooltipState = {
  title?: string;
  rows: TooltipRow[];
  separatorRow?: TooltipRow;
  footer?: string;
  tone?: 'default' | 'muted';
} | null;
