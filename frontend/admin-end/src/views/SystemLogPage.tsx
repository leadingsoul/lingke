import { useEffect, useState, useCallback } from 'react';
import {
  Table, Select, DatePicker, Tag, Space, Alert,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { logApi, LogItem } from '../api';

const { RangePicker } = DatePicker;

const ACTION_OPTIONS = [
  { label: '回复', value: '回复' },
  { label: '审核', value: '审核' },
  { label: '关闭', value: '关闭' },
  { label: '删除', value: '删除' },
];

const TARGET_TYPE_OPTIONS = [
  { label: '会话', value: 'conversation' },
  { label: '工单', value: 'ticket' },
  { label: '知识库', value: 'knowledge' },
  { label: '策略', value: 'policy' },
  { label: '客服', value: 'staff' },
  { label: 'AI配置', value: 'ai_config' },
  { label: '对策', value: 'countermeasure' },
  { label: '沉淀文档', value: 'summary' },
];

const ACTION_COLOR_MAP: Record<string, string> = {
  '回复': 'blue',
  '审核': 'orange',
  '关闭': 'green',
  '删除': 'red',
};

const TARGET_COLOR_MAP: Record<string, string> = {
  'conversation': 'geekblue',
  'ticket': 'volcano',
  'knowledge': 'green',
  'policy': 'purple',
  'staff': 'cyan',
  'ai_config': 'lime',
  'countermeasure': 'gold',
  'summary': 'magenta',
};

export default function SystemLogPage() {
  const [data, setData] = useState<LogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [filterAction, setFilterAction] = useState<string>('');
  const [filterTargetType, setFilterTargetType] = useState<string>('');
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {
        page,
        page_size: pageSize,
        action: filterAction || undefined,
        target_type: filterTargetType || undefined,
        start_date: dateRange?.[0],
        end_date: dateRange?.[1],
      };
      const res = await logApi.list(params);
      setData(res.items);
      setTotal(res.total);
    } catch {
      setError('加载操作日志失败');
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterAction, filterTargetType, dateRange]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const columns: ColumnsType<LogItem> = [
    {
      title: '操作人',
      dataIndex: 'staff_name',
      key: 'staff_name',
      width: 120,
      render: (name: string) => name || <span style={{ color: 'rgba(0,0,0,0.35)' }}>-</span>,
    },
    {
      title: '操作',
      dataIndex: 'action_cn',
      key: 'action',
      width: 90,
      render: (cn: string) => (
        <Tag color={ACTION_COLOR_MAP[cn] || 'default'}>{cn}</Tag>
      ),
    },
    {
      title: '目标类型',
      dataIndex: 'target_type_cn',
      key: 'target_type',
      width: 100,
      render: (cn: string) => (
        <Tag color={TARGET_COLOR_MAP[cn] || 'default'}>{cn}</Tag>
      ),
    },
    {
      title: '目标ID',
      dataIndex: 'target_id',
      key: 'target_id',
      width: 90,
    },
    {
      title: '详细信息',
      dataIndex: 'detail',
      key: 'detail',
      ellipsis: true,
      render: (d: string) => d || <span style={{ color: 'rgba(0,0,0,0.35)' }}>-</span>,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Select
          placeholder="操作类型"
          value={filterAction || undefined}
          onChange={(v) => { setFilterAction(v || ''); setPage(1); }}
          allowClear
          style={{ width: 140 }}
          options={ACTION_OPTIONS}
        />
        <Select
          placeholder="目标类型"
          value={filterTargetType || undefined}
          onChange={(v) => { setFilterTargetType(v || ''); setPage(1); }}
          allowClear
          style={{ width: 140 }}
          options={TARGET_TYPE_OPTIONS}
        />
        <RangePicker
          onChange={(_, dateStrings) => {
            setDateRange(dateStrings[0] && dateStrings[1] ? [dateStrings[0], dateStrings[1]] : null);
            setPage(1);
          }}
          placeholder={['开始日期', '结束日期']}
        />
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: '暂无日志' }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条日志`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
      />
    </div>
  );
}
