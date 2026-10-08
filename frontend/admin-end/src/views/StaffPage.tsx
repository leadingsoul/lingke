import { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Select, Tag, Space, Modal, Form, Input,
  InputNumber, Drawer, message, Alert,
} from 'antd';
import { PlusOutlined, EditOutlined, EyeOutlined, StopOutlined, CheckCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import ReactECharts from 'echarts-for-react';
import { staffApi, StaffItem, StaffPerformance } from '../api';

const STATUS_OPTIONS = [
  { label: '在线', value: '在线' },
  { label: '离线', value: '离线' },
  { label: '禁用', value: '禁用' },
];

const ROLE_OPTIONS = [
  { label: '管理员', value: 'admin' },
  { label: '主管', value: 'supervisor' },
  { label: '客服', value: 'agent' },
];

export default function StaffPage() {
  const [data, setData] = useState<StaffItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingStaff, setEditingStaff] = useState<StaffItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [performance, setPerformance] = useState<StaffPerformance | null>(null);
  const [perfLoading, setPerfLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await staffApi.list({ status: filterStatus || undefined });
      // 后端返回 { items: [], total: N }，前端拦截器已剥离外层 code
      setData(result?.items || (Array.isArray(result) ? result : []));
    } catch {
      setError('加载客服数据失败');
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [filterStatus]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields();
      setSubmitting(true);
      await staffApi.create(values);
      message.success('创建成功');
      setCreateModalOpen(false);
      createForm.resetFields();
      fetchData();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) {
        // validation error
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = async () => {
    if (!editingStaff) return;
    try {
      const values = await editForm.validateFields();
      setSubmitting(true);
      await staffApi.update(editingStaff.id, values);
      message.success('更新成功');
      setEditModalOpen(false);
      fetchData();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) {
        // validation error
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openDrawer = async (staff: StaffItem) => {
    setEditingStaff(staff);
    setDrawerOpen(true);
    setPerfLoading(true);
    try {
      const perf = await staffApi.getPerformance(staff.id);
      setPerformance(perf);
    } catch {
      message.error('加载绩效数据失败');
    } finally {
      setPerfLoading(false);
    }
  };

  const perfOption = (performance?.daily_stats?.length) ? {
    tooltip: { trigger: 'axis' },
    legend: { data: ['处理量', '满意度'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: {
      type: 'category',
      data: performance.daily_stats.map((d: any) => d.date),
    },
    yAxis: [
      { type: 'value', name: '处理量' },
      { type: 'value', name: '满意度(%)', max: 100 },
    ],
    series: [
      {
        name: '处理量',
        type: 'bar',
        data: performance.daily_stats.map((d: any) => d.handled),
        itemStyle: { color: '#0D9488' },
      },
      {
        name: '满意度',
        type: 'line',
        yAxisIndex: 1,
        data: performance.daily_stats.map((d: any) => d.satisfaction),
        lineStyle: { color: '#52C41A' },
      },
    ],
  } : null;

  const columns: ColumnsType<StaffItem> = [
    { title: '用户名', dataIndex: 'username', key: 'username', width: 120 },
    { title: '姓名', dataIndex: 'name', key: 'name', width: 100 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (status: string) => {
        const colorMap: Record<string, string> = { '在线': 'green', '离线': 'default', '禁用': 'red' };
        return <Tag color={colorMap[status] || 'default'}>{status || '-'}</Tag>;
      },
    },
    { title: '最大并发', dataIndex: 'max_concurrent', key: 'max_concurrent', width: 100 },
    { title: '今日处理', dataIndex: 'today_handled', key: 'today_handled', width: 100 },
    {
      title: '满意度', dataIndex: 'satisfaction_rate', key: 'satisfaction_rate', width: 100,
      render: (v: number) => v !== undefined ? `${v}%` : '-',
    },
    {
      title: '操作', key: 'actions', width: 220,
      render: (_: unknown, record: StaffItem) => {
        const isDisabled = record.status === '禁用';
        return (
          <Space onClick={(e) => e.stopPropagation()}>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
              setEditingStaff(record);
              editForm.setFieldsValue(record);
              setEditModalOpen(true);
            }}>
              编辑
            </Button>
            <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openDrawer(record)}>
              绩效
            </Button>
            <Button
              type="link"
              size="small"
              danger={!isDisabled}
              icon={isDisabled ? <CheckCircleOutlined /> : <StopOutlined />}
              onClick={async () => {
                const newStatus = isDisabled ? '在线' : '禁用';
                try {
                  await staffApi.update(record.id, { status: newStatus } as any);
                  message.success(isDisabled ? '已启用' : '已禁用');
                  fetchData();
                } catch {
                  message.error('操作失败');
                }
              }}
            >
              {isDisabled ? '启用' : '禁用'}
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Select
          placeholder="状态筛选"
          value={filterStatus || undefined}
          onChange={(val) => setFilterStatus(val || '')}
          allowClear
          style={{ width: 150 }}
          options={STATUS_OPTIONS}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
          新增客服
        </Button>
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: '暂无数据' }}
        pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
        onRow={(record) => ({
          onClick: () => openDrawer(record),
          style: { cursor: 'pointer' },
        })}
      />

      {/* Create Modal */}
      <Modal
        title="新增客服"
        open={createModalOpen}
        onOk={handleCreate}
        onCancel={() => { setCreateModalOpen(false); createForm.resetFields(); }}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input placeholder="登录用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password placeholder="初始密码" />
          </Form.Item>
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="真实姓名" />
          </Form.Item>
          <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select options={ROLE_OPTIONS} placeholder="选择角色" />
          </Form.Item>
          <Form.Item name="phone" label="电话">
            <Input placeholder="联系电话" />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="邮箱地址" />
          </Form.Item>
          <Form.Item name="max_concurrent" label="最大并发数" initialValue={5}>
            <InputNumber min={1} max={50} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        title="编辑客服"
        open={editModalOpen}
        onOk={handleEdit}
        onCancel={() => { setEditModalOpen(false); editForm.resetFields(); }}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
            <Input placeholder="真实姓名" />
          </Form.Item>
          <Form.Item name="status" label="状态" rules={[{ required: true, message: '请选择状态' }]}>
            <Select options={STATUS_OPTIONS} />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input placeholder="邮箱地址" />
          </Form.Item>
          <Form.Item name="max_concurrent" label="最大并发数">
            <InputNumber min={1} max={50} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Performance Drawer */}
      <Drawer
        title={`${editingStaff?.name || ''} 的绩效详情`}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setPerformance(null); }}
        width={600}
        loading={perfLoading}
      >
        {performance ? (
          <>
            <div style={{ display: 'flex', gap: 24, marginBottom: 24 }}>
              <div><strong>总处理量</strong><p style={{ fontSize: 24, color: '#0D9488' }}>{performance.total_handled}</p></div>
              <div><strong>平均满意度</strong><p style={{ fontSize: 24, color: '#52C41A' }}>{performance.avg_satisfaction}%</p></div>
              <div><strong>平均响应</strong><p style={{ fontSize: 24, color: '#FA8C16' }}>{performance.avg_response_time}s</p></div>
            </div>
            {perfOption && (
              <div style={{ height: 320 }}>
                <ReactECharts option={perfOption} style={{ height: '100%' }} />
              </div>
            )}
          </>
        ) : (
          <Alert type="info" message="暂无绩效数据" />
        )}
      </Drawer>
    </div>
  );
}
