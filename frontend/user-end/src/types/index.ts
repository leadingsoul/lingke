/** 用户信息 */
export interface UserInfo {
  id: string
  openid: string
  nickname: string
  avatar: string
  phone: string
  platform_account: string
  role: string
  status: number
  created_at: string
  updated_at: string
}

/** 订单 */
export interface Order {
  id: string
  order_sn: string
  status: string
  total_amount: number
  product_name: string
  product_image: string
  created_at: string
  finished_at?: string
}

/** 订单详情 */
export interface OrderDetail extends Order {
  product_spec: string
  quantity: number
  logistics_info?: LogisticsInfo
  items?: OrderItem[]
}

export interface OrderItem {
  product_id: string
  product_name: string
  product_image: string
  price: number
  quantity: number
}

/** 物流信息 */
export interface LogisticsInfo {
  company: string
  tracking_no: string
  status: string
  traces: LogisticsTrace[]
}

export interface LogisticsTrace {
  time: string
  status: string
  description: string
}

/** 会话 */
export interface ChatSession {
  id: string
  consumer_id: string
  staff_id?: string
  order_id?: string
  product_name?: string
  status: string
  intent?: string
  confidence?: number
  level?: string
  last_message?: string
  last_message_time?: string
  created_at: string
  updated_at?: string
  updated_at: string
}

/** 聊天消息 */
export interface ChatMessage {
  id: string
  conversation_id: string
  sender_type: 'consumer' | 'ai' | 'staff'
  content: string
  image_urls?: string[]
  ai_metadata?: Record<string, any>
  created_at: string
}

/** 意图识别结果 */
export interface IntentResult {
  intent: string
  confidence: number
  level: string
}

/** 售后工单 */
export interface AftersaleTicket {
  id: string
  order_id: string
  aso_type: string
  aso_reason: string
  description: string
  evidence_urls: string[]
  aso_status: string
  urgency: string
  responsibility: string
  suggested_action: string
  handle_opinion?: string
  custom_tags: string[]
  created_at: string
  updated_at: string
  order_info?: Order
}

/** 评价 */
export interface Evaluation {
  id: string
  order_id: string
  product_rating: number
  service_rating: number
  logistics_rating: number
  content: string
  image_urls: string[]
  is_anonymous: boolean
  sentiment: string
  themes: string[]
  created_at: string
  order_info?: Order
}

/** 待评价订单 */
export interface PendingEval {
  order_id: string
  order_sn: string
  product_name: string
  product_image: string
  total_amount: number
  finished_at: string
}

/** 通知消息 */
export interface Notice {
  id: string
  recipient_id: string
  recipient_type: string
  type: string
  title: string
  content: string
  link: string
  is_read: number
  created_at: string
}

/** 分页数据（后端 response.data 格式） */
export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** API统一响应（后端返回格式） */
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T | null
}
