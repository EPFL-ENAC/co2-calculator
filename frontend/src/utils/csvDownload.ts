const UTF8_BOM = '\ufeff';

export const escapeCsvValue = (v: unknown) => {
  const s = String(v ?? '');
  return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

// The one way to hand a file to the user. Callers fetch the Blob first, so
// the request shows in DevTools and a failure throws instead of ending as a
// silent failed entry in the browser's download shelf. Object URLs honor
// `a.download` in every browser, including Safari.
export const downloadBlob = (blob: Blob, filename: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const downloadCsv = (csv: string, filename: string) =>
  downloadBlob(
    new Blob([UTF8_BOM + csv], { type: 'text/csv;charset=utf-8' }),
    filename,
  );
