import { HTTPError } from 'ky';
import { QNotifyCreateOptions } from 'quasar';

/**
 * Permission error details extracted from a 403 response.
 */
export interface PermissionErrorDetails {
  /** The full error message from the backend */
  message: string;
  /** The permission path (e.g., 'modules.headcount') if extractable */
  path?: string;
  /** The permission action (e.g., 'view', 'edit') if extractable */
  action?: string;
  /** The reason for denial if available */
  reason?: string;
}

/**
 * Parse permission error details from a 403 HTTP response.
 *
 * Extracts permission information from ky HTTPError responses.
 * The backend returns errors in the format:
 * {
 *   "detail": "Permission denied: {reason}"
 * }
 *
 * This function attempts to parse the error from the error message.
 * For more accurate parsing of the JSON response body, use parsePermissionErrorAsync.
 *
 * @param error - The error object (typically a ky HTTPError)
 * @returns Permission error details, or null if not a permission error
 *
 * @example
 * ```typescript
 * try {
 *   await api.post('some-endpoint');
 * } catch (error) {
 *   const details = parsePermissionError(error);
 *   if (details) {
 *     console.log('Permission denied:', details.message);
 *     console.log('Required permission:', details.path, details.action);
 *   }
 * }
 * ```
 */
export function parsePermissionError(
  error: unknown,
): PermissionErrorDetails | null {
  // Check if it's a ky HTTPError with status 403
  if (!(error instanceof HTTPError)) {
    return null;
  }

  if (error.response.status !== 403) {
    return null;
  }

  // Try to extract the error detail from the response body
  let detail = 'Permission denied';
  let path: string | undefined;
  let action: string | undefined;
  let reason: string | undefined;

  try {
    // Parse from error message (ky includes response details in the message)
    const errorMessage = error.message || 'Permission denied';

    // Try to parse common error message patterns
    // Pattern: "Permission denied: {reason}"
    // Pattern: "Permission denied: {path}.{action} required"
    const permissionDeniedMatch = errorMessage.match(
      /Permission denied:\s*(.+)/i,
    );
    if (permissionDeniedMatch) {
      const reasonText = permissionDeniedMatch[1].trim();

      // Try to extract path and action from patterns like:
      // "modules.headcount.edit required"
      // "modules.headcount.view required"
      const pathActionMatch = reasonText.match(
        /^([a-z0-9_.]+)\.([a-z]+)\s+required$/i,
      );
      if (pathActionMatch) {
        path = pathActionMatch[1];
        action = pathActionMatch[2];
        reason = reasonText;
      } else {
        reason = reasonText;
      }

      detail = `Permission denied: ${reasonText}`;
    } else {
      // Fallback: use the error message as-is
      detail = errorMessage;
    }
  } catch (parseError) {
    // If parsing fails, use default message
    console.warn('Failed to parse permission error:', parseError);
    detail = 'Permission denied';
  }

  return {
    message: detail,
    path,
    action,
    reason,
  };
}

/**
 * Async version that parses permission error details from the JSON response body.
 *
 * This version properly parses the JSON response body for more accurate error details.
 * Use this when you need the exact error message from the backend.
 *
 * @param error - The error object (typically a ky HTTPError)
 * @returns Promise resolving to permission error details, or null if not a permission error
 *
 * @example
 * ```typescript
 * try {
 *   await api.post('some-endpoint');
 * } catch (error) {
 *   const details = await parsePermissionErrorAsync(error);
 *   if (details) {
 *     console.log('Permission denied:', details.message);
 *   }
 * }
 * ```
 */
export async function parsePermissionErrorAsync(
  error: unknown,
): Promise<PermissionErrorDetails | null> {
  // Check if it's a ky HTTPError with status 403
  if (!(error instanceof HTTPError)) {
    return null;
  }

  if (error.response.status !== 403) {
    return null;
  }

  let detail = 'Permission denied';
  let path: string | undefined;
  let action: string | undefined;
  let reason: string | undefined;

  try {
    // Try to parse the JSON response body
    let responseBody: { detail?: string } | null = null;

    if (!error.response.bodyUsed) {
      try {
        responseBody = (await error.response.json()) as { detail?: string };
      } catch (jsonError) {
        // Response might not be JSON or already consumed
        console.warn('Failed to parse error response as JSON:', jsonError);
      }
    }

    // Extract detail from response body or fall back to error message
    const errorDetail =
      responseBody?.detail || error.message || 'Permission denied';

    // Try to parse common error message patterns
    const permissionDeniedMatch = errorDetail.match(
      /Permission denied:\s*(.+)/i,
    );
    if (permissionDeniedMatch) {
      const reasonText = permissionDeniedMatch[1].trim();

      // Try to extract path and action
      const pathActionMatch = reasonText.match(
        /^([a-z0-9_.]+)\.([a-z]+)\s+required$/i,
      );
      if (pathActionMatch) {
        path = pathActionMatch[1];
        action = pathActionMatch[2];
        reason = reasonText;
      } else {
        reason = reasonText;
      }

      detail = `Permission denied: ${reasonText}`;
    } else {
      detail = errorDetail;
    }
  } catch (parseError) {
    // If parsing fails, use default message
    console.warn('Failed to parse permission error:', parseError);
    detail = 'Permission denied';
  }

  return {
    message: detail,
    path,
    action,
    reason,
  };
}

/**
 * Display a user-friendly permission error toast notification.
 *
 * Parses the error and shows a toast notification using Quasar's notify system.
 * The notification will be styled as a warning/error and positioned at the top.
 *
 * @param error - The error object (typically a ky HTTPError)
 * @param $q - The Quasar instance from useQuasar() composable
 * @param options - Optional additional Quasar notify options to override defaults
 *
 * @example
 * ```typescript
 * import { useQuasar } from 'quasar';
 * import { showPermissionError } from 'src/utils/errors';
 *
 * const $q = useQuasar();
 *
 * try {
 *   await api.post('some-endpoint');
 * } catch (error) {
 *   showPermissionError(error, $q);
 * }
 * ```
 */
export function showPermissionError(
  error: unknown,
  $q: { notify: (opts: QNotifyCreateOptions) => void },
  options?: Partial<QNotifyCreateOptions>,
): void {
  const details = parsePermissionError(error);

  if (!details) {
    // Not a permission error, show generic error
    $q.notify({
      color: 'negative',
      message: error instanceof Error ? error.message : 'An error occurred',
      position: 'top',
      ...options,
    });
    return;
  }

  // Build user-friendly message
  let message = details.message;

  // If we have path and action, make it more user-friendly
  if (details.path && details.action) {
    // Convert snake_case to Title Case for display
    const pathDisplay = details.path
      .split('.')
      .map((part) =>
        part
          .split('_')
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' '),
      )
      .join(' > ');

    const actionDisplay =
      details.action.charAt(0).toUpperCase() + details.action.slice(1);

    message = `Permission denied: ${actionDisplay} access required for ${pathDisplay}`;
  }

  $q.notify({
    color: 'negative',
    message,
    position: 'top',
    timeout: 5000,
    actions: [{ icon: 'close', color: 'white' }],
    ...options,
  });
}
