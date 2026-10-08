import { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Input, Select, Tag, Space, Modal, Form,
  Tabs, Upload, message, Popconfirm, Alert,
} from 'antd';
import {
  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, UploadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { knowledgeApi, KnowledgeItem, KnowledgeListParams } from '../api';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';

const QUILL_MODULES = {
  toolbar: [
    [{ header: [1, 2, 3, false] }],
    ['bold', 'italic', 'underline', 'strike'],
    [{ color: [] }, { background: [] }],
    [{ list: 'ordered' }, { list: 'bullet' }],
    [{ align: [] }],
    ['blockquote', 'code-block'],
    ['link', 'image'],
    ['clean'],
  ],
};

const QUILL_FORMATS = [
  'header', 'bold', 'italic', 'underline', 'strike',
  'color', 'background', 'list', 'bullet', 'align',
  'blockquote', 'code-block', 'link', 'image',
];

const TYPE_OPTIONS = [
  { label: '商品知识', value: '商品知识' },
  { label: 'FAQ', value: 'FAQ' },
  { label: '售后政策', value: '售后政策' },
];

const STATUS_OPTIONS = [
  { label: '启用', value: '启用' },
  { label: '草稿', value: '草稿' },
  { label: '已归档', value: '已归档' },
];

const TAG_OPTIONS = [
  { label: '退款', value: 'refund' },
  { label: '换货', value: 'exchange' },
  { label: '维修', value: 'repair' },
  { label: '物流', value: 'logistics' },
  { label: '投诉', value: 'complaint' },
  { label: '常见问题', value: 'common' },
];

function getTypeLabel(type: string): string {
  return TYPE_OPTIONS.find((t) => t.value === type)?.label || type;
}

export default function KnowledgePage() {
  const [data, setData] = useState<KnowledgeItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [activeTab, setActiveTab] = useState<string>('');
  const [keyword, setKeyword] = useState('');
  const [filterTag, setFilterTag] = useState<string>('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<KnowledgeItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [viewContent, setViewContent] = useState<string | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: KnowledgeListParams = {
        page,
        page_size: pageSize,
        keyword: keyword || undefined,
        type: activeTab || undefined,
        tag: filterTag || undefined,
      };
      const res = await knowledgeApi.list(params);
      setData(res.items);
      setTotal(res.total);
    } catch {
      setError('加载知识库数据失败');
      setData([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, activeTab, keyword, filterTag]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDelete = async (id: number) => {
    try {
      await knowledgeApi.delete(id);
      message.success('删除成功');
      fetchData();
    } catch {
      // handled by interceptor
    }
  };

  const openModal = (item?: KnowledgeItem) => {
    if (item) {
      setEditingItem(item);
      form.setFieldsValue(item);
    } else {
      setEditingItem(null);
      form.resetFields();
      form.setFieldsValue({ status: '草稿', tags: [] });
    }
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      if (editingItem) {
        await knowledgeApi.update(editingItem.id, values);
        message.success('更新成功');
      } else {
        await knowledgeApi.create(values);
        message.success('创建成功');
      }
      setModalOpen(false);
      form.resetFields();
      fetchData();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) {
        return; // antd form validation error, let antd display
      }
      message.error('保存失败，请检查填写内容后重试');
    } finally {
      setSubmitting(false);
    }
  };

  const handleImport = async (file: File) => {
    try {
      const res: any = await knowledgeApi.import(file);
      const msg = res?.data?.message || res?.message || `成功导入 ${res?.data?.imported || 0} 条知识`;
      message.success(msg);
      fetchData();
    } catch {
      // error handled by interceptor
    }
    return false; // prevent default upload
  };

  const columns: ColumnsType<KnowledgeItem> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 200,
      ellipsis: true,
      render: (text: string, record: KnowledgeItem) => (
        <a onClick={() => setViewContent(record.content)}>{text}</a>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 110,
      render: (type: string) => <Tag color="blue">{getTypeLabel(type)}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status: string) => {
        const colorMap: Record<string, string> = { '启用': 'green', '草稿': 'orange', '已归档': 'default' };
        const labelMap: Record<string, string> = { '启用': '启用', '草稿': '草稿', '已归档': '已归档' };
        return <Tag color={colorMap[status] || 'default'}>{labelMap[status] || status}</Tag>;
      },
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 180,
      render: (tags: string[]) => (
        <>{tags?.map((t) => <Tag key={t}>{t}</Tag>) || '-'}</>
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 90,
      render: (s: string) => <Tag>{s || 'manual'}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (t: string) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_: unknown, record: KnowledgeItem) => (
        <Space onClick={(e) => e.stopPropagation()}>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openModal(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该知识条目？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Tabs
        activeKey={activeTab}
        onChange={(key) => { setActiveTab(key); setPage(1); }}
        items={[
          { key: '', label: '全部' },
          ...TYPE_OPTIONS.map((t) => ({ key: t.value, label: t.label })),
        ]}
      />

      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <Input
          placeholder="搜索标题..."
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={() => { setPage(1); fetchData(); }}
          style={{ width: 240 }}
          allowClear
        />
        <Select
          placeholder="标签筛选"
          value={filterTag || undefined}
          onChange={(val) => { setFilterTag(val || ''); setPage(1); }}
          allowClear
          style={{ width: 150 }}
          options={TAG_OPTIONS}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>
          新增
        </Button>
        <Upload
          accept=".xlsx,.xls,.docx,.pdf,.pptx,.ppt,.html,.htm,.txt,.json,.csv,.md"
          showUploadList={false}
          beforeUpload={handleImport}
        >
          <Button icon={<UploadOutlined />}>导入文档</Button>
        </Upload>
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

      <Table
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
        onRow={(record) => ({
          onClick: () => openModal(record),
          style: { cursor: 'pointer' },
        })}
      />

      {/* View Content Modal */}
      <Modal
        title="查看内容"
        open={!!viewContent}
        onCancel={() => setViewContent(null)}
        footer={null}
        width={700}
      >
        <div
          className="ql-editor"
          style={{ maxHeight: 500, overflow: 'auto', padding: 12, background: 'rgba(0,0,0,0.025)', borderRadius: 12 }}
          dangerouslySetInnerHTML={{ __html: viewContent || '' }}
        />
      </Modal>

      {/* Create / Edit Modal */}
      <Modal
        title={editingItem ? '编辑知识' : '新增知识'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        confirmLoading={submitting}
        width={800}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{ status: '草稿', tags: [], type: 'FAQ' }}
        >
          <Form.Item
            name="title"
            label="标题"
            rules={[{ required: true, message: '请输入标题' }]}
          >
            <Input placeholder="知识标题" />
          </Form.Item>
          <Form.Item
            name="type"
            label="类型"
            rules={[{ required: true, message: '请选择类型' }]}
          >
            <Select options={TYPE_OPTIONS} placeholder="选择类型" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select
              mode="multiple"
              options={TAG_OPTIONS}
              placeholder="选择标签"
            />
          </Form.Item>
          <Form.Item
            name="content"
            label="内容"
            rules={[{ required: true, message: '请输入内容' }]}
            style={{ marginBottom: 8 }}
          >
            <ReactQuill
              theme="snow"
              modules={QUILL_MODULES}
              formats={QUILL_FORMATS}
              placeholder="请输入知识内容，支持文字排版、图片、链接等..."
              style={{ height: 300 }}
            />
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select options={STATUS_OPTIONS} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
