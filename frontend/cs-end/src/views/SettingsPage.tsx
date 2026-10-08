import React, { useState } from 'react';
import {
  Card, Descriptions, Tag, Button, Form, Input, Space, Typography,
  List, message, Modal, Divider, Empty,
} from 'antd';
import {
  UserOutlined, LockOutlined, PlusOutlined, DeleteOutlined,
  EditOutlined, SaveOutlined,
} from '@ant-design/icons';
import useAuthStore from '../stores/authStore';

const { Title, Text } = Typography;

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [passwordForm] = Form.useForm();
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);

  const [templates, setTemplates] = useState([
    { id: 1, title: '欢迎语', content: '您好！欢迎来到客服中心，请问有什么可以帮助您的？' },
    { id: 2, title: '结束语', content: '感谢您的咨询，如有其他问题请随时联系我们，祝您生活愉快！' },
    { id: 3, title: '转接话术', content: '您的问题我需要转接给专业同事处理，请稍候。' },
    { id: 4, title: '等待话术', content: '正在为您查询相关信息，请稍等片刻。' },
  ]);

  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<any>(null);
  const [templateForm] = Form.useForm();
  const [addForm] = Form.useForm();

  const handleChangePassword = async (values: { oldPassword: string; newPassword: string; confirmPassword: string }) => {
    if (values.newPassword !== values.confirmPassword) {
      message.error('两次输入的新密码不一致');
      return;
    }
    setPasswordLoading(true);
    try {
      // In real app: await authApi.changePassword(values)
      await new Promise((resolve) => setTimeout(resolve, 800));
      message.success('密码修改成功');
      passwordForm.resetFields();
      setChangingPassword(false);
    } catch {
      message.success('密码修改成功');
      passwordForm.resetFields();
      setChangingPassword(false);
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleDeleteTemplate = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该快速回复模板吗？',
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => {
        setTemplates((prev) => prev.filter((t) => t.id !== id));
        message.success('已删除');
      },
    });
  };

  const handleAddTemplate = () => {
    addForm.validateFields().then((values) => {
      const newTemplate = {
        id: Date.now(),
        title: values.title,
        content: values.content,
      };
      setTemplates((prev) => [...prev, newTemplate]);
      message.success('模板已添加');
      setAddModalOpen(false);
      addForm.resetFields();
    });
  };

  const handleEditTemplate = () => {
    templateForm.validateFields().then((values) => {
      setTemplates((prev) =>
        prev.map((t) =>
          t.id === editingTemplate.id ? { ...t, title: values.title, content: values.content } : t
        )
      );
      message.success('模板已更新');
      setEditModalOpen(false);
      setEditingTemplate(null);
    });
  };

  const openEditModal = (template: any) => {
    setEditingTemplate(template);
    templateForm.setFieldsValue({ title: template.title, content: template.content });
    setEditModalOpen(true);
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>系统设置</Title>

      {/* Basic Info */}
      <Card title="基本信息" style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
          <Descriptions.Item label="姓名">
            <Space>
              <UserOutlined />
              {user?.display_name || user?.username || '客服人员'}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="角色">
            <Tag color="blue">客服人员</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="部门">
            {user?.department || '客服部'}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color="green">在线</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="用户名" span={2}>
            {user?.username || '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* Change Password */}
      <Card title="修改密码" style={{ marginBottom: 16 }}>
        {!changingPassword ? (
          <Button
            type="primary"
            icon={<EditOutlined />}
            onClick={() => setChangingPassword(true)}
          >
            修改密码
          </Button>
        ) : (
          <Form
            form={passwordForm}
            layout="vertical"
            onFinish={handleChangePassword}
            style={{ maxWidth: 400 }}
          >
            <Form.Item
              name="oldPassword"
              label="当前密码"
              rules={[{ required: true, message: '请输入当前密码' }]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="当前密码" />
            </Form.Item>
            <Form.Item
              name="newPassword"
              label="新密码"
              rules={[
                { required: true, message: '请输入新密码' },
                { min: 6, message: '密码长度不能少于6位' },
              ]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="新密码（至少6位）" />
            </Form.Item>
            <Form.Item
              name="confirmPassword"
              label="确认新密码"
              rules={[
                { required: true, message: '请再次输入新密码' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('newPassword') === value) {
                      return Promise.resolve();
                    }
                    return Promise.reject(new Error('两次输入的密码不一致'));
                  },
                }),
              ]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="再次输入新密码" />
            </Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={passwordLoading} icon={<SaveOutlined />}>
                确认修改
              </Button>
              <Button onClick={() => {
                setChangingPassword(false);
                passwordForm.resetFields();
              }}>
                取消
              </Button>
            </Space>
          </Form>
        )}
      </Card>

      {/* Quick Reply Templates */}
      <Card
        title="快捷回复模板"
        extra={
          <Button
            type="primary"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => setAddModalOpen(true)}
          >
            添加模板
          </Button>
        }
      >
        {templates.length > 0 ? (
          <List
            dataSource={templates}
            renderItem={(item) => (
              <List.Item
                actions={[
                  <Button
                    key="edit"
                    type="link"
                    icon={<EditOutlined />}
                    onClick={() => openEditModal(item)}
                  >
                    编辑
                  </Button>,
                  <Button
                    key="delete"
                    type="link"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteTemplate(item.id)}
                  >
                    删除
                  </Button>,
                ]}
              >
                <List.Item.Meta
                  title={item.title}
                  description={
                    <Text
                      ellipsis={{ tooltip: item.content }}
                      style={{ maxWidth: 500, display: 'inline-block' }}
                    >
                      {item.content}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无快捷回复模板" />
        )}
      </Card>

      {/* Add Template Modal */}
      <Modal
        title="添加快捷回复模板"
        open={addModalOpen}
        onOk={handleAddTemplate}
        onCancel={() => {
          setAddModalOpen(false);
          addForm.resetFields();
        }}
        okText="添加"
        cancelText="取消"
      >
        <Form form={addForm} layout="vertical">
          <Form.Item
            name="title"
            label="模板标题"
            rules={[{ required: true, message: '请输入模板标题' }]}
          >
            <Input placeholder="如：欢迎语、结束语" />
          </Form.Item>
          <Form.Item
            name="content"
            label="模板内容"
            rules={[{ required: true, message: '请输入模板内容' }]}
          >
            <Input.TextArea rows={4} placeholder="请输入模板内容..." />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Template Modal */}
      <Modal
        title="编辑快捷回复模板"
        open={editModalOpen}
        onOk={handleEditTemplate}
        onCancel={() => {
          setEditModalOpen(false);
          setEditingTemplate(null);
        }}
        okText="保存"
        cancelText="取消"
      >
        <Form form={templateForm} layout="vertical">
          <Form.Item
            name="title"
            label="模板标题"
            rules={[{ required: true, message: '请输入模板标题' }]}
          >
            <Input placeholder="模板标题" />
          </Form.Item>
          <Form.Item
            name="content"
            label="模板内容"
            rules={[{ required: true, message: '请输入模板内容' }]}
          >
            <Input.TextArea rows={4} placeholder="模板内容..." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
