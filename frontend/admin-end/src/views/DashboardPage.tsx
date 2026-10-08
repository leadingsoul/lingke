import { useEffect, useState, useCallback } from 'react';
import { Row, Col, Card, Statistic, Spin, Alert, Badge } from 'antd';
import {
  MessageOutlined,
  ToolOutlined,
  TeamOutlined,
  UserOutlined,
  StarOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { dashboardApi, DashboardStats } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';

const AUTO_REFRESH_MS = 60000; // WebSocket 实时推送时，HTTP 轮询降级到 60s

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const ws = useWebSocket();

  const fetchStats = useCallback(async () => {
    try {
      setError(null);
      const data = await dashboardApi.getStats();
      setStats(data);
    } catch {
      setError('加载仪表盘数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const timer = setInterval(fetchStats, AUTO_REFRESH_MS);
    return () => clearInterval(timer);
  }, [fetchStats]);

  // WebSocket: 系统通知触发仪表盘刷新
  useEffect(() => {
    const refresh = () => fetchStats()
    ws.on('system_notice', refresh)
    ws.on('ticket_update', refresh)
    return () => {
      ws.off('system_notice', refresh)
      ws.off('ticket_update', refresh)
    }
  }, [ws, fetchStats])

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 120 }}>
        <Spin size="large" tip="加载仪表盘..." />
      </div>
    );
  }

  if (error) {
    return <Alert type="error" message={error} showIcon style={{ margin: 24 }} />;
  }

  if (!stats) {
    return <Alert type="warning" message="暂无数据" showIcon style={{ margin: 24 }} />;
  }

  const consultationOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: stats.consultation_trend?.map((d) => d.date) || [],
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: '咨询数',
        type: 'line',
        data: stats.consultation_trend?.map((d) => d.count) || [],
        smooth: true,
        lineStyle: { color: '#0D9488', width: 2 },
        areaStyle: { color: 'rgba(13,148,136,0.1)' },
      },
    ],
  };

  const ticketOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: stats.ticket_trend?.map((d) => d.date) || [],
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: '工单数',
        type: 'line',
        data: stats.ticket_trend?.map((d) => d.count) || [],
        smooth: true,
        lineStyle: { color: '#FA8C16', width: 2 },
        areaStyle: { color: 'rgba(250,140,22,0.1)' },
      },
    ],
  };

  const sentimentOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['正面', '中性', '负面'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: {
      type: 'category',
      data: stats.sentiment_trend?.map((d) => d.date) || [],
      axisLabel: { rotate: 30 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: '正面',
        type: 'line',
        data: stats.sentiment_trend?.map((d) => d.positive) || [],
        smooth: true,
        lineStyle: { color: '#52C41A' },
      },
      {
        name: '中性',
        type: 'line',
        data: stats.sentiment_trend?.map((d) => d.neutral) || [],
        smooth: true,
        lineStyle: { color: '#0D9488' },
      },
      {
        name: '负面',
        type: 'line',
        data: stats.sentiment_trend?.map((d) => d.negative) || [],
        smooth: true,
        lineStyle: { color: '#FF4D4F' },
      },
    ],
  };

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>系统概览</h2>
        <Badge status={ws.isConnected ? 'success' : 'default'} text={ws.isConnected ? 'WS实时' : 'HTTP'} />
      </div>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <Card className="stat-card" hoverable>
            <Statistic
              title="总用户数"
              value={stats.total_users}
              prefix={<UserOutlined />}
              valueStyle={{ color: '#0D9488' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card className="stat-card" hoverable>
            <Statistic
              title="总咨询数"
              value={stats.total_consultations}
              prefix={<MessageOutlined />}
              valueStyle={{ color: '#0D9488' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card className="stat-card" hoverable>
            <Statistic
              title="总工单量"
              value={stats.total_tickets}
              prefix={<ToolOutlined />}
              valueStyle={{ color: '#FA8C16' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card className="stat-card" hoverable>
            <Statistic
              title="总评价数"
              value={stats.total_evaluations}
              prefix={<StarOutlined />}
              valueStyle={{ color: '#722ED1' }}
              suffix={
                <span style={{ fontSize: 14, color: '#FF4D4F' }}>
                  负面 {stats.negative_sentiment_rate}%
                </span>
              }
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card className="stat-card" hoverable>
            <Statistic
              title="待处理工单"
              value={stats.pending_tickets}
              prefix={<ExclamationCircleOutlined />}
              valueStyle={{ color: '#FF4D4F' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card className="stat-card" hoverable>
            <Statistic
              title="在线客服"
              value={stats.online_agents}
              prefix={<TeamOutlined />}
              valueStyle={{ color: '#52C41A' }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="咨询趋势" hoverable>
            <div className="chart-container">
              <ReactECharts option={consultationOption} style={{ height: '100%' }} />
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="工单趋势" hoverable>
            <div className="chart-container">
              <ReactECharts option={ticketOption} style={{ height: '100%' }} />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card title="情感趋势" hoverable>
            <div className="chart-container">
              <ReactECharts option={sentimentOption} style={{ height: '100%' }} />
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
