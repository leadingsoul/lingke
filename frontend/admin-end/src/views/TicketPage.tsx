import { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Select, Input, DatePicker, Tag, Space, Modal, message, Alert,
} from 'antd';
import { SearchOutlined, TeamOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { ticketApi, staffApi, TicketItem, StaffItem } from '../api';

const { RangePicker } = DatePicker;

const TYPE_OPTIONS = [
  { label: '仅退款', value: '仅退款' },
  { label: '退货退款', value: '退货退款' },
  { label: '换货', value: '换货' },
  { label: '维修', value: '维修' },
];

const STATUS_OPTIONS = [
  { label: '待审核', value: '待审核' },
  { label: '审核通过', value: '审核通过' },
  { label: '处理中', value: '处理中' },
  { label: '已完成', value: '已完成' },
  { label: '已拒绝', value: '已拒绝' },
  { label: '已撤销', value: '已撤销' },
];

const URGENCY_OPTIONS = [
  { label: '普通', value: '普通' },
  { label: '紧急', value: '紧急' },
];

export default function TicketPage() {
  const [data, setData] = useState<TicketItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filterType, setFilterType] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterUrgency, setFilterUrgency] = useState<string>('');
  const [keyword, setKeyword] = useState('');
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [staffList, setStaffList] = useState<StaffItem[]>([]);
  const [selectedStaffId, setSelectedStaffId] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = {
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        aso_type: filterType || undefined,
        aso_status: filterStatus || undefined,
        urgency: filterUrgency || undefined,
        start_date: dateRange?.[0],
        end_date: dateRange?.[1],
      };
      const res = await ticketApi.list(params);
      setData(res.items);
      setTotal(res.total);
    } catch {
      setError('加载工单数据失败');
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterType, filterStatus, filterUrgency, keyword, dateRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openAssignModal = async () => {
    try {
      const staff = await staffApi.list();
      setStaffList(staff?.items || (Array.isArray(staff) ? staff : []));
      setSelectedStaffId(null);
      setAssignModalOpen(true);
    } catch {
      message.error('加载客服列表失败');
    }
  };

  const handleBatchAssign = async () => {
    if (!selectedStaffId) {
      message.warning('请选择客服');
      return;
    }
    setAssigning(true);
    try {
      await ticketApi.batchAssign(selectedRowKeys as string[], selectedStaffId!);
      message.success(`已将 ${selectedRowKeys.length} 个工单分配成功`);
      setAssignModalOpen(false);
      setSelectedRowKeys([]);
      fetchData();
    } catch {
      // handled by interceptor
    } finally {
      setAssigning(false);
    }
  };

  const columns: ColumnsType<TicketItem> = [
    { title: '工单号', dataIndex: 'ticket_no', key: 'ticket_no', width: 140 },
    { title: '消费者', dataIndex: 'consumer_name', key: 'consumer_name', width: 100 },
    {
      title: '售后类型', dataIndex: 'aso_type', key: 'aso_type', width: 100,
      render: (t: string) => <Tag color="blue">{t || '-'}</Tag>,
    },
    {
      title: '状态', dataIndex: 'aso_status', key: 'aso_status', width: 90,
      render: (s: string) => {
        const colorMap: Record<string, string> = { '待审核': 'orange', '审核通过': 'blue', '处理中': 'processing', '已完成': 'green', '已拒绝': 'red', '已撤销': 'default' };
        return <Tag color={colorMap[s] || 'default'}>{s || '-'}</Tag>;
      },
    },
    {
      title: '紧急度', dataIndex: 'urgency', key: 'urgency', width: 80,
      render: (u: string) => {
        const colorMap: Record<string, string> = { '普通': 'default', '紧急': 'red' };
        return <Tag color={colorMap[u] || 'default'}>{u || '-'}</Tag>;
      },
    },
    {
      title: '责任归属', dataIndex: 'responsibility', key: 'responsibility', width: 90,
      render: (r: string) => {
        const colorMap: Record<string, string> = { '商家': 'red', '物流': 'orange', '用户': 'blue', '待定': 'default' };
        return <Tag color={colorMap[r] || 'default'}>{r || '-'}</Tag>;
      },
    },
    { title: '负责人', dataIndex: 'assigned_to', key: 'assigned_to', width: 100,
      render: (v: string) => v || <span style={{ color: 'rgba(0,0,0,0.35)' }}>未分配</span> },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true, width: 180 },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-',
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Input
          placeholder="搜索工单号/客户/内容..."
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={() => { setPage(1); fetchData(); }}
          style={{ width: 240 }}
          allowClear
        />
        <Select
          placeholder="类型"
          value={filterType || undefined}
          onChange={(v) => { setFilterType(v || ''); setPage(1); }}
          allowClear
          style={{ width: 120 }}
          options={TYPE_OPTIONS}
        />
        <Select
          placeholder="状态"
          value={filterStatus || undefined}
          onChange={(v) => { setFilterStatus(v || ''); setPage(1); }}
          allowClear
          style={{ width: 120 }}
          options={STATUS_OPTIONS}
        />
        <Select
          placeholder="紧急度"
          value={filterUrgency || undefined}
          onChange={(v) => { setFilterUrgency(v || ''); setPage(1); }}
          allowClear
          style={{ width: 110 }}
          options={URGENCY_OPTIONS}
        />
        <RangePicker
          onChange={(_, dateStrings) => {
            setDateRange(dateStrings[0] && dateStrings[1] ? [dateStrings[0], dateStrings[1]] : null);
            setPage(1);
          }}
          placeholder={['开始日期', '结束日期']}
        />
        {selectedRowKeys.length > 0 && (
          <Button type="primary" icon={<TeamOutlined />} onClick={openAssignModal}>
            批量分配 ({selectedRowKeys.length})
          </Button>
        )}
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

      <Table
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
        }}
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: '暂无数据' }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
      />

      <Modal
        title="批量分配工单"
        open={assignModalOpen}
        onOk={handleBatchAssign}
        onCancel={() => setAssignModalOpen(false)}
        confirmLoading={assigning}
      >
        <p style={{ marginBottom: 16 }}>
          将为 <strong>{selectedRowKeys.length}</strong> 个工单分配客服
        </p>
        <Select
          placeholder="选择客服"
          value={selectedStaffId}
          onChange={(v) => setSelectedStaffId(v)}
          style={{ width: '100%' }}
          options={staffList.map((s) => ({
            label: `${s.name} (${s.username})`,
            value: s.id,
          }))}
          showSearch
          filterOption={(input, option) =>
            (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
          }
        />
      </Modal>
    </div>
  );
}
