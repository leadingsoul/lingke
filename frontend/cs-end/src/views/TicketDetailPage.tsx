import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Descriptions, Tag, Button, Space, Typography, Image, Modal, Input,
  Spin, Empty, Timeline, message, Divider,
} from 'antd';
import {
  ArrowLeftOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ExclamationCircleOutlined, PlusOutlined,
} from '@ant-design/icons';
import { ticketApi } from '../api';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

// Backend uses Chinese values — maps align with backend
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

const responsibilityColorMap: Record<string, string> = {
  '商家': 'red',
  '物流': 'orange',
  '用户': 'blue',
  '待定': 'default',
};

export default function TicketDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [ticket, setTicket] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [reviewModalOpen, setReviewModalOpen] = useState(false);
  const [reviewAction, setReviewAction] = useState<string>('');
  const [reviewOpinion, setReviewOpinion] = useState('');
  const [supplementModalOpen, setSupplementModalOpen] = useState(false);
  const [supplementNote, setSupplementNote] = useState('');
  const [newTag, setNewTag] = useState('');

  const fetchTicket = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const res: any = await ticketApi.detail(id);
      // Backend wraps: { code, message, data: {...} }
      setTicket(res.data || res);
    } catch {
      setTicket(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchTicket();
  }, [fetchTicket]);

  const handleReviewAction = (result: string) => {
    setReviewAction(result);
    setReviewOpinion('');
    setReviewModalOpen(true);
  };

  const handleSubmitReview = async () => {
    if (!reviewOpinion.trim() && reviewAction === '拒绝') {
      message.warning('请输入拒绝原因');
      return;
    }
    setActionLoading(true);
    try {
      await ticketApi.review(id!, {
        result: reviewAction, // Backend expects "result", not "action"
        opinion: reviewOpinion.trim() || undefined,
      });
      message.success(
        reviewAction === '通过' ? '审核通过' : reviewAction === '拒绝' ? '已拒绝' : '已处理'
      );
      setReviewModalOpen(false);
      fetchTicket();
    } catch {
      message.error('操作失败，请重试');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSupplement = async () => {
    if (!supplementNote.trim()) {
      message.warning('请输入补充说明');
      return;
    }
    setActionLoading(true);
    try {
      await ticketApi.supplement(id!, supplementNote.trim());
      message.success('已要求补充材料');
      setSupplementModalOpen(false);
      setSupplementNote('');
      fetchTicket();
    } catch {
      message.error('操作失败，请重试');
    } finally {
      setActionLoading(false);
    }
  };

  const handleComplete = () => {
    Modal.confirm({
      title: '确认完成',
      content: '确认该工单已处理完毕？完成后工单将标记为已完成状态。',
      okText: '确认完成',
      cancelText: '取消',
      onOk: async () => {
        try {
          await ticketApi.complete(id!);
          message.success('工单已完成');
          fetchTicket();
        } catch {
          message.error('操作失败，请重试');
        }
      },
    });
  };

  const handleAddTag = async () => {
    if (!newTag.trim()) return;
    try {
      await ticketApi.addTag(id!, newTag.trim());
      message.success('标签已添加');
      setNewTag('');
      fetchTicket();
    } catch {
      message.error('操作失败，请重试');
    }
  };

  const handleRemoveTag = async (tag: string) => {
    Modal.confirm({
      title: '确认移除',
      content: `确定要移除标签 "${tag}" 吗？`,
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        try {
          await ticketApi.removeTag(id!, tag);
          message.success('标签已移除');
          fetchTicket();
        } catch {
          message.error('操作失败，请重试');
        }
      },
    });
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="加载工单详情..." />
      </div>
    );
  }

  if (!ticket) {
    return <Empty description="工单不存在或加载失败" />;
  }

  const isPending = ticket.aso_status === '待审核';
  const isApproved = ticket.aso_status === '审核通过' || ticket.aso_status === '处理中';

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tickets')}>返回</Button>
          <Title level={5} style={{ margin: 0 }}>
            工单详情 - <Text code style={{ fontSize: 12 }}>{ticket.id?.slice(0, 12)}...</Text>
          </Title>
        </Space>
      </div>

      {/* Ticket Info Card */}
      <Card className="ticket-detail-section" title="基本信息">
        <Descriptions column={{ xs: 1, sm: 2, lg: 3 }} bordered size="small">
          <Descriptions.Item label="工单号">
            <Text code style={{ fontSize: 12 }}>{ticket.id}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="关联订单">
            <Text code style={{ fontSize: 12 }}>{ticket.order_id?.slice(0, 12)}...</Text>
          </Descriptions.Item>
          <Descriptions.Item label="售后类型">
            <Tag color={typeColorMap[ticket.aso_type] || 'default'}>{ticket.aso_type}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="售后原因">{ticket.aso_reason || '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusColorMap[ticket.aso_status] || 'default'}>{ticket.aso_status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="紧急度">
            <Tag color={urgencyColorMap[ticket.urgency] || 'default'}>{ticket.urgency}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="责任归属">
            <Tag color={responsibilityColorMap[ticket.responsibility] || 'default'}>
              {ticket.responsibility || '待定'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="申请人">{ticket.consumer_name || ticket.consumer_id?.slice(0, 12) || '-'}</Descriptions.Item>
          <Descriptions.Item label="负责人">{ticket.handler_name || '-'}</Descriptions.Item>
          <Descriptions.Item label="申请时间">
            {ticket.created_at ? dayjs(ticket.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {ticket.updated_at ? dayjs(ticket.updated_at).format('YYYY-MM-DD HH:mm:ss') : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* AI Suggested Action */}
      {ticket.suggested_action && (
        <Card className="ticket-detail-section" title="AI 建议处理方案" style={{ borderLeft: '3px solid #0D9488' }}>
          <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, margin: 0 }}>
            💡 {ticket.suggested_action}
          </Paragraph>
        </Card>
      )}

      {/* Description */}
      <Card className="ticket-detail-section" title="问题描述">
        <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
          {ticket.description || '暂无描述'}
        </Paragraph>
      </Card>

      {/* Review Opinion */}
      {ticket.review_opinion && (
        <Card className="ticket-detail-section" title="审核意见">
          <Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
            {ticket.review_opinion}
          </Paragraph>
        </Card>
      )}

      {/* Evidence Images */}
      {ticket.evidence_urls && ticket.evidence_urls.length > 0 && (
        <Card className="ticket-detail-section" title="凭证图片">
          <Image.PreviewGroup>
            <Space wrap size="middle">
              {ticket.evidence_urls.map((url: string, index: number) => (
                <Image
                  key={index}
                  src={url}
                  width={150}
                  height={120}
                  style={{ objectFit: 'cover', borderRadius: 6 }}
                  fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
                  alt={`凭证 ${index + 1}`}
                />
              ))}
            </Space>
          </Image.PreviewGroup>
        </Card>
      )}

      {/* Action Panel */}
      <Card className="ticket-detail-section" title="操作面板">
        <Space wrap size="middle">
          {isPending && (
            <>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={() => handleReviewAction('通过')}
                loading={actionLoading}
              >
                审核通过
              </Button>
              <Button
                danger
                icon={<CloseCircleOutlined />}
                onClick={() => handleReviewAction('拒绝')}
                loading={actionLoading}
              >
                拒绝
              </Button>
              <Button
                icon={<ExclamationCircleOutlined />}
                onClick={() => setSupplementModalOpen(true)}
                loading={actionLoading}
              >
                需补充材料
              </Button>
            </>
          )}
          {isApproved && (
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={handleComplete}
              loading={actionLoading}
            >
              完成工单
            </Button>
          )}
          {(ticket.aso_status === '已完成' || ticket.aso_status === '已拒绝' || ticket.aso_status === '已撤销') && (
            <Text type="secondary">工单已{ticket.aso_status}，无需操作</Text>
          )}
        </Space>
      </Card>

      {/* Tags Management */}
      <Card className="ticket-detail-section" title="标签管理">
        <div style={{ marginBottom: 12 }}>
          {ticket.custom_tags && ticket.custom_tags.length > 0 ? (
            ticket.custom_tags.map((tag: string) => (
              <Tag
                key={tag}
                closable
                onClose={() => handleRemoveTag(tag)}
                style={{ marginBottom: 8 }}
              >
                {tag}
              </Tag>
            ))
          ) : (
            <Text type="secondary">暂无标签</Text>
          )}
        </div>
        <Space.Compact style={{ width: 300 }}>
          <Input
            placeholder="输入新标签"
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
            onPressEnter={handleAddTag}
          />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={handleAddTag}
          >
            添加
          </Button>
        </Space.Compact>
      </Card>

      {/* Timeline */}
      <Card className="ticket-detail-section" title="处理时间线">
        {ticket.timeline && ticket.timeline.length > 0 ? (
          <Timeline
            items={ticket.timeline.map((item: any, index: number) => ({
              color: index === 0 ? 'blue' : 'gray',
              children: (
                <div>
                  <div style={{ fontWeight: 500 }}>{item.event}</div>
                  <div style={{ color: 'rgba(0,0,0,0.45)', fontSize: 13 }}>{item.detail}</div>
                  <div style={{ color: 'rgba(0,0,0,0.30)', fontSize: 12 }}>{item.time}</div>
                </div>
              ),
            }))}
          />
        ) : (
          <Empty description="暂无处理记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        )}
      </Card>

      {/* Review Modal */}
      <Modal
        title={reviewAction === '通过' ? '审核通过 - 审核意见' : '拒绝工单 - 拒绝原因'}
        open={reviewModalOpen}
        onOk={handleSubmitReview}
        onCancel={() => setReviewModalOpen(false)}
        okText={reviewAction === '通过' ? '确认通过' : '确认拒绝'}
        cancelText="取消"
        confirmLoading={actionLoading}
        okButtonProps={{ danger: reviewAction === '拒绝' }}
      >
        <TextArea
          rows={4}
          value={reviewOpinion}
          onChange={(e) => setReviewOpinion(e.target.value)}
          placeholder={reviewAction === '通过' ? '请输入审核意见（可选）' : '请输入拒绝原因（必填）'}
        />
      </Modal>

      {/* Supplement Modal */}
      <Modal
        title="要求补充材料"
        open={supplementModalOpen}
        onOk={handleSupplement}
        onCancel={() => setSupplementModalOpen(false)}
        okText="发送"
        cancelText="取消"
        confirmLoading={actionLoading}
      >
        <TextArea
          rows={4}
          value={supplementNote}
          onChange={(e) => setSupplementNote(e.target.value)}
          placeholder="请说明需要补充哪些材料..."
        />
      </Modal>
    </div>
  );
}
