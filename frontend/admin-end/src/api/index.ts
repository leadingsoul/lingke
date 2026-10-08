import request from './request';

// ==================== Types ====================

export interface LoginParams {
  username: string;
  password: string;
}

export interface LoginResult {
  token: string;
  user: AdminUser;
}

export interface AdminUser {
  id: number;
  username: string;
  name: string;
  role: string;
  status: string;
}

export interface DashboardStats {
  total_users: number;
  total_consultations: number;
  total_tickets: number;
  total_evaluations: number;
  pending_tickets: number;
  negative_sentiment_rate: number;
  online_agents: number;
  consultation_trend: Array<{ date: string; count: number }>;
  ticket_trend: Array<{ date: string; count: number }>;
  sentiment_trend: Array<{ date: string; positive: number; neutral: number; negative: number }>;
}

export interface KnowledgeItem {
  id: number;
  title: string;
  type: string;
  tags: string[];
  content: string;
  status: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeListParams {
  page?: number;
  page_size?: number;
  type?: string;
  tag?: string;
  keyword?: string;
}

export interface KnowledgeListResult {
  items: KnowledgeItem[];
  total: number;
}

export interface KnowledgeCreateParams {
  title: string;
  type: string;
  tags: string[];
  content: string;
  status: string;
}

export interface KnowledgeUpdateParams extends Partial<KnowledgeCreateParams> {
  id: number;
}

export interface StaffItem {
  id: number;
  username: string;
  name: string;
  role: string;
  status: string;
  phone: string;
  email: string;
  max_concurrent: number;
  today_handled: number;
  satisfaction_rate: number;
}

export interface StaffPerformance {
  daily_stats: Array<{ date: string; handled: number; satisfaction: number }>;
  total_handled: number;
  avg_satisfaction: number;
  avg_response_time: number;
}

export interface TicketItem {
  id: number;
  ticket_no: string;
  consumer_name: string;
  order_id: string;
  aso_type: string;
  aso_reason: string;
  aso_status: string;
  urgency: string;
  responsibility: string;
  assigned_to: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface EvolutionItem {
  id: number;
  title: string;
  type: string;
  status: string;
  content: string;
  review_status: string;
  synced_to_knowledge: boolean;
  created_at: string;
}

export interface ChartStats {
  satisfaction_stats: Array<{ rating: number; count: number }>;
  ticket_distribution: Array<{ type: string; count: number }>;
  agent_performance: Array<{ name: string; handled: number; satisfaction: number }>;
  hot_topics: Array<{ topic: string; count: number }>;
  product_ratings: Array<{ product_name: string; avg_rating: number; count: number }>;
  sentiment_trend: Array<{ date: string; positive: number; neutral: number; negative: number }>;
}

export interface AIInsightResult {
  markdown: string;
  generated_at: string;
}

export interface LogItem {
  id: string;
  staff_name: string;
  action: string;
  action_cn: string;
  target_type: string;
  target_type_cn: string;
  target_id: string;
  detail: string;
  created_at: string;
}

// ==================== Auth API ====================

export const authApi = {
  login: (params: LoginParams) =>
    request.post<any, LoginResult>('/auth/login', { ...params, user_type: 'admin' }),

  me: () => request.get<any, AdminUser>('/auth/me'),

  logout: () => request.post('/auth/logout'),
};

// ==================== Dashboard API ====================

export const dashboardApi = {
  getStats: () => request.get<any, DashboardStats>('/admin/dashboard'),
};

// ==================== Knowledge API ====================

export const knowledgeApi = {
  list: (params?: KnowledgeListParams) =>
    request.get<any, KnowledgeListResult>('/admin/knowledge', { params }),

  getById: (id: number) =>
    request.get<any, KnowledgeItem>(`/admin/knowledge/${id}`),

  create: (data: KnowledgeCreateParams) =>
    request.post<any, KnowledgeItem>('/admin/knowledge', data),

  update: (id: number, data: Partial<KnowledgeCreateParams>) =>
    request.put<any, KnowledgeItem>(`/admin/knowledge/${id}`, data),

  delete: (id: number) =>
    request.delete(`/admin/knowledge/${id}`),

  import: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request.post('/admin/knowledge/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ==================== Staff API ====================

export const staffApi = {
  list: (params?: { status?: string }) =>
    request.get<any, PaginatedResult<StaffItem>>('/admin/staff', { params }),

  create: (data: Partial<StaffItem> & { password?: string }) =>
    request.post<any, StaffItem>('/admin/staff', data),

  update: (id: number, data: Partial<StaffItem>) =>
    request.put<any, StaffItem>(`/admin/staff/${id}`, data),

  getPerformance: (id: number) =>
    request.get<any, StaffPerformance>(`/admin/staff/${id}/performance`),
};

// ==================== Ticket API ====================

export const ticketApi = {
  list: (params?: Record<string, unknown>) =>
    request.get<any, { items: TicketItem[]; total: number }>('/cs/tickets', { params }),

  batchAssign: (ticketIds: string[], staffId: string) =>
    request.post('/cs/tickets/batch-assign', { ticket_ids: ticketIds, staff_id: staffId }),
};

// ==================== Stats API ====================

export const statsApi = {
  getCharts: (params?: { start_date?: string; end_date?: string }) =>
    request.get<any, ChartStats>('/admin/stats/charts', { params }),

  export: (data: { type: string; format?: string; start_date?: string; end_date?: string }) =>
    request.post('/admin/stats/export', data, { responseType: 'blob' }),
};

// ==================== AI Insight API ====================

export const aiInsightApi = {
  get: (params?: { start_date?: string; end_date?: string }) =>
    request.get<any, AIInsightResult>('/admin/stats/ai-insight', { params }),
};

// ==================== Crawl API ====================

export const crawlApi = {
  trigger: (params?: { source?: string }) =>
    request.post('/admin/crawler/tasks', params),

  status: () =>
    request.get<any, { running: boolean; last_run: string }>('/admin/crawler/logs'),
};

// ==================== Summary API ====================

export const summaryApi = {
  list: (params?: { type?: string; status?: string }) =>
    request.get<any, PaginatedResult<EvolutionItem>>('/admin/summaries', { params }),

  getById: (id: number) =>
    request.get<any, EvolutionItem>(`/admin/summaries/${id}`),

  review: (id: number, status: string, comment?: string) =>
    request.post(`/admin/summaries/${id}/review`, { status, comment }),

  syncToKnowledge: (id: number) =>
    request.post(`/admin/summaries/${id}/sync-knowledge`),
};

// ==================== Log API ====================

export const logApi = {
  list: (params?: {
    page?: number;
    page_size?: number;
    action?: string;
    target_type?: string;
    start_date?: string;
    end_date?: string;
  }) =>
    request.get<any, { items: LogItem[]; total: number }>('/admin/logs', { params }),
};
