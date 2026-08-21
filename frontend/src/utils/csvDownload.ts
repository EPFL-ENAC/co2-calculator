const UTF8_BOM = '\ufeff';

export const escapeCsvValue = (v: unknown) => {
  const s = String(v ?? '');
  return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export const downloadCsv = (csv: string, filename: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(
    new Blob([UTF8_BOM + csv], { type: 'text/csv;charset=utf-8' }),
  );
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};
