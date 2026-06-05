/** Best-effort extraction of a human-readable message from an API error body. */
export function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object') {
    if ('detail' in error) return String(error.detail);
    if ('message' in error) return String(error.message);
  }
  return 'Unknown error';
}
