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
     * List files and directories at a given path (backend admin only).
     * @param path The path to list files from.
     */
    async function listFiles(path: string): Promise<FileNode[]> {
      const response = await api.get<FileNode[]>(
        `files/list/${encodeURIComponent(path)}`,
      );
      return await response.json();
    }

    /**
     * List all temporary files stored in the backend (backend admin only).
     */
    async function listTempFiles(): Promise<FileNode[]> {
      const response = await api.get<FileNode[]>('files/tmp');
      const nodes = await response.json();
      return nodes;
    }

    /**
     * Upload temporary files to the backend.
     * @param files The files to upload.
     */
    async function uploadTempFiles(files: FileObject[]) {
      const formData = new FormData();
      files.forEach((file) => {
        formData.append('files', file, file.name);
      });

      const response = await api.post<FileNode[]>('files/tmp', {
        body: formData,
      });
      const nodes = await response.json();
      tempFiles.value.push(...nodes);
    }

    /**
     * Clear all the references to the temporary files, does not delete them from the backend,
     * use this only after the temporary files have been processed and are no longer needed.
     */
    function clearTempFiles(paths: string[] = []) {
      if (paths.length > 0) {
        tempFiles.value = tempFiles.value.filter(
          (file) => !paths.includes(file.path),
        );
        return;
      }
      tempFiles.value = [];
    }

    /**
     * Delete a temporary file from the backend and remove its reference from the store.
     * @param path The path of the temporary file to delete.
     */
    async function deleteTempFile(path: string) {
      const tempFile = tempFiles.value.find((file) => file.path === path);
      if (tempFile) {
        // file.path is already URI encoded
        await api.delete(`files/${tempFile.path}`);
        const index = tempFiles.value.indexOf(tempFile);
        tempFiles.value.splice(index, 1);
      }
    }

    /**
     * Delete all temporary files from the backend and clear their references from the store.
     */
    async function deleteTempFiles() {
      if (tempFiles.value.length === 0) return;
      // make a copy of the array to avoid mutation issues during iteration
      const tempFilesCopy = [...tempFiles.value];
      for (const file of tempFilesCopy) {
        try {
          // file.path is already URI encoded
          await deleteTempFile(file.path);
        } catch (error) {
          console.error('Error deleting temporary file:', error);
        }
      }
    }

    /**
     * Download a file from the backend (backend admin only).
     * @param path The path of the file to download.
     */
    async function downloadFile(path: string): Promise<Blob> {
      const response = await api.get(`files/${encodeURIComponent(path)}`);
      return await response.blob();
    }

    return {
      tempFiles,
      listFiles,
      listTempFiles,
      uploadTempFiles,
      clearTempFiles,
      deleteTempFile,
      deleteTempFiles,
      downloadFile,
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
