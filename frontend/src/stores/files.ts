import { defineStore } from 'pinia';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref } from 'vue';
import { api } from 'src/api/http';

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
