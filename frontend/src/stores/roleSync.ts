/**
 * Role Sync Store - SSE connection for real-time role updates
 *
 * Features:
 * - Maintains SSE connection to /api/v1/roles/stream
 * - Auto-reconnects on connection loss
 * - Updates auth store on role changes
 * - Implements TTL-based fallback (re-fetch /me every 15 minutes)
 */

import { defineStore } from 'pinia';
import { ref, onUnmounted } from 'vue';
import { useAuthStore } from './auth';

interface RoleUpdatePayload {
  type: 'user_roles_updated' | 'ping';
  payload?: {
    user_id: number;
    roles: Array<{
      role: string;
      on: { unit?: string; affiliation?: string } | 'global';
    }>;
    timestamp: string;
  };
}

export const useRoleSyncStore = defineStore('roleSync', () => {
  const isConnected = ref(false);
  const lastEventTime = ref<Date | null>(null);
  const sse: Ref<EventSource | null> = ref(null);
  const reconnectAttempts = ref(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000; // 3 seconds

  const TTL_MS = 15 * 60 * 1000; // 15 minutes
  let ttlTimer: ReturnType<typeof setTimeout> | null = null;

  function startTTLTimer() {
    // Clear existing timer
    if (ttlTimer) {
      clearTimeout(ttlTimer);
    }

    // Set new timer to re-fetch /me
    ttlTimer = setTimeout(async () => {
      console.log('[RoleSync] TTL expired, re-fetching /me');
      const authStore = useAuthStore();
      await authStore.getUser();
      startTTLTimer(); // Restart timer
    }, TTL_MS);
  }

  function connect() {
    if (sse.value) {
      sse.value.close();
    }

    try {
      sse.value = new EventSource('/api/v1/roles/stream');

      sse.value.onopen = () => {
        console.log('[RoleSync] SSE connection established');
        isConnected.value = true;
        reconnectAttempts.value = 0;
        startTTLTimer();
      };

      sse.value.onmessage = (event: MessageEvent) => {
        try {
          const data: RoleUpdatePayload = JSON.parse(event.data);

          if (data.type === 'ping') {
            // Keep-alive ping, ignore
            return;
          }

          if (data.type === 'user_roles_updated' && data.payload) {
            console.log('[RoleSync] Role update received', data.payload);
            lastEventTime.value = new Date();

            // Update auth store
            const authStore = useAuthStore();
            if (authStore.user) {
              authStore.user.roles_raw = data.payload.roles;
              // Re-calculate permissions (placeholder - actual implementation needed)
              // authStore.user.permissions = calculatePermissions(data.payload.roles);
            }
          }
        } catch (err) {
          console.error('[RoleSync] Error parsing SSE message:', err);
        }
      };

      sse.value.onerror = () => {
        console.log('[RoleSync] SSE connection error');
        isConnected.value = false;

        // Attempt reconnection
        if (reconnectAttempts.value < maxReconnectAttempts) {
          reconnectAttempts.value++;
          console.log(
            `[RoleSync] Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttempts.value}/${maxReconnectAttempts})`,
          );
          setTimeout(connect, reconnectDelay);
        } else {
          console.warn(
            '[RoleSync] Max reconnection attempts reached, using TTL fallback',
          );
          // Fallback: rely on TTL-based /me re-fetch
          startTTLTimer();
        }
      };
    } catch (err) {
      console.error('[RoleSync] Failed to establish SSE connection:', err);
      isConnected.value = false;
    }
  }

  function disconnect() {
    if (sse.value) {
      sse.value.close();
      sse.value = null;
    }
    if (ttlTimer) {
      clearTimeout(ttlTimer);
      ttlTimer = null;
    }
    isConnected.value = false;
  }

  // Auto-connect on store initialization
  connect();

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect();
  });

  return {
    isConnected,
    lastEventTime,
    connect,
    disconnect,
  };
});
