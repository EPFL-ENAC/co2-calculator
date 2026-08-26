import { defineStore } from 'pinia';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref } from 'vue';
import { api, SLOW_REQUEST_TIMEOUT_MS } from '@/api/http';

export interface FileObject extends Blob {
  readonly size: number;
  readonly name: string;
  readonly path: string;
  readonly type: string;
}

export interface FileNode {
  name: string;
  path: string;
  size: number;
  mime_type: string;
  alt_name?: string;
  alt_path?: string;
  alt_size?: number;
  alt_mime_type?: string;
  children?: FileNode[];
}

export const useFilesStore = defineStore(
  'files',
  () => {
    const tempFiles = ref<FileNode[]>([]);

    /**
     * Upload temporary files to the backend.
     * @param files The files to upload.
     * @returns The uploaded FileNode array with paths
     */
    async function uploadTempFiles(files: FileObject[]): Promise<FileNode[]> {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append('files', file, file.name);
      });

      const response = await api.post<FileNode[]>('files/temp-upload', {
        body: formData,
        // Wall time here is dominated by the *client's* upload bandwidth, not
        // by the server: a large CSV on a slow link exceeds ky's 10 s default
        // while everything is working correctly. The server's own per-file cap
        // (FILES_MAX_SIZE_MB, #2261) is what actually bounds this.
        timeout: SLOW_REQUEST_TIMEOUT_MS,
      });
      const nodes = await response.json();
      tempFiles.value.push(...nodes);
      return nodes;
    }

    return {
      tempFiles,
      uploadTempFiles,
    };
  },
  {
    persist: {
      key: 'filesLocalStorage',
      pick: ['tempFiles'],
      storage: localStorage,
    } as PersistenceOptions,
  },
);
