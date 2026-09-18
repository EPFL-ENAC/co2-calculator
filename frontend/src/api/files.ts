import { api } from '@/api/http';
import { downloadFrom } from '@/utils/download';

// Through the ky client so the auth/refresh hooks apply and a 401 or 404
// throws instead of ending as a failed entry in the browser's download shelf.
export function fetchFile(path: string): Promise<Blob> {
  return api.get(`files/${path}`).blob();
}

// Download a backend file under its own base name.
export function downloadFile(path: string): Promise<void> {
  return downloadFrom(
    () => fetchFile(path),
    path.slice(path.lastIndexOf('/') + 1),
  );
}
