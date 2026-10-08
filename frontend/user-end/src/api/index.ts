import { get, post, put, del } from './request'
import type {
  UserInfo, Order, OrderDetail, ChatSession, ChatMessage,
  AftersaleTicket, Evaluation, PendingEval, Notice,
  PaginatedData
} from '@/types'

// ============ Auth ============
export const authApi = {
  /** 用户名密码登录 */
  login: (username: string, password: string) =>
    post<{ access_token: string; user: UserInfo }>('/auth/login', { username, password, user_type: 'consumer' }),

  /** 微信登录 */
  wechatLogin: (code: string) =>
    post<{ token: string; user: UserInfo }>('/auth/wechat-login', { code }),

  /** 刷新Token */
  refreshToken: (refreshToken: string) =>
    post<{ token: string }>('/auth/refresh', { refresh_token: refreshToken }),

  /** 登出 */
  logout: () =>
    post<void>('/auth/logout'),

  /** 获取当前用户信息 */
  me: () =>
    get<UserInfo>('/auth/me'),
}

// ============ Order ============
export const orderApi = {
  /** 订单列表 */
  list: (status?: string, keyword?: string, page = 1, pageSize = 10) =>
    get<PaginatedData<Order>>('/consumer/orders', { status, keyword, page, page_size: pageSize }),

  /** 订单详情 */
  detail: (orderId: string) =>
    get<OrderDetail>(`/consumer/orders/${orderId}`),
}

// ============ Chat ============
export const chatApi = {
  /** 创建新会话（进页面即创建） */
  createConversation: (orderId?: string) =>
    post<{ session_id: string; is_existing?: boolean }>('/consumer/chat/conversations', { order_id: orderId }),

  /** 发送消息（AI 生成回复可能需 30s+，单独设置 60s 超时） */
  sendMessage: (sessionId: string | undefined, content: string, orderId?: string, imageUrls?: string[]) =>
    post<{
      message_id: string
      session_id: string
      ai_reply?: string
      suggestions?: string[]
      intent?: string
      is_transferred?: boolean
    }>('/consumer/chat/send', {
      session_id: sessionId, order_id: orderId, content, image_urls: imageUrls || [],
    }, { timeout: 60000 }),

  /** 获取历史消息 */
  getHistory: (sessionId: string, page = 1, pageSize = 20) =>
    get<PaginatedData<ChatMessage>>(`/consumer/chat/history/${sessionId}`, { page, page_size: pageSize }),

  /** 获取会话列表 */
  getSessions: (page = 1, pageSize = 10) =>
    get<PaginatedData<ChatSession>>('/consumer/chat/conversations', { page, page_size: pageSize }),

  /** 删除会话 */
  deleteSession: (sessionId: string) =>
    del<void>(`/consumer/chat/conversations/${sessionId}`),

  /** 对已关闭会话进行满意度评分 */
  rateConversation: (sessionId: string, rating: number, feedback?: string) =>
    post<{ message: string; rating: number }>(`/consumer/chat/conversations/${sessionId}/rate`, { rating, feedback }),

  /** 上传聊天文件（图片/视频/文档），返回 URL */
  uploadFile: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return post<{ url: string; file_name: string; file_type: string; file_size: number; extension: string }>(
      '/consumer/chat/upload', formData,
    )
  },

  /** 转接人工 */
  transferToHuman: (sessionId: string) =>
    post<{ message: string }>('/consumer/chat/transfer', { session_id: sessionId }),
}

// ============ Aftersale ============
export const aftersaleApi = {
  /** 创建售后工单 */
  apply: (data: {
    order_id: string
    aso_type: string
    aso_reason: string
    description: string
    evidence_urls: string[]
  }) => post<AftersaleTicket>('/consumer/aftersale', data),

  /** 售后工单列表 */
  list: (status?: string, page = 1, pageSize = 10) =>
    get<PaginatedData<AftersaleTicket>>('/consumer/aftersale', { aso_status: status, page, page_size: pageSize }),

  /** 售后工单详情 */
  detail: (ticketId: string) =>
    get<AftersaleTicket>(`/consumer/aftersale/${ticketId}`),

  /** 撤销售后工单 */
  cancel: (ticketId: string) =>
    del<void>(`/consumer/aftersale/${ticketId}`),
}

// ============ Evaluate ============
export const evaluateApi = {
  /** 提交评价 */
  submit: (data: {
    order_id: string
    product_rating: number
    service_rating: number
    logistics_rating: number
    content?: string
    image_urls?: string[]
    is_anonymous?: boolean
  }) => post<Evaluation>('/consumer/evaluation', data),

  /** 待评价订单列表 */
  pendingList: (page = 1, pageSize = 10) =>
    get<PaginatedData<PendingEval>>('/consumer/evaluation/pending', { page, page_size: pageSize }),

  /** 我的评价列表 */
  myList: (page = 1, pageSize = 10) =>
    get<PaginatedData<Evaluation>>('/consumer/evaluation', { page, page_size: pageSize }),

  /** 追评 */
  append: (evaluationId: string, content: string, imageUrls?: string[]) =>
    post<void>(`/consumer/evaluation/${evaluationId}/reply`, { content, image_urls: imageUrls || [] }),

  /** 修改评价（7 天内） */
  update: (evaluationId: string, productRating: number, serviceRating: number, logisticsRating: number, content?: string) =>
    put<void>(`/consumer/evaluation/${evaluationId}`, {
      product_rating: productRating,
      service_rating: serviceRating,
      logistics_rating: logisticsRating,
      content: content || '',
    }),
}

// ============ Profile ============
export const userApi = {
  /** 获取个人资料 */
  getProfile: () =>
    get<UserInfo>('/consumer/profile'),

  /** 更新个人资料 */
  updateProfile: (data: { nickname?: string; avatar?: string }) =>
    put<UserInfo>('/consumer/profile', data),

  /** 绑定手机号 */
  bindPhone: (phone: string, smsCode: string) =>
    post<void>('/consumer/bind-phone', { phone, sms_code: smsCode }),

  /** 关联平台账号 */
  linkPlatform: (platform: string, account: string) =>
    post<void>('/consumer/link-platform', { platform, account }),
}

// ============ Feedback ============
export const feedbackApi = {
  /** 提交反馈 */
  submit: (content: string, type: string = '建议') =>
    post<void>('/consumer/feedback', { content, type }),
}

// ============ Notice (通过 notification API) ============
export const noticeApi = {
  /** 通知列表 */
  list: (page = 1, pageSize = 10) =>
    get<PaginatedData<Notice>>('/consumer/notifications', { page, page_size: pageSize }),

  /** 未读通知数 */
  unreadCount: () =>
    get<{ count: number }>('/consumer/notifications/unread-count'),

  /** 标记已读 */
  markAsRead: (id: string) =>
    put<void>(`/consumer/notifications/${id}/read`),

  /** 全部已读 */
  markAllRead: () =>
    put<void>('/consumer/notifications/read-all'),
}
