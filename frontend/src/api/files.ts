import { api } from '@/api/http';

// Through the ky client so the auth/refresh hooks apply and a 401 or 404
// throws instead of ending as a failed entry in the browser's download shelf.
export function fetchFile(path: string): Promise<Blob> {
  return api.get(`files/${path}`).blob();
}
