import { useEffect, useState, useCallback } from 'react';
import {
  Card, Button, Tag, Space, Modal, Input,
  message, Spin, Alert, Row, Col, Empty,
} from 'antd';
import {
  CheckOutlined, CloseOutlined, EyeOutlined, SyncOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import dayjs from 'dayjs';
import { summaryApi, EvolutionItem } from '../api';

const { TextArea } = Input;

export default function EvolutionPage() {
  // Summaries tab
  const [summaries, setSummaries] = useState<EvolutionItem[]>([]);
  const [summLoading, setSummLoading] = useState(false);
  const [summError, setSummError] = useState<string | null>(null);
  const [viewDoc, setViewDoc] = useState<EvolutionItem | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const [reviewComment, setReviewComment] = useState('');

  // Actions
  const [actionLoading, setActionLoading] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);

  const fetchSummaries = useCallback(async () => {
    setSummLoading(true);
    setSummError(null);
    try {
      const data = await summaryApi.list();
      setSummaries(data?.items || (Array.isArray(data) ? data : []));
    } catch {
      setSummError('加载沉淀文档失败');
    } finally {
      setSummLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummaries();
  }, [fetchSummaries]);

  const handleReview = async (id: number, status: string) => {
    setActionLoading(true);
    try {
      await summaryApi.review(id, status, reviewComment);
      message.success(status === 'approved' ? '审核通过' : '已驳回');
      setViewDoc(null);
      setReviewComment('');
      fetchSummaries();
    } catch {
      // handled by interceptor
    } finally {
      setActionLoading(false);
    }
  };

  const handleSyncToKnowledge = async (id: number) => {
    setSyncLoading(true);
    try {
      await summaryApi.syncToKnowledge(id);
      message.success('已同步至知识库');
      setViewDoc({ ...viewDoc!, synced_to_knowledge: true } as any);
      fetchSummaries();
    } catch {
      // handled by interceptor
    } finally {
      setSyncLoading(false);
    }
  };

  return (
    <div>
      {summError && <Alert type="error" message={summError} showIcon style={{ marginBottom: 16 }} />}
      <Spin spinning={summLoading}>
        <Row gutter={[16, 16]}>
          {summaries.length === 0 && !summLoading && (
            <Col span={24}><Empty description="暂无沉淀文档" /></Col>
          )}
          {summaries.map((item) => (
            <Col xs={24} sm={12} lg={8} key={item.id}>
              <Card
                title={item.title || `沉淀文档 #${item.id}`}
                extra={
                  <Space size={4}>
                    <Tag color={item.review_status === '待审核' ? 'orange' : item.review_status === '已驳回' ? 'red' : 'green'}>
                      {item.review_status || '待审核'}
                    </Tag>
                    {item.synced_to_knowledge && <Tag color="blue" icon={<SyncOutlined />}>已同步</Tag>}
                  </Space>
                }
                hoverable
                size="small"
                actions={[
                  <Button
                    type="link"
                    icon={<EyeOutlined />}
                    loading={viewLoading}
                    onClick={async () => {
                      setViewLoading(true);
                      try {
                        const detail = await summaryApi.getById(item.id);
                        setViewDoc(detail);
                      } catch {
                        message.error('加载文档详情失败');
                      } finally {
                        setViewLoading(false);
                      }
                    }}
                  >
                    查看
                  </Button>,
                ]}
              >
                <p style={{ color: 'rgba(0,0,0,0.45)', fontSize: 12 }}>
                  {dayjs(item.created_at).format('YYYY-MM-DD HH:mm')}
                </p>
                <p style={{ color: 'rgba(0,0,0,0.45)' }}>类型: {item.type || '沉淀文档'}</p>
              </Card>
            </Col>
          ))}
        </Row>
      </Spin>

      <Modal
        title={viewDoc?.title || '文档详情'}
        open={!!viewDoc}
        onCancel={() => { setViewDoc(null); setReviewComment(''); }}
        width={700}
        footer={
          viewDoc?.review_status === '待审核' ? (
            <Space>
              <TextArea
                rows={2}
                value={reviewComment}
                onChange={(e) => setReviewComment(e.target.value)}
                placeholder="审核意见（可选）"
                style={{ width: 300 }}
              />
              <Button
                type="primary"
                icon={<CheckOutlined />}
                loading={actionLoading}
                onClick={() => handleReview(viewDoc!.id, 'approved')}
              >
                审核通过
              </Button>
              <Button
                danger
                icon={<CloseOutlined />}
                loading={actionLoading}
                onClick={() => handleReview(viewDoc!.id, 'rejected')}
              >
                驳回
              </Button>
            </Space>
          ) : viewDoc?.review_status === '已审核' && !viewDoc?.synced_to_knowledge ? (
            <Space>
              <Button
                type="primary"
                icon={<SyncOutlined />}
                loading={syncLoading}
                onClick={() => handleSyncToKnowledge(viewDoc!.id)}
              >
                同步至知识库
              </Button>
            </Space>
          ) : null
        }
      >
        <div className="markdown-content" style={{ maxHeight: 500, overflow: 'auto', background: 'rgba(0,0,0,0.025)', padding: 16, borderRadius: 12 }}>
          {viewLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          ) : viewDoc?.content ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{viewDoc.content}</ReactMarkdown>
          ) : (
            <Empty description="文档内容为空" />
          )}
        </div>
      </Modal>
    </div>
  );
}
