import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card, Input, Button, Tag, Descriptions, Avatar, Spin, Empty,
  Typography, Space, Divider, message, Modal, Row, Col, Badge, Alert,
} from 'antd';
import {
  UserOutlined, SendOutlined, ArrowLeftOutlined, CloseOutlined, DeleteOutlined,
  RobotOutlined, CustomerServiceOutlined, WifiOutlined,
  CheckCircleOutlined, EditOutlined,
} from '@ant-design/icons';
import { conversationApi } from '../api';
import useAuthStore from '../stores/authStore';
import { useWebSocket } from '../hooks/useWebSocket';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface Message {
  id: string | number;
  sender_type: 'system' | 'consumer' | 'staff' | 'ai';
  sender_name?: string;
  content: string;
  image_urls?: string[];
  created_at: string;
}

interface Suggestion {
  id: number | string;
  title: string;
  content: string;
}

interface PendingDraft {
  id: string;
  content: string;
  ai_metadata?: any;
  created_at: string;
}

export default function ConversationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const ws = useWebSocket();

  const [conversation, setConversation] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const DEFAULT_SUGGESTIONS: Suggestion[] = [];
  const [sending, setSending] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>(DEFAULT_SUGGESTIONS);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [pendingDraft, setPendingDraft] = useState<PendingDraft | null>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

  // 将后端返回的字符串数组转为前端 Suggestion 对象数组
  function normalizeSuggestions(data: any): Suggestion[] {
    if (!data || !Array.isArray(data) || data.length === 0) return [];
    return data.map((item: any, idx: number) => {
      if (typeof item === 'string') {
        // 取第一行（通常不超过 20 字）做 title，全文做 content
        const lines = item.split('\n');
        const title = lines[0].slice(0, 20);
        return { id: idx, title, content: item };
      }
      // 已经是对象格式
      return {
        id: item.id ?? idx,
        title: item.title || item.content?.slice(0, 20) || `建议${idx + 1}`,
        content: item.content || item.title || item,
      };
    });
  }

  const fetchConversation = useCallback(async () => {
    if (!id) return;
    try {
      // 后端返回的 body.data 已被拦截器取出，res 即是 data
      const convData: any = await conversationApi.detail(id);
      if (!convData || (!convData.id && !convData.consumer_id)) {
        // API 返回空数据 → 会话不存在
        setConversation(null);
        setMessages([]);
        return;
      }
      const conv = {
        ...convData,
        username: convData.consumer_name || convData.username || '未知用户',
        user_id: convData.consumer_id || convData.user_id,
        intent: convData.intent_level || convData.intent,
        customer_tags: convData.customer_tags || [],
        order_status: convData.order_status || null,
        order_amount: convData.order_amount || 0,
        // 确保落在我们定义的 status map 内
        status: convData.status || 'AI进行中',
        priority: convData.priority || '普通',
      };
      setConversation(conv);
      const normalized = normalizeSuggestions(convData.ai_suggestions);
      if (normalized.length > 0) {
        setSuggestions(normalized);
      }
      if (convData.pending_draft) {
        setPendingDraft(convData.pending_draft);
      } else {
        setPendingDraft(null);
      }

      // 加载消息列表
      const msgRes: any = await conversationApi.messages(id);
      const msgData = msgRes?.data || msgRes;
      setMessages(msgData?.items || msgData || []);
    } catch {
      // API 请求异常 → 会话不存在或无权访问
      setConversation(null);
      setMessages([]);
      message.error('加载会话失败，请返回列表重试');
    } finally {
      setLoading(false);
    }
  }, [id]);

  // 切换会话时重置状态，避免旧会话数据残留
  useEffect(() => {
    setConversation(null);
    setMessages([]);
    setSuggestions(DEFAULT_SUGGESTIONS);
    setPendingDraft(null);
  }, [id]);

  useEffect(() => {
    fetchConversation();
  }, [fetchConversation]);

  // 刷新 AI 建议回复（轻量刷新，不重载整个会话）
  const refreshSuggestions = useCallback(async () => {
    if (!id) return;
    try {
      const convData: any = await conversationApi.detail(id);
      const normalized = normalizeSuggestions(convData?.ai_suggestions);
      if (normalized.length > 0) {
        setSuggestions(normalized);
      }
      // 同步更新 pendingDraft（L2 草稿审批）
      if (convData?.pending_draft) {
        setPendingDraft(convData.pending_draft);
      } else {
        setPendingDraft(null);
      }
    } catch {
      // 静默刷新，失败不影响主流程
    }
  }, [id]);

  // WebSocket: 实时接收新消息，替代原来的 5s HTTP 轮询
  useEffect(() => {
    const handler = (data: any) => {
      // 只处理当前会话的消息
      if (data.conversation_id && data.conversation_id !== id) return
      if (!data.sender_type || !data.content) return

      const newMsg: Message = {
        id: data.id || Date.now(),
        sender_type: data.sender_type,
        sender_name: data.sender_name || (
          data.sender_type === 'ai' ? 'AI助手'
          : data.sender_type === 'consumer' ? (conversation?.username || '用户')
          : (user?.display_name || '客服')
        ),
        content: data.content,
        image_urls: data.image_urls || undefined,
        created_at: data.created_at || new Date().toISOString(),
      }
      setMessages((prev) => {
        // 去重：相同 ID 跳过
        if (prev.some((m) => m.id === newMsg.id)) return prev
        // 去重：上次发送的 staff 消息已本地添加，WS 回显时跳过（近 5s 内相同内容）
        if (newMsg.sender_type === 'staff' && prev.some(
          (m) => m.sender_type === 'staff' && m.content === newMsg.content
          && Math.abs(Date.now() - new Date(m.created_at).getTime()) < 5000
        )) return prev
        return [...prev, newMsg]
      })

      // 收到消费者消息后延迟刷新 AI 建议，确保后端 DB 事务已提交
      if (newMsg.sender_type === 'consumer') {
        setTimeout(() => refreshSuggestions(), 300);
      }
    }

    ws.on('new_message', handler)
    return () => ws.off('new_message', handler)
  }, [id, ws, conversation?.username, user?.display_name, refreshSuggestions])

  // WebSocket: 监听会话状态变更（客服 B 关闭了会话等）
  useEffect(() => {
    const handler = (data: any) => {
      if (data.conversation_id === id && data.status) {
        setConversation((prev: any) => prev ? { ...prev, status: data.status } : prev)
        message.info(`会话状态已更新: ${data.status}`)
      }
    }
    ws.on('conversation_update', handler)
    return () => ws.off('conversation_update', handler)
  }, [id, ws])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 点击输入区域外部时关闭建议列表
  useEffect(() => {
    if (!showSuggestions) return;
    const handler = (e: MouseEvent) => {
      if (inputContainerRef.current && !inputContainerRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showSuggestions]);

  const handleInputFocus = useCallback(async () => {
    if (conversation?.status === '已关闭') return;
    try {
      const convData: any = await conversationApi.detail(id!);
      const normalized = normalizeSuggestions(convData?.ai_suggestions);
      setSuggestions(normalized);
      setShowSuggestions(normalized.length > 0);
      // 同步 pendingDraft
      if (convData?.pending_draft) {
        setPendingDraft(convData.pending_draft);
      }
    } catch { /* ignore */ }
  }, [id, conversation?.status]);

  const handleSend = async () => {
    if (!id || !inputValue.trim() || sending) return;
    setSending(true);
    const content = inputValue.trim();
    try {
      await conversationApi.reply(id, content);
      const tempMsg: Message = {
        id: Date.now(),
        sender_type: 'staff',
        sender_name: user?.display_name || '客服',
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempMsg]);
      setInputValue('');

      // 后端 reply_conversation 已通过 manager.send_personal 推送消息给消费者
      // 不再前端 ws.emit，避免双重推送

      // 发送后刷新 AI 建议（上下文变了，重新生成）
      refreshSuggestions();
    } catch {
      message.error('发送失败，请稍后重试');
    } finally {
      setSending(false);
    }
  };

  const handleClose = () => {
    if (!id) return;
    Modal.confirm({
      title: '确认关闭',
      content: '关闭后该会话将无法继续回复，确定要关闭吗？',
      okText: '确认关闭',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await conversationApi.close(id);
          message.success('会话已关闭');
          navigate('/conversations');
        } catch {
          message.success('会话已关闭');
          navigate('/conversations');
        }
      },
    });
  };

  const handleDelete = () => {
    if (!id) return;
    Modal.confirm({
      title: '确认删除',
      content: `确定要永久删除与 ${conversation?.username || '该用户'} 的会话吗？此操作不可撤销，所有消息记录将被清除。`,
      okText: '确认删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await conversationApi.delete(id);
          message.success('会话已删除');
          navigate('/conversations');
        } catch {
          message.error('删除失败，请稍后重试');
        }
      },
    });
  };

  // L2 草稿审批：一键发送 AI 草稿
  const handleApproveDraft = async () => {
    if (!id || !pendingDraft || sending) return;
    setSending(true);
    const content = pendingDraft.content;
    try {
      await conversationApi.reply(id, content);
      const tempMsg: Message = {
        id: Date.now(),
        sender_type: 'staff',
        sender_name: user?.display_name || '客服',
        content,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempMsg]);
      setPendingDraft(null);
      setConversation((prev: any) => prev ? { ...prev, status: '客服处理中' } : prev);
      message.success('AI 草稿已发送');
      // 发送后刷新 AI 建议
      refreshSuggestions();
    } catch {
      message.error('发送失败，请稍后重试');
    } finally {
      setSending(false);
    }
  };

  // L2 草稿审批：编辑后发送（填入输入框）
  const handleEditDraft = () => {
    if (!pendingDraft) return;
    setInputValue(pendingDraft.content);
    setPendingDraft(null);
  };

  // ====== 文件类型判断辅助函数 ======
  const isImageUrl = (url: string): boolean => {
    const ext = url.split('.').pop()?.split('?')[0]?.toLowerCase() || '';
    return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp'].includes(ext);
  };
  const isVideoUrl = (url: string): boolean => {
    const ext = url.split('.').pop()?.split('?')[0]?.toLowerCase() || '';
    return ['mp4', 'mov', 'webm', 'avi'].includes(ext);
  };
  const fileIconForExt = (ext: string): string => {
    const map: Record<string, string> = {
      pdf: '📄', doc: '📝', docx: '📝', xls: '📊', xlsx: '📊',
      ppt: '📽️', pptx: '📽️', txt: '📃', md: '📃', csv: '📊',
      zip: '📦', rar: '📦',
    };
    return map[ext] || '📎';
  };
  const getExtFromUrl = (url: string): string =>
    url.split('.').pop()?.split('?')[0]?.toLowerCase() || '';

  // ====== 文件附件渲染器 ======
  const renderFileAttachments = (urls: string[], isConsumer: boolean) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6 }}>
      {urls.map((url, i) => {
        if (isImageUrl(url)) {
          return (
            <img
              key={i}
              src={url}
              alt="attachment"
              style={{
                maxWidth: 240, maxHeight: 200, borderRadius: 10,
                objectFit: 'cover', cursor: 'pointer',
              }}
              onClick={() => window.open(url, '_blank')}
            />
          );
        }
        if (isVideoUrl(url)) {
          return (
            <video
              key={i}
              src={url}
              controls
              preload="metadata"
              style={{ maxWidth: 240, maxHeight: 200, borderRadius: 10, background: '#000' }}
            />
          );
        }
        const ext = getExtFromUrl(url);
        const name = decodeURIComponent(url.split('/').pop()?.split('?')[0] || '文件');
        return (
          <a
            key={i}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 14px', borderRadius: 10,
              background: isConsumer ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.04)',
              textDecoration: 'none',
              transition: 'background 0.2s',
            }}
          >
            <span style={{ fontSize: 24 }}>{fileIconForExt(ext)}</span>
            <span style={{
              fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis',
              whiteSpace: 'nowrap', color: isConsumer ? 'rgba(255,255,255,0.85)' : 'rgba(0,0,0,0.55)',
            }}>
              {name}
            </span>
          </a>
        );
      })}
    </div>
  );

  const renderBubble = (msg: Message) => {
    const isSystem = msg.sender_type === 'system';
    const isConsumer = msg.sender_type === 'consumer';
    const isStaff = msg.sender_type === 'staff';
    const isAi = msg.sender_type === 'ai';

    const bubbleClass = isSystem ? 'system-bubble' : isConsumer ? 'consumer-bubble' : isStaff ? 'staff-bubble' : 'ai-bubble';
    // AI 和客服消息用 Markdown 富文本渲染，消费者消息保持纯文本
    const useMarkdown = isAi || isStaff;

    return (
      <div className={`chat-message ${msg.sender_type}`} key={msg.id}>
        {!isSystem && <div className="chat-sender">{msg.sender_name || msg.sender_type}</div>}
        <div className={`chat-bubble ${bubbleClass}`}>
          {useMarkdown ? (
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.content}
            </ReactMarkdown>
          ) : (
            msg.content
          )}
          {msg.image_urls && msg.image_urls.length > 0 && renderFileAttachments(msg.image_urls, isConsumer)}
        </div>
        {!isSystem && (
          <div style={{ fontSize: 11, color: '#bbb', marginTop: 2 }}>
            {dayjs(msg.created_at).format('HH:mm')}
          </div>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="加载会话详情..." />
      </div>
    );
  }

  if (!conversation) {
    return <Empty description="会话不存在" />;
  }

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

  return (
    <div style={{ height: 'calc(100vh - 160px)', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/conversations')}>返回</Button>
          <Title level={5} style={{ margin: 0 }}>
            与 {conversation.username} 的会话
          </Title>
          <Tag color={statusColorMap[conversation.status] || 'default'}>
            {statusLabelMap[conversation.status] || conversation.status}
          </Tag>
          <Tag color={priorityColorMap[conversation.priority] || 'default'}>
            {conversation.priority === '紧急' ? '高优先级' : conversation.priority === '普通' ? '普通' : conversation.priority || '-'}
          </Tag>
          <Badge status={ws.isConnected ? 'success' : 'default'} text={ws.isConnected ? '实时' : '离线'} />
        </Space>
        <Space>
          {conversation.status !== '已关闭' && (
            <Button danger icon={<CloseOutlined />} onClick={handleClose}>关闭会话</Button>
          )}
          <Button danger type="primary" icon={<DeleteOutlined />} onClick={handleDelete}>删除会话</Button>
        </Space>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
        {/* Left: Chat Message Area (70%) */}
        <Card
          style={{ flex: '0 0 70%', display: 'flex', flexDirection: 'column' }}
          bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}
        >
          {/* Messages */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '20px 24px',
            backgroundColor: 'var(--bg-page)',
          }}>
            {messages.length > 0 ? (
              messages.map(renderBubble)
            ) : (
              <Empty description="暂无消息" />
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div
            ref={inputContainerRef}
            style={{
              borderTop: '1px solid #f0f0f0',
              padding: '12px 16px',
              backgroundColor: '#fff',
              position: 'relative',
            }}
          >
            {/* AI 建议回复下拉列表 */}
            {showSuggestions && suggestions.length > 0 && (
              <div style={{
                position: 'absolute',
                bottom: '100%',
                left: 0,
                right: 0,
                backgroundColor: '#fff',
                border: '1px solid #e8e8e8',
                borderRadius: '8px 8px 0 0',
                boxShadow: '0 -4px 12px rgba(0,0,0,0.1)',
                padding: '12px 16px',
                zIndex: 10,
              }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: 10,
                }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <RobotOutlined style={{ marginRight: 4 }} />AI 建议回复
                  </Text>
                  <Button
                    type="text"
                    size="small"
                    onClick={() => setShowSuggestions(false)}
                    style={{ fontSize: 12, padding: 0 }}
                  >
                    收起
                  </Button>
                </div>
                {suggestions.map((s) => (
                  <div
                    key={s.id}
                    onClick={() => {
                      setInputValue(s.content);
                      setShowSuggestions(false);
                    }}
                    style={{
                      padding: '8px 12px',
                      marginBottom: 6,
                      backgroundColor: '#f6f8fa',
                      borderRadius: 6,
                      cursor: 'pointer',
                      fontSize: 13,
                      lineHeight: 1.6,
                      color: '#333',
                      border: '1px solid transparent',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = '#0D9488';
                      e.currentTarget.style.backgroundColor = 'rgba(13,148,136,0.06)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'transparent';
                      e.currentTarget.style.backgroundColor = '#f6f8fa';
                    }}
                  >
                    <div style={{ fontWeight: 500, marginBottom: 2, color: '#0D9488', fontSize: 12 }}>
                      {s.title}
                    </div>
                    <div>{s.content}</div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', gap: 12 }}>
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onFocus={handleInputFocus}
                placeholder="输入回复内容..."
                autoSize={{ minRows: 2, maxRows: 4 }}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                style={{ flex: 1 }}
                disabled={conversation.status === '已关闭'}
              />
              <Space style={{ alignItems: 'flex-start' }}>
                {suggestions.length > 0 && conversation?.status !== '已关闭' && (
                  <Button
                    icon={<RobotOutlined />}
                    onClick={async () => {
                      if (showSuggestions) {
                        setShowSuggestions(false);
                      } else {
                        try {
                          const convData: any = await conversationApi.detail(id!);
                          const normalized = normalizeSuggestions(convData?.ai_suggestions);
                          setSuggestions(normalized);
                          setShowSuggestions(true);
                        } catch { /* ignore */ }
                      }
                    }}
                    type={showSuggestions ? 'primary' : 'default'}
                    title="AI 建议回复"
                  />
                )}
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  loading={sending}
                  disabled={conversation.status === '已关闭' || !inputValue.trim()}
                  style={{ height: 'auto' }}
                >
                  发送
                </Button>
              </Space>
            </div>
          </div>
        </Card>

        {/* Right: Info Panel (30%) */}
        <div style={{ flex: '0 0 30%', display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto' }}>
          {/* Customer Info */}
          <Card size="small" title="客户信息">
            <Descriptions column={1} size="small" colon={false}>
              <Descriptions.Item label="用户名">{conversation.username}</Descriptions.Item>
              <Descriptions.Item label="用户ID">{conversation.user_id || '-'}</Descriptions.Item>
              <Descriptions.Item label="标签">
                {conversation.customer_tags?.length
                  ? conversation.customer_tags.map((t: string) => <Tag key={t} color="blue">{t}</Tag>)
                  : '-'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* Order Info */}
          <Card size="small" title="关联订单">
            {conversation.order_id ? (
              <Descriptions column={1} size="small" colon={false}>
                <Descriptions.Item label="订单号">{conversation.order_id}</Descriptions.Item>
                <Descriptions.Item label="状态">{conversation.order_status || '-'}</Descriptions.Item>
                <Descriptions.Item label="金额">¥{conversation.order_amount || 0}</Descriptions.Item>
              </Descriptions>
            ) : (
              <Text type="secondary">无关联订单</Text>
            )}
          </Card>

          {/* L2 Pending Draft — AI 草稿待审批 */}
          {pendingDraft && conversation?.status !== '已关闭' && (
            <Card
              size="small"
              style={{ borderColor: '#faad14', backgroundColor: '#fffbe6' }}
              title={<span><RobotOutlined style={{ marginRight: 6, color: '#faad14' }} />AI 草稿待审批</span>}
            >
              <Alert
                message="L2 辅助人工"
                description="AI 已根据用户问题生成了回复草稿，请审核后发送或编辑后再发送。"
                type="warning"
                showIcon
                style={{ marginBottom: 12 }}
              />
              <div style={{
                backgroundColor: '#fff',
                border: '1px solid #f0f0f0',
                borderRadius: 6,
                padding: 12,
                marginBottom: 12,
                fontSize: 13,
                lineHeight: 1.8,
                whiteSpace: 'pre-wrap',
                maxHeight: 200,
                overflowY: 'auto',
              }}>
                {pendingDraft.content}
              </div>
              <Space>
                <Button
                  type="primary"
                  icon={<CheckCircleOutlined />}
                  onClick={handleApproveDraft}
                  loading={sending}
                  size="small"
                >
                  发送
                </Button>
                <Button
                  icon={<EditOutlined />}
                  onClick={handleEditDraft}
                  size="small"
                >
                  编辑后发送
                </Button>
              </Space>
            </Card>
          )}

        </div>
      </div>
    </div>
  );
}
