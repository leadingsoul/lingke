import React, { useEffect, useState, useCallback } from 'react';
import { Table, Tag, Input, Select, Button, Space, Card, Typography, Empty, Spin } from 'antd';
import { SearchOutlined, ReloadOutlined, EyeOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { ticketApi } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';
import dayjs from 'dayjs';

const { Title } = Typography;

const typeColorMap: Record<string, string> = {
  '仅退款': 'volcano',
  '退货退款': 'red',
  '换货': 'orange',
  '维修': 'blue',
};

const statusColorMap: Record<string, string> = {
  '待审核': 'gold',
  '审核通过': 'blue',
  '处理中': 'blue',
  '已完成': 'green',
  '已拒绝': 'red',
  '已撤销': 'default',
};

const urgencyColorMap: Record<string, string> = {
  '紧急': 'red',
  '普通': 'blue',
};

export default function TicketListPage() {
  const navigate = useNavigate();
  const ws = useWebSocket();
  const [list, setList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filters, setFilters] = useState({
    type: undefined as string | undefined,
    status: undefined as string | undefined,
    urgency: undefined as string | undefined,
    keyword: '',
  });
  const filtersRef = React.useRef(filters);
  filtersRef.current = filters;

  const fetchList = useCallback(async (page = 1, pageSize = 10, overrideFilters?: typeof filters) => {
    const f = overrideFilters ?? filters;
    setLoading(true);
    try {
      const params: any = { page, page_size: pageSize };
      if (f.type) params.aso_type = f.type;
      if (f.status) params.aso_status = f.status;
      if (f.urgency) params.urgency = f.urgency;
      if (f.keyword) params.keyword = f.keyword;

      const res: any = await ticketApi.list(params);
      const data = res.data || res;
      // Backend returns { items, total, page, page_size }
      const items = (data.items || []).map((t: any) => ({
        ...t,
        // Ensure created_at is parseable
        created_at: t.created_at || '',
      }));
      setList(items);
      setPagination({ current: page, pageSize, total: data.total || 0 });
    } catch {
      setList([]);
      setPagination({ current: 1, pageSize: 10, total: 0 });
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // WebSocket: 新工单创建/状态变更时自动刷新列表
  useEffect(() => {
    const refresh = () => fetchList(1, 10);
    ws.on('ticket_update', refresh);
    return () => {
      ws.off('ticket_update', refresh);
    };
  }, [ws, fetchList]);

  const handleTableChange = (pag: any) => {
    fetchList(pag.current, pag.pageSize);
  };

  const handleSearch = () => {
    fetchList(1, pagination.pageSize, filters);
  };

  // 下拉筛选：替换筛选条件并立即查询（用新 filters 覆盖闭包旧值）
  const handleFilterChange = (key: 'type' | 'status' | 'urgency', val: any) => {
    const nextFilters = { ...filters, [key]: val };
    setFilters(nextFilters);
    fetchList(1, pagination.pageSize, nextFilters);
  };

  const columns = [
    { title: '工单号', dataIndex: 'ticket_no', key: 'ticket_no', width: 140,
      render: (val: string) => <span style={{ fontFamily: 'monospace', fontSize: 12 }}>{val || '-'}</span>,
    },
    {
      title: '类型', dataIndex: 'aso_type', key: 'aso_type', width: 90,
      render: (val: string) => <Tag color={typeColorMap[val] || 'default'}>{val}</Tag>,
    },
    {
      title: '状态', dataIndex: 'aso_status', key: 'aso_status', width: 90,
      render: (val: string) => <Tag color={statusColorMap[val] || 'default'}>{val}</Tag>,
    },
    {
      title: '紧急度', dataIndex: 'urgency', key: 'urgency', width: 80,
      render: (val: string) => <Tag color={urgencyColorMap[val] || 'default'}>{val}</Tag>,
    },
    {
      title: '责任归属', dataIndex: 'responsibility', key: 'responsibility', width: 100,
      render: (val: string) => {
        const respColorMap: Record<string, string> = { '商家': 'red', '物流': 'orange', '用户': 'blue', '待定': 'default' };
        return <Tag color={respColorMap[val] || 'default'}>{val || '待定'}</Tag>;
      },
    },
    { title: '申请人', dataIndex: 'consumer_name', key: 'consumer_name', width: 110 },
    { title: '描述摘要', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '申请时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (val: string) => val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    {
      title: '操作', key: 'action', width: 100, fixed: 'right' as const,
      render: (_: any, record: any) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/tickets/${record.id}`)}
        >
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>工单管理</Title>

      <Card style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <Select
            placeholder="类型筛选"
            allowClear
            style={{ width: 110 }}
            value={filters.type}
            onChange={(val) => handleFilterChange('type', val)}
            options={[
              { label: '仅退款', value: '仅退款' },
              { label: '退货退款', value: '退货退款' },
              { label: '换货', value: '换货' },
              { label: '维修', value: '维修' },
            ]}
          />
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 120 }}
            value={filters.status}
            onChange={(val) => handleFilterChange('status', val)}
            options={[
              { label: '待审核', value: '待审核' },
              { label: '审核通过', value: '审核通过' },
              { label: '处理中', value: '处理中' },
              { label: '已完成', value: '已完成' },
              { label: '已拒绝', value: '已拒绝' },
              { label: '已撤销', value: '已撤销' },
            ]}
          />
          <Select
            placeholder="紧急度筛选"
            allowClear
            style={{ width: 120 }}
            value={filters.urgency}
            onChange={(val) => handleFilterChange('urgency', val)}
            options={[
              { label: '紧急', value: '紧急' },
              { label: '普通', value: '普通' },
            ]}
          />
          <Input
            placeholder="搜索工单号/申请人/描述"
            prefix={<SearchOutlined />}
            style={{ width: 260 }}
            value={filters.keyword}
            onChange={(e) => setFilters((f) => ({ ...f, keyword: e.target.value }))}
            onPressEnter={handleSearch}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
            搜索
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => {
            setFilters({ type: undefined, status: undefined, urgency: undefined, keyword: '' });
            fetchList(1, 10);
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
              scroll={{ x: 1000 }}
              onRow={(record) => ({
                onClick: () => navigate(`/tickets/${record.id}`),
                style: { cursor: 'pointer' },
              })}
            />
          ) : (
            <Empty description="暂无工单数据" />
          )}
        </Spin>
      </Card>
    </div>
  );
}
