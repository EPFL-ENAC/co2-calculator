import { Notify } from 'quasar';
import { i18n } from '@/boot/i18n';

const UTF8_BOM = '\ufeff';

export const escapeCsvValue = (v: unknown) => {
  const s = String(v ?? '');
  return /[,"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

// The one way to hand a file to the user. Callers load the Blob first, so
// the request shows in DevTools and a failure throws instead of ending as a
// silent failed entry in the browser's download shelf. Object URLs honor
// `a.download` in every browser, including Safari.
export const downloadBlob = (blob: Blob, filename: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  // ponytail: 40 s like FileSaver; Firefox can abort a large download when
  // the object URL is revoked before its download manager reads the blob.
  setTimeout(() => URL.revokeObjectURL(a.href), 40_000);
};

// Load a Blob and hand it to the user. A failure toasts, then rethrows so
// Sentry sees it: the one place a download error becomes visible.
export async function downloadFrom(
  load: () => Promise<Blob>,
  filename: string,
): Promise<void> {
  try {
    downloadBlob(await load(), filename);
  } catch (e: unknown) {
    Notify.create({
      color: 'negative',
      message: i18n.global.t('common_download_failed', { filename }),
      position: 'top',
    });
    throw e;
  }
}

export const downloadCsv = (csv: string, filename: string) =>
  downloadBlob(
    new Blob([UTF8_BOM + csv], { type: 'text/csv;charset=utf-8' }),
    filename,
  );
