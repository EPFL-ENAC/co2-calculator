export type TooltipRow = {
  label: string;
  value: string;
  color?: string;
  /** Optional module icon name (uses existing `ModuleIcon` system). */
  icon?: string;
};

export type TooltipState = {
  title?: string;
  rows: TooltipRow[];
  separatorRow?: TooltipRow;
  footer?: string;
  tone?: 'default' | 'muted';
} | null;
