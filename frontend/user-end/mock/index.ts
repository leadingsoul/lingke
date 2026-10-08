import type { MockMethod } from 'vite-plugin-mock'
import Mock from 'mockjs'

const { Random } = Mock

// 生成随机订单
function makeOrder(id?: number): any {
  const statuses = ['进行中', '已完成', '售后中', '已取消']
  const status = statuses[Math.floor(Math.random() * 3)] // 少出现已取消
  return {
    id: id ? String(id) : Random.guid(),
    orderSn: `EC${Random.date('yyyyMMdd')}${Random.integer(10000, 99999)}`,
    status,
    totalAmount: Number(Random.float(9.9, 1999, 2, 2)),
    productName: Random.ctitle(5, 15),
    productImage: Random.image('200x200', Random.color(), '#fff', Random.word()),
    createdAt: Random.datetime('yyyy-MM-dd HH:mm:ss'),
    finishedAt: status === '已完成' ? Random.datetime('yyyy-MM-dd HH:mm:ss') : undefined,
  }
}

// Mock 用户数据
const mockUser = {
  id: 1,
  openid: 'mock_openid_123',
  nickname: '测试用户',
  avatarUrl: 'https://img.yzcdn.cn/vant/cat.jpeg',
  phone: '138****0000',
  platformBindings: { taobao: 'tb_123' },
  createdAt: '2026-06-01 10:00:00',
  status: 1,
}

// 生成订单列表
const orderList = Array.from({ length: 20 }, (_, i) => makeOrder(i + 1))

export default [
  // ============ Auth ============
  {
    url: '/api/auth/wechat-login',
    method: 'post',
    response: ({ body }: any) => {
      const { code } = body
      if (!code) {
        return { code: 1001, message: '参数错误', data: null, traceId: Random.guid() }
      }
      return {
        code: 0,
        message: 'ok',
        data: {
          token: 'mock_jwt_token_' + Random.guid(),
          userInfo: { ...mockUser },
        },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: '/api/user/bind-phone',
    method: 'post',
    response: ({ body }: any) => {
      const { phone } = body
      if (!phone || !/^1[3-9]\d{9}$/.test(phone)) {
        return { code: 1001, message: '手机号格式不正确', data: null, traceId: Random.guid() }
      }
      mockUser.phone = phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
      return { code: 0, message: '绑定成功', data: null, traceId: Random.guid() }
    },
  },
  {
    url: '/api/user/link-platform',
    method: 'post',
    response: () => {
      return { code: 0, message: '关联成功', data: null, traceId: Random.guid() }
    },
  },

  // ============ User ============
  {
    url: '/api/user/profile',
    method: 'get',
    response: () => {
      return { code: 0, message: 'ok', data: { ...mockUser }, traceId: Random.guid() }
    },
  },
  {
    url: '/api/user/profile',
    method: 'put',
    response: ({ body }: any) => {
      Object.assign(mockUser, body)
      return { code: 0, message: '更新成功', data: mockUser, traceId: Random.guid() }
    },
  },

  // ============ Order ============
  {
    url: '/api/order/list',
    method: 'get',
    response: ({ query }: any) => {
      const { status, page = 1, size = 10 } = query
      let list = [...orderList]
      if (status && status !== 'all') {
        list = list.filter(o => o.status === status)
      }
      const start = (Number(page) - 1) * Number(size)
      return {
        code: 0,
        message: 'ok',
        data: { list: list.slice(start, start + Number(size)), total: list.length, page: Number(page), size: Number(size) },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: /\/api\/order\/detail\/(.+)/,
    method: 'get',
    response: ({ url }: any) => {
      const orderId = url.split('/').pop()
      const order = orderList.find(o => o.id === orderId) || makeOrder()
      return {
        code: 0,
        message: 'ok',
        data: {
          ...order,
          productSpec: '规格: 白色 / L码',
          quantity: Random.integer(1, 5),
          logisticsInfo: {
            company: '顺丰速运',
            trackingNo: `SF${Random.integer(100000000, 999999999)}`,
            status: '运输中',
            traces: [
              { time: '2026-06-24 08:30:00', status: '派送中', description: '快递员正在派送' },
              { time: '2026-06-24 06:00:00', status: '到达网点', description: '快件已到达目的地网点' },
              { time: '2026-06-23 22:00:00', status: '运输中', description: '快件在运输中' },
            ],
          },
        },
        traceId: Random.guid(),
      }
    },
  },

  // ============ Chat ============
  {
    url: '/api/chat/message',
    method: 'post',
    response: ({ body }: any) => {
      const intents = ['物流查询', '退货退款', '质量问题', '使用咨询', '发票问题', '价格问题']
      const intent = intents[Math.floor(Math.random() * intents.length)]
      const level = Math.random() > 0.7 ? 'L1' : (Math.random() > 0.5 ? 'L2' : 'L3')
      const replies: Record<string, string> = {
        '物流查询': '您的订单预计今日18:00前送达，当前快递员正在派送中。物流单号：SF1234567890',
        '退货退款': '请您在订单详情页点击"申请售后"选择退货退款，我们会在48小时内审核您的申请。',
        '质量问题': '非常抱歉给您带来不便！请拍照上传问题商品的照片，我们会尽快为您处理退换货。',
        '使用咨询': '您可以在商品详情页查看使用说明，或直接咨询人工客服获取详细指导。',
        '发票问题': '电子发票将在订单确认收货后1-3个工作日内开具，届时会发送到您绑定的邮箱。',
        '价格问题': '商品价格会根据促销活动有所变动，已购买的订单不支持退还差价哦。',
      }
      return {
        code: 0,
        message: 'ok',
        data: {
          reply: replies[intent],
          sessionId: body.sessionId || `sess_${Random.guid()}`,
          level,
          intent,
          confidence: Number(Random.float(0.5, 0.99, 2, 2)),
        },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: /\/api\/chat\/history\/(.+)/,
    method: 'get',
    response: () => {
      return {
        code: 0,
        message: 'ok',
        data: {
          messages: Array.from({ length: 6 }, (_, i) => ({
            id: i + 1,
            sessionId: 'sess_123',
            role: i % 2 === 0 ? 'user' : (i % 4 === 1 ? 'ai' : 'agent'),
            content: i % 2 === 0
              ? ['我的快递到哪了？', '商品收到有点问题', '可以退货吗'][Math.floor(i / 2)]
              : '您好，我来帮您查询一下，请稍等...',
            imageUrls: [] as string[],
            sentAt: Random.datetime('yyyy-MM-dd HH:mm:ss'),
          })),
          hasMore: false,
        },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: '/api/chat/sessions',
    method: 'get',
    response: ({ query }: any) => {
      const { page = 1, size = 10 } = query
      const list = Array.from({ length: 5 }, () => ({
        id: Random.guid(),
        userId: 1,
        startAt: Random.datetime('yyyy-MM-dd HH:mm:ss'),
        intent: ['物流查询', '退货退款', '质量问题'][Math.floor(Math.random() * 3)],
        level: ['L1', 'L2', 'L3'][Math.floor(Math.random() * 3)] as any,
        lastMessage: ['好的谢谢', '还有问题', '已经解决了'][Math.floor(Math.random() * 3)],
        lastMessageTime: Random.datetime('yyyy-MM-dd HH:mm:ss'),
      }))
      return {
        code: 0, message: 'ok',
        data: { list, total: 5, page: Number(page), size: Number(size) },
        traceId: Random.guid(),
      }
    },
  },

  // ============ Aftersale ============
  {
    url: '/api/aftersaleticket',
    method: 'post',
    response: () => {
      return {
        code: 0,
        message: '提交成功',
        data: { ticketId: `TK${Random.date('yyyyMMdd')}${Random.integer(1000, 9999)}` },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: '/api/aftersaleticket/list',
    method: 'get',
    response: ({ query }: any) => {
      const { page = 1, size = 10 } = query
      const types = ['仅退款', '退货退款', '换货', '维修']
      const reasons = ['质量问题', '发错货', '物流问题', '七天无理由', '描述不符', '其他']
      const statuses = ['待审核', '审核通过', '处理中', '已完成', '已拒绝']
      const list = Array.from({ length: 8 }, (_, i) => ({
        id: `TK2026${String(i + 1).padStart(2, '0')}`,
        orderId: orderList[i]?.id || String(i + 1),
        type: types[i % 4],
        reason: reasons[i % 6],
        description: '商品收到有明显划痕，包装完好但内部破损',
        evidenceUrls: [Random.image('200x200', Random.color(), '#fff', 'evidence')],
        status: statuses[i % 5],
        handleOpinion: i < 3 ? '已通过审核，请寄回商品' : undefined,
        aiType: types[i % 4],
        aiUrgency: (['high', 'medium', 'low'] as const)[i % 3],
        createdAt: Random.datetime('yyyy-MM-dd HH:mm:ss'),
        updatedAt: Random.datetime('yyyy-MM-dd HH:mm:ss'),
        orderInfo: orderList[i] || makeOrder(),
      }))
      return {
        code: 0, message: 'ok',
        data: { list, total: 8, page: Number(page), size: Number(size) },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: /\/api\/aftersaleticket\/detail\/(.+)/,
    method: 'get',
    response: ({ url }: any) => {
      const id = url.split('/').pop()
      return {
        code: 0,
        message: 'ok',
        data: {
          id,
          orderId: '1',
          type: '退货退款',
          reason: '质量问题',
          description: '商品收到有明显划痕',
          evidenceUrls: [Random.image('200x200', Random.color(), '#fff', 'evidence')],
          status: '处理中',
          handleOpinion: '已通过审核，请您在3天内寄回商品',
          aiType: '退货退款',
          aiUrgency: 'medium',
          createdAt: '2026-06-23 14:30:00',
          updatedAt: '2026-06-24 09:00:00',
          orderInfo: makeOrder(1),
        },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: /\/api\/aftersaleticket\/(.+)\/cancel/,
    method: 'post',
    response: () => {
      return { code: 0, message: '撤销成功', data: null, traceId: Random.guid() }
    },
  },

  // ============ Evaluate ============
  {
    url: '/api/evaluation',
    method: 'post',
    response: () => {
      return {
        code: 0,
        message: '评价提交成功',
        data: { evalId: `EV${Random.date('yyyyMMdd')}${Random.integer(1000, 9999)}` },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: '/api/evaluation/pending',
    method: 'get',
    response: ({ query }: any) => {
      const { page = 1, size = 10 } = query
      // 已完成订单中随机取作为待评价
      const doneOrders = orderList.filter(o => o.status === '已完成').concat(
        Array.from({ length: 5 }, () => makeOrder())
      )
      return {
        code: 0, message: 'ok',
        data: { list: doneOrders, total: doneOrders.length, page: Number(page), size: Number(size) },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: '/api/evaluation/my',
    method: 'get',
    response: ({ query }: any) => {
      const { page = 1, size = 10 } = query
      const list = Array.from({ length: 5 }, () => ({
        id: Random.guid(),
        orderId: String(Random.integer(1, 20)),
        scoreProduct: Random.integer(3, 5),
        scoreLogistics: Random.integer(3, 5),
        scoreService: Random.integer(3, 5),
        content: Random.ctitle(10, 30),
        imageUrls: [] as string[],
        isAnonymous: false,
        createdAt: Random.datetime('yyyy-MM-dd HH:mm:ss'),
        sentiment: ['positive', 'neutral', 'negative'][Math.floor(Math.random() * 3)] as any,
        topics: ['包装问题', '物流时效'][Math.floor(Math.random() * 2)],
        orderInfo: makeOrder(),
      }))
      return {
        code: 0, message: 'ok',
        data: { list, total: 5, page: Number(page), size: Number(size) },
        traceId: Random.guid(),
      }
    },
  },

  // ============ Notice ============
  {
    url: '/api/notice/list',
    method: 'get',
    response: ({ query }: any) => {
      const { page = 1, size = 10 } = query
      const list = [
        { id: 1, title: '售后进度更新', content: '您的工单TK001已审核通过，请寄回商品', type: 'aftersale', isRead: false, createdAt: '2026-06-24 09:30:00' },
        { id: 2, title: '系统通知', content: '系统将于6月25日凌晨2:00-4:00进行维护', type: 'system', isRead: false, createdAt: '2026-06-23 18:00:00' },
        { id: 3, title: '售后完成', content: '您的工单TK002已完成退款，请查收', type: 'aftersale', isRead: true, createdAt: '2026-06-22 15:00:00' },
        { id: 4, title: '评价提醒', content: '您在6月20日完成的订单还未评价，快去评价吧', type: 'service', isRead: true, createdAt: '2026-06-22 10:00:00' },
        { id: 5, title: '客服回复', content: '您咨询的问题已有客服回复，请查看', type: 'service', isRead: true, createdAt: '2026-06-21 14:00:00' },
      ]
      return {
        code: 0, message: 'ok',
        data: { list, total: list.length, page: Number(page), size: Number(size) },
        traceId: Random.guid(),
      }
    },
  },
  {
    url: '/api/notice/unread-count',
    method: 'get',
    response: () => {
      return { code: 0, message: 'ok', data: { count: 2 }, traceId: Random.guid() }
    },
  },
  {
    url: '/api/notice/read',
    method: 'post',
    response: () => {
      return { code: 0, message: 'ok', data: null, traceId: Random.guid() }
    },
  },

  // ============ Feedback ============
  {
    url: '/api/feedback',
    method: 'post',
    response: () => {
      return { code: 0, message: '感谢您的反馈！', data: null, traceId: Random.guid() }
    },
  },
] as MockMethod[]
