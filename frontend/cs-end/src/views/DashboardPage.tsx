import React, { useEffect, useState, useCallback } from 'react';
import { Row, Col, Card, Statistic, Table, Tag, Spin, Empty, Typography, notification, Badge } from 'antd';
import {
  MessageOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  AlertOutlined,
  ExclamationCircleOutlined,
  WifiOutlined,
} from '@ant-design/icons';
import { dashboardApi } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';
import dayjs from 'dayjs';

const { Title } = Typography;

interface DashboardData {
  pending_conversations: number;
  pending_tickets: number;
  today_processed: number;
  avg_response_time: string;
  urgent_conversations: any[];
  pending_ticket_list: any[];
}

const urgencyColorMap: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'blue',
};

const priorityColorMap: Record<string, string> = {
  高: 'red',
  中: 'orange',
  低: 'blue',
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const ws = useWebSocket();

  const fetchDashboard = useCallback(async () => {
    try {
      const res: any = await dashboardApi.getCSDashboard();
      setData(res.data || res);
    } catch (err) {
      // Use mock data on failure
      setData({
        pending_conversations: 12,
        pending_tickets: 8,
        today_processed: 45,
        avg_response_time: '2.5分钟',
        urgent_conversations: [
          { id: 1, username: '用户A', last_message: '我的订单为什么还没发货？', urgency: 'high', priority: '高', created_at: new Date().toISOString() },
          { id: 2, username: '用户B', last_message: '收到的商品有质量问题', urgency: 'high', priority: '高', created_at: new Date().toISOString() },
          { id: 3, username: '用户C', last_message: '申请退款一直未处理', urgency: 'high', priority: '中', created_at: new Date().toISOString() },
          { id: 4, username: '用户D', last_message: '账号被限制登录', urgency: 'medium', priority: '中', created_at: new Date().toISOString() },
          { id: 5, username: '用户E', last_message: '优惠券无法使用', urgency: 'medium', priority: '高', created_at: new Date().toISOString() },
        ],
        pending_ticket_list: [
          { id: 1, ticket_no: 'TK20240101001', type: '退货', urgency: 'high', status: 'pending', applicant: '用户A', description: '商品破损要求退货', created_at: new Date().toISOString() },
          { id: 2, ticket_no: 'TK20240101002', type: '换货', urgency: 'medium', status: 'pending', applicant: '用户B', description: '尺码不合适申请换货', created_at: new Date().toISOString() },
          { id: 3, ticket_no: 'TK20240101003', type: '退款', urgency: 'high', status: 'processing', applicant: '用户C', description: '未收到货申请退款', created_at: new Date().toISOString() },
          { id: 4, ticket_no: 'TK20240101004', type: '投诉', urgency: 'low', status: 'pending', applicant: '用户D', description: '物流时效投诉', created_at: new Date().toISOString() },
          { id: 5, ticket_no: 'TK20240101005', type: '咨询', urgency: 'low', status: 'pending', applicant: '用户E', description: '商品库存咨询', created_at: new Date().toISOString() },
        ],
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    // HTTP 轮询降级到 60s（WebSocket 会实时触发刷新）
    const timer = setInterval(fetchDashboard, 60000);
    return () => clearInterval(timer);
  }, [fetchDashboard]);

  // WebSocket: 会话更新或工单变更时，自动刷新工作台数据 + 弹窗提醒
  useEffect(() => {
    const handleConversationUpdate = (eventData: any) => {
      fetchDashboard()
      const msg = eventData?.message || eventData?.data?.message || '有一条新的会话更新'
      notification.info({
        message: '会话更新',
        description: msg,
        placement: 'topRight',
        duration: 5,
        icon: <MessageOutlined style={{ color: '#0D9488' }} />,
      })
    }
    const handleTicketUpdate = (eventData: any) => {
      fetchDashboard()
      const msg = eventData?.message || eventData?.data?.message || '有一条新的工单更新'
      notification.warning({
        message: '工单更新',
        description: msg,
        placement: 'topRight',
        duration: 5,
        icon: <FileTextOutlined style={{ color: '#EA580C' }} />,
      })
    }
    ws.on('conversation_update', handleConversationUpdate)
    ws.on('ticket_update', handleTicketUpdate)
    return () => {
      ws.off('conversation_update', handleConversationUpdate)
      ws.off('ticket_update', handleTicketUpdate)
    }
  }, [ws, fetchDashboard])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="加载工作台数据..." />
      </div>
    );
  }

  if (!data) {
    return <Empty description="暂无数据" />;
  }

  const conversationColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username', width: 100 },
    { title: '最后消息', dataIndex: 'last_message', key: 'last_message', ellipsis: true },
    {
      title: '紧急度', dataIndex: 'urgency', key: 'urgency', width: 90,
      render: (val: string) => <Tag color={urgencyColorMap[val] || 'default'}>{val === 'high' ? '紧急' : val === 'medium' ? '中等' : '一般'}</Tag>,
    },
    {
      title: '优先级', dataIndex: 'priority', key: 'priority', width: 80,
      render: (val: string) => <Tag color={priorityColorMap[val] || 'default'}>{val}</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
  ];

  const ticketColumns = [
    { title: '工单号', dataIndex: 'ticket_no', key: 'ticket_no', width: 160 },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 80,
      render: (val: string) => <Tag>{val}</Tag>,
    },
    {
      title: '紧急度', dataIndex: 'urgency', key: 'urgency', width: 90,
      render: (val: string) => <Tag color={urgencyColorMap[val] || 'default'}>{val === 'high' ? '紧急' : val === 'medium' ? '中等' : '一般'}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (val: string) => {
        const map: Record<string, { color: string; text: string }> = {
          pending: { color: 'gold', text: '待审核' },
          processing: { color: 'blue', text: '处理中' },
          completed: { color: 'green', text: '已完成' },
          rejected: { color: 'red', text: '已拒绝' },
        };
        const item = map[val] || { color: 'default', text: val };
        return <Tag color={item.color}>{item.text}</Tag>;
      },
    },
    { title: '申请人', dataIndex: 'applicant', key: 'applicant', width: 100 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '申请时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (val: string) => dayjs(val).format('YYYY-MM-DD HH:mm'),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        工作台
        <Badge status={ws.isConnected ? 'success' : 'default'} style={{ marginLeft: 12 }} text={ws.isConnected ? 'WS实时' : 'HTTP'} />
      </Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <div className="stat-card">
              <Statistic
                title="待处理会话"
                value={data.pending_conversations}
                prefix={<MessageOutlined style={{ color: '#0D9488' }} />}
                valueStyle={{ color: '#0D9488' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <div className="stat-card">
              <Statistic
                title="待审核工单"
                value={data.pending_tickets}
                prefix={<FileTextOutlined style={{ color: '#EA580C' }} />}
                valueStyle={{ color: '#EA580C' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <div className="stat-card">
              <Statistic
                title="今日已处理"
                value={data.today_processed}
                prefix={<CheckCircleOutlined style={{ color: '#16A34A' }} />}
                valueStyle={{ color: '#16A34A' }}
              />
            </div>
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <div className="stat-card">
              <Statistic
                title="平均响应时间"
                value={data.avg_response_time}
                prefix={<ClockCircleOutlined style={{ color: '#722ed1' }} />}
                valueStyle={{ color: '#722ed1' }}
              />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title={<span><ExclamationCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />紧急会话</span>}
            bodyStyle={{ padding: '12px' }}
          >
            {data.urgent_conversations && data.urgent_conversations.length > 0 ? (
              <Table
                columns={conversationColumns}
                dataSource={data.urgent_conversations}
                rowKey="id"
                size="small"
                pagination={false}
                scroll={{ x: 500 }}
              />
            ) : (
              <Empty description="暂无紧急会话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={<span><AlertOutlined style={{ color: '#faad14', marginRight: 8 }} />待处理工单</span>}
            bodyStyle={{ padding: '12px' }}
          >
            {data.pending_ticket_list && data.pending_ticket_list.length > 0 ? (
              <Table
                columns={ticketColumns}
                dataSource={data.pending_ticket_list}
                rowKey="id"
                size="small"
                pagination={false}
                scroll={{ x: 700 }}
              />
            ) : (
              <Empty description="暂无待处理工单" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
