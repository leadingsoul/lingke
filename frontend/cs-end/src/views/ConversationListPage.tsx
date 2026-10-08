import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Table, Tag, Input, Select, Button, Space, Card, Typography, Empty, Spin, message, Badge, Modal, Tooltip } from 'antd';
import { SearchOutlined, ReloadOutlined, EyeOutlined, DeleteOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { conversationApi } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';
import dayjs from 'dayjs';

const { Title, Text } = Typography;

// 后端实际状态值（中文）→ 前端展示
const statusColorMap: Record<string, string> = {
  'AI进行中': 'blue',
  '待客服接手': 'gold',
  '待客服确认': 'orange',
  '客服处理中': 'green',
  '已关闭': 'default',
};

const statusLabelMap: Record<string, string> = {
  'AI进行中': 'AI处理中',
  '待客服接手': '等待接手',
  '待客服确认': '待审批',
  '客服处理中': '人工处理中',
  '已关闭': '已关闭',
};

const priorityColorMap: Record<string, string> = {
  '紧急': 'red',
  '普通': 'blue',
};

const priorityLabelMap: Record<string, string> = {
  '紧急': '高',
  '普通': '低',
};

const intentLevelLabelMap: Record<string, string> = {
  'L1': '普通咨询',
  'L2': '需关注',
  'L3': '需人工',
};

const intentLevelColorMap: Record<string, string> = {
  'L1': 'blue',
  'L2': 'orange',
  'L3': 'red',
};

// 需要人工介入的状态
const HUMAN_NEEDED_STATUSES = ['待客服接手', '待客服确认'] as const;

// SLA 倒计时秒数（5 分钟）
const SLA_SECONDS = 300;

/** 格式化剩余秒数为 "M:SS" */
function formatCountdown(remaining: number): string {
  if (remaining <= 0) return '超时';
  const m = Math.floor(remaining / 60);
  const s = remaining % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** 根据剩余秒数返回颜色 */
function countdownColor(remaining: number): string {
  if (remaining <= 0) return '#DC2626';      // 超时 → 红色
  if (remaining <= 30) return '#DC2626';      // <30s → 红色
  if (remaining <= 60) return '#EA580C';      // 30-60s → 橙色
  return '#16A34A';                            // >60s → 绿色
}

export default function ConversationListPage() {
  const navigate = useNavigate();
  const ws = useWebSocket();
  const [list, setList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filters, setFilters] = useState({
    status: undefined as string | undefined,
    priority: undefined as string | undefined,
    keyword: '',
  });

  // 每秒刷新当前时间，驱动倒计时
  const [now, setNow] = useState(Date.now());
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    tickRef.current = setInterval(() => setNow(Date.now()), 1000);
    return () => { if (tickRef.current) clearInterval(tickRef.current); };
  }, []);

  const fetchList = useCallback(async (page = 1, pageSize = 10, currentFilters = filters) => {
    setLoading(true);
    try {
      const params: any = { page, page_size: pageSize };
      if (currentFilters.status) params.status = currentFilters.status;
      if (currentFilters.priority) params.priority = currentFilters.priority;
      if (currentFilters.keyword) params.keyword = currentFilters.keyword;

      const res: any = await conversationApi.list(params);
      setList(res?.items || res?.results || []);
      setPagination({
        current: page,
        pageSize,
        total: res?.total || 0,
      });
    } catch {
      setList([]);
      setPagination({ current: page, pageSize, total: 0 });
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchList(1, 10, filters);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // WebSocket: 新消息/新会话 → 自动刷新列表
  useEffect(() => {
    const onNewMessage = () => {
      fetchList(pagination.current, pagination.pageSize, filters);
    };

    const onConversationUpdate = (data: any) => {
      const statusFilter = filters.status;
      if (!statusFilter || data.status === statusFilter) {
        message.info(`新会话接入: ${data.message || '有用户请求人工客服'}`);
        fetchList(1, pagination.pageSize, filters);
      }
    };

    ws.on('new_message', onNewMessage);
    ws.on('conversation_update', onConversationUpdate);
    return () => {
      ws.off('new_message', onNewMessage);
      ws.off('conversation_update', onConversationUpdate);
    };
  }, [ws, fetchList, pagination.current, pagination.pageSize, filters]);

  const handleTableChange = (pag: any) => {
    fetchList(pag.current, pag.pageSize, filters);
  };

  const handleSearch = () => {
    fetchList(1, pagination.pageSize, filters);
  };

  // 下拉筛选：直接替换筛选条件并立即查询
  const handleFilterChange = (key: 'status' | 'priority', val: any) => {
    const nextFilters = { ...filters, [key]: val };
    setFilters(nextFilters);
    fetchList(1, pagination.pageSize, nextFilters);
  };

  const handleDelete = (record: any) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要永久删除与 ${record.consumer_name} 的会话吗？此操作不可撤销。`,
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await conversationApi.delete(record.id);
          message.success('会话已删除');
          fetchList(pagination.current, pagination.pageSize);
        } catch {
          message.error('删除失败，请稍后重试');
        }
      },
    });
  };

  const columns = [
    {
      title: '会话', dataIndex: 'display_label', key: 'display_label', width: 160, ellipsis: true,
      render: (val: string, record: any) => (
        <Tooltip title={`会话ID: ${record.id}`} placement="topLeft">
          <span style={{ fontWeight: 500 }}>{val || record.id?.slice(0, 8) || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: '用户', dataIndex: 'consumer_name', key: 'consumer_name', width: 100,
      render: (val: string) => <a>{val}</a>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 110,
      render: (val: string) => (
        <Tag color={statusColorMap[val] || 'default'}>{statusLabelMap[val] || val}</Tag>
      ),
    },
    {
      title: '等待时长', dataIndex: 'updated_at', key: 'wait_time', width: 110,
      render: (updated_at: string, record: any) => {
        if (!HUMAN_NEEDED_STATUSES.includes(record.status) || !updated_at) return <span style={{ color: 'rgba(0,0,0,0.30)' }}>-</span>;
        // 去掉时区后缀，按本地时间（东八区）解析，避免后端标记为 +00:00 导致 8 小时偏差
        const localTime = updated_at.replace(/[+-]\d{2}:\d{2}$/, '');
        const waitSeconds = Math.floor((now - dayjs(localTime).valueOf()) / 1000);
        const remaining = Math.max(0, SLA_SECONDS - waitSeconds);
        const color = countdownColor(remaining);
        return (
          <span style={{ color, fontWeight: 600, fontSize: 13 }}>
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            {formatCountdown(remaining)}
          </span>
        );
      },
    },
    {
      title: '意图等级', dataIndex: 'intent_level', key: 'intent_level', width: 100,
      render: (val: string) => (
        <Tag color={intentLevelColorMap[val] || 'default'}>{intentLevelLabelMap[val] || val || '-'}</Tag>
      ),
    },
    {
      title: '优先级', dataIndex: 'priority', key: 'priority', width: 80,
      render: (val: string) => (
        <Tag color={priorityColorMap[val] || 'default'}>{priorityLabelMap[val] || val || '-'}</Tag>
      ),
    },
    {
      title: '最后消息', dataIndex: 'last_message', key: 'last_message', ellipsis: true,
      render: (val: string) => val || '-',
    },
    { title: '消息数', dataIndex: 'message_count', key: 'message_count', width: 80 },
    {
      title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 150,
      render: (val: string) => val ? dayjs(val).format('MM-DD HH:mm') : '-',
      sorter: true,
    },
    {
      title: '操作', key: 'action', width: 140, fixed: 'right' as const,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/conversations/${record.id}`);
            }}
          >
            查看
          </Button>
          <Button
            type="link"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              handleDelete(record);
            }}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>会话管理</Title>
        <Space>
          <Badge status={ws.isConnected ? 'success' : 'default'} text={ws.isConnected ? 'WS 实时' : '离线'} />
          <Button icon={<ReloadOutlined />} onClick={() => fetchList(1, pagination.pageSize)}>刷新</Button>
        </Space>
      </div>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 140 }}
            value={filters.status}
            onChange={(val) => handleFilterChange('status', val)}
            options={[
              { label: 'AI处理中', value: 'AI进行中' },
              { label: '等待接手', value: '待客服接手' },
              { label: '待审批', value: '待客服确认' },
              { label: '人工处理中', value: '客服处理中' },
              { label: '已关闭', value: '已关闭' },
            ]}
          />
          <Select
            placeholder="优先级筛选"
            allowClear
            style={{ width: 130 }}
            value={filters.priority}
            onChange={(val) => handleFilterChange('priority', val)}
            options={[
              { label: '高', value: '紧急' },
              { label: '低', value: '普通' },
            ]}
          />
          <Input
            placeholder="搜索用户"
            prefix={<SearchOutlined />}
            style={{ width: 200 }}
            value={filters.keyword}
            onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
            onPressEnter={handleSearch}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => {
            const empty = { status: undefined, priority: undefined, keyword: '' };
            setFilters(empty);
            fetchList(1, 10, empty);
          }}>
            重置
          </Button>
        </Space>
      </Card>

      <Card>
        <Spin spinning={loading}>
          {list.length > 0 ? (
            <Table
              columns={columns}
              dataSource={list}
              rowKey="id"
              pagination={{
                ...pagination,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条`,
              }}
              onChange={handleTableChange}
              scroll={{ x: 1300 }}
              onRow={(record) => {
                const isHumanNeeded = HUMAN_NEEDED_STATUSES.includes(record.status);
                let bgColor = 'transparent';
                if (isHumanNeeded && record.updated_at) {
                  const localTime = record.updated_at.replace(/[+-]\d{2}:\d{2}$/, '');
                  const waitSeconds = Math.floor((now - dayjs(localTime).valueOf()) / 1000);
                  const remaining = SLA_SECONDS - waitSeconds;
                  if (remaining <= 0) bgColor = '#fff1f0';
                  else if (remaining <= 30) bgColor = '#fffbe6';
                }
                return {
                  onClick: () => navigate(`/conversations/${record.id}`),
                  style: { cursor: 'pointer', background: bgColor },
                };
              }}
            />
          ) : (
            <Empty description="暂无会话数据" />
          )}
        </Spin>
      </Card>
    </div>
  );
}
