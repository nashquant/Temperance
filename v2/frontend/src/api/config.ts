export const API_CONFIG = {
  basePath: '/api/v1',
  endpoints: {
    login: '/auth/login',
    me: '/auth/me',
    owners: '/auth/owners',
    weekOutlook: '/week-outlook',
  },
} as const;

// TODO: If your backend path changes (e.g., /v1 or another gateway prefix), update API_CONFIG.basePath.
// TODO: If auth token type changes from Bearer token, update header logic in src/api/http-client.ts.
