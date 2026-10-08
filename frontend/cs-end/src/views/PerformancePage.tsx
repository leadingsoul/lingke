import React, { useEffect, useState, useCallback } from 'react';
import { Row, Col, Card, Statistic, Spin, Empty, Typography, Progress, message } from 'antd';
import {
  CheckCircleOutlined,
  MessageOutlined,
  AuditOutlined,
  ClockCircleOutlined,
  StarOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { statsApi } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';

const { Title } = Typography;

interface PerformanceData {
  today_handled: number;
  today_replies: number;
  today_reviews: number;
  total_handled: number;
  total_conversations: number;
  avg_response_time: string;
  satisfaction_rate: number;
  satisfaction_count: number;
}

export default function PerformancePage() {
  const [data, setData] = useState<PerformanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const ws = useWebSocket();

  const fetchData = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res: any = await statsApi.myPerformance();
      setData(res.data || res);
    } catch {
      // network error — keep null
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // WS 监听：消费者评分后自动刷新满意度
  useEffect(() => {
    const handler = (_data: any) => {
      fetchData(true); // 静默刷新，不显示 loading
      message.success('收到新的客户评价，满意度已更新');
    };
    ws.on('rating_update', handler);
    return () => ws.off('rating_update', handler);
  }, [ws, fetchData]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="加载绩效数据..." />
      </div>
    );
  }

  if (!data) {
    return <Empty description="暂无绩效数据" />;
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>我的绩效</Title>

      {/* 今日概览 */}
      <Title level={5} style={{ marginBottom: 16, color: 'rgba(0,0,0,0.45)' }}>📅 今日概览</Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={8}>
          <Card hoverable>
            <Statistic
              title="今日处理总量"
              value={data.today_handled}
              prefix={<CheckCircleOutlined style={{ color: '#0D9488' }} />}
              valueStyle={{ color: '#0D9488' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card hoverable>
            <Statistic
              title="今日回复"
              value={data.today_replies}
              prefix={<MessageOutlined style={{ color: '#16A34A' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card hoverable>
            <Statistic
              title="今日审核"
              value={data.today_reviews}
              prefix={<AuditOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 累计统计 */}
      <Title level={5} style={{ marginBottom: 16, color: 'rgba(0,0,0,0.45)' }}>📊 累计统计</Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="累计处理量"
              value={data.total_handled}
              prefix={<CheckCircleOutlined style={{ color: '#0D9488' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="服务会话数"
              value={data.total_conversations}
              prefix={<TeamOutlined style={{ color: '#722ed1' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="平均响应时间"
              value={data.avg_response_time}
              prefix={<ClockCircleOutlined style={{ color: '#13c2c2' }} />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <div style={{ marginBottom: 4 }}>
              <span style={{ fontSize: 14, color: '#666' }}>
                <StarOutlined style={{ color: '#faad14', marginRight: 4 }} />
                满意度
              </span>
            </div>
            {data.satisfaction_count > 0 ? (
              <div>
                <span style={{ fontSize: 28, fontWeight: 600, color: '#faad14' }}>
                  {data.satisfaction_rate.toFixed(1)}
                </span>
                <span style={{ fontSize: 14, color: '#999', marginLeft: 4 }}>/ 5.0</span>
                <Progress
                  percent={(data.satisfaction_rate / 5) * 100}
                  showInfo={false}
                  strokeColor="#faad14"
                  size="small"
                  style={{ marginTop: 8 }}
                />
                <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                  共 {data.satisfaction_count} 条评价
                </div>
              </div>
            ) : (
              <div>
                <span style={{ fontSize: 28, fontWeight: 600, color: '#999' }}>—</span>
                <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>暂无评价</div>
              </div>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
