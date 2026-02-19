const envBackend = (import.meta.env.VITE_BACKEND_URL as string | undefined)?.trim()
export const backend = envBackend || window.location.origin
