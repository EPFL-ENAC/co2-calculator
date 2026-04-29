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

function renderRow(row: TooltipRow): string {
  let html = '<div class="chart-tooltip__row row items-center">';
  if (row.color) {
    html += `<span class="chart-tooltip__dot" style="--dot-color:${row.color}"></span>`;
  }
  html += `<span class="chart-tooltip__label col">${row.label}</span>`;
  html += `<span class="chart-tooltip__value text-weight-medium">${row.value}</span>`;
  html += '</div>';
  return html;
}

export function renderTooltipHtml(state: TooltipState): string {
  if (!state) return '';
  const { title, rows, separatorRow, footer, tone } = state;

  let html = '<div class="chart-tooltip">';

  if (title) {
    html += `<p class="chart-tooltip__title">${title}</p>`;
  }

  for (const row of rows) {
    html += renderRow(row);
  }

  if (separatorRow) {
    html +=
      '<div class="chart-tooltip__row chart-tooltip__row--separator row items-center">';
    if (separatorRow.color) {
      html += `<span class="chart-tooltip__dot" style="--dot-color:${separatorRow.color}"></span>`;
    }
    html += `<span class="chart-tooltip__label col">${separatorRow.label}</span>`;
    html += `<span class="chart-tooltip__value text-weight-medium">${separatorRow.value}</span>`;
    html += '</div>';
  }

  if (footer) {
    const footerClass =
      tone === 'muted'
        ? 'chart-tooltip__footer chart-tooltip__footer--muted'
        : 'chart-tooltip__footer';
    html += `<p class="${footerClass}">${footer}</p>`;
  }

  html += '</div>';
  return html;
}
