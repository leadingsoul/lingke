import request from './request';

/* ====== Auth APIs ====== */
export const authApi = {
  login: (username: string, password: string) =>
    request.post('/auth/login', { username, password, user_type: 'cs_staff' }),

  me: () => request.get('/auth/me'),

  refreshToken: (token: string) =>
    request.post('/auth/refresh', { token }),

  logout: () => request.post('/auth/logout'),
};

/* ====== Conversation APIs ====== */
export const conversationApi = {
  list: (params?: Record<string, unknown>) =>
    request.get('/cs/conversations', { params }),

  detail: (id: string) =>
    request.get(`/cs/conversations/${id}`),

  messages: (id: string, params?: Record<string, unknown>) =>
    request.get(`/cs/conversations/${id}/messages`, { params }),

  reply: (id: string, content: string) =>
    request.post(`/cs/conversations/${id}/reply`, { content }),

  close: (id: string) =>
    request.post(`/cs/conversations/${id}/close`),

  delete: (id: string) =>
    request.delete(`/cs/conversations/${id}`),
};

/* ====== Ticket APIs ====== */
export const ticketApi = {
  list: (params?: Record<string, unknown>) =>
    request.get('/cs/tickets', { params }),

  detail: (id: string) =>
    request.get(`/cs/tickets/${id}`),

  review: (id: string, data: { result: string; opinion?: string }) =>
    request.post(`/cs/tickets/${id}/review`, data),

  supplement: (id: string, note: string) =>
    request.post(`/cs/tickets/${id}/supplement`, { note }),

  complete: (id: string) =>
    request.post(`/cs/tickets/${id}/complete`),

  addTag: (id: string, tag: string) =>
    request.post(`/cs/tickets/${id}/tags`, { tag }),

  removeTag: (id: string, tag: string) =>
    request.delete(`/cs/tickets/${id}/tags`, { data: { tag } }),
};

/* ====== Dashboard APIs ====== */
export const dashboardApi = {
  getCSDashboard: () => request.get('/cs/dashboard'),
};

/* ====== Knowledge APIs ====== */
export const knowledgeApi = {
  list: (params?: Record<string, unknown>) =>
    request.get('/cs/knowledge', { params }),
};

/* ====== Stats APIs ====== */
export const statsApi = {
  categoryStats: () => request.get('/cs/stats/category'),
  myPerformance: () => request.get('/cs/performance'),
};

/* ====== Records APIs ====== */
export const recordsApi = {
  list: (params?: Record<string, unknown>) =>
    request.get('/cs/records', { params }),
};
