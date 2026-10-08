import { useEffect, useState } from 'react';
import {
  Tabs, DatePicker, Button, Row, Col, Card, Statistic,
  message, Spin, Alert, Empty, Table, Space,
} from 'antd';
import { DownloadOutlined, ReloadOutlined, ThunderboltOutlined, FileTextOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import dayjs from 'dayjs';
import { statsApi, aiInsightApi, ChartStats } from '../api';
import type { Dayjs } from 'dayjs';

const { RangePicker } = DatePicker;

export default function StatisticsPage() {
  const [stats, setStats] = useState<ChartStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);
  const [activeTab, setActiveTab] = useState('satisfaction');

  // AI 洞察状态
  const [aiMarkdown, setAiMarkdown] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { start_date?: string; end_date?: string } = {};
      if (dateRange) {
        params.start_date = dateRange[0];
        params.end_date = dateRange[1];
      }
      const data = await statsApi.getCharts(params);
      setStats(data);
    } catch {
      setError('加载统计数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, [dateRange]);

  const handleExport = async () => {
    // AI 洞察 Tab 不支持数据导出，切换为满意度导出
    const exportType = activeTab === 'ai_insight' ? 'satisfaction' : activeTab;
    try {
      const data: { type: string; format: string; start_date?: string; end_date?: string } = {
        type: exportType === 'product_eval' ? 'product_eval' : exportType,
        format: 'xlsx',
      };
      if (dateRange) {
        data.start_date = dateRange[0];
        data.end_date = dateRange[1];
      }
      const blob: Blob = await statsApi.export(data) as unknown as Blob;
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const typeLabels: Record<string, string> = {
        satisfaction: '服务评价', performance: '绩效',
        hot_topics: '热点', product_eval: '商品评价',
      };
      a.download = `统计导出_${typeLabels[activeTab] || activeTab}_${dayjs().format('YYYYMMDD')}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch {
      message.error('导出失败');
    }
  };

  const handleAIInsight = async () => {
    setAiLoading(true);
    setAiError(null);
    setAiMarkdown(null);
    try {
      const params: { start_date?: string; end_date?: string } = {};
      if (dateRange) {
        params.start_date = dateRange[0];
        params.end_date = dateRange[1];
      }
      const result = await aiInsightApi.get(params);
      setAiMarkdown(result.markdown);
    } catch {
      setAiError('AI 分析失败，请稍后重试');
    } finally {
      setAiLoading(false);
    }
  };

  const handleExportReport = () => {
    if (!aiMarkdown) return;
    const blob = new Blob([aiMarkdown], { type: 'text/markdown;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `AI评价洞察报告_${dayjs().format('YYYYMMDD_HHmm')}.md`;
    a.click();
    window.URL.revokeObjectURL(url);
    message.success('报告已下载');
  };

  // ── Chart configurations ──

  const satisfactionOption = stats?.satisfaction_stats ? {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      name: '满意度分布', type: 'pie', radius: ['40%', '70%'],
      data: stats.satisfaction_stats.map((d) => ({
        name: `${d.rating}星`, value: d.count,
      })),
      label: { show: true, formatter: '{b}: {c}' },
      emphasis: { label: { fontSize: 16, fontWeight: 'bold' } },
    }],
  } : null;

  const ticketDistributionOption = stats?.ticket_distribution ? {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: stats.ticket_distribution.map((d) => d.type) },
    yAxis: { type: 'value' },
    series: [{
      name: '工单数', type: 'bar',
      data: stats.ticket_distribution.map((d) => d.count),
      itemStyle: { color: '#0D9488' },
      barMaxWidth: 50,
    }],
  } : null;

  const agentPerformanceOption = stats?.agent_performance ? {
    tooltip: { trigger: 'axis' },
    legend: { data: ['评价数', '均分'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: stats.agent_performance.map((d) => d.name) },
    yAxis: [
      { type: 'value', name: '评价数' },
      { type: 'value', name: '均分', min: 0, max: 5 },
    ],
    series: [
      {
        name: '评价数', type: 'bar',
        data: stats.agent_performance.map((d) => d.handled),
        itemStyle: { color: '#0D9488' },
      },
      {
        name: '均分', type: 'line', yAxisIndex: 1,
        data: stats.agent_performance.map((d) => d.satisfaction),
        lineStyle: { color: '#52C41A' },
        symbol: 'circle', symbolSize: 8,
      },
    ],
  } : null;

  const hotTopicsOption = stats?.hot_topics ? {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: {
      type: 'category',
      data: [...stats.hot_topics].reverse().map((d) => d.topic),
    },
    series: [{
      name: '出现次数', type: 'bar',
      data: [...stats.hot_topics].reverse().map((d) => d.count),
      itemStyle: { color: '#FA8C16', borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right' },
    }],
  } : null;

  // 商品评分横向柱状图
  const productRatingOption = stats?.product_ratings?.length ? {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
    yAxis: {
      type: 'category',
      data: [...stats.product_ratings].reverse().map((d) =>
        d.product_name.length > 10 ? d.product_name.slice(0, 10) + '...' : d.product_name
      ),
    },
    xAxis: { type: 'value', name: '均分', min: 0, max: 5 },
    series: [{
      name: '商品均分', type: 'bar',
      data: [...stats.product_ratings].reverse().map((d) => d.avg_rating),
      itemStyle: {
        color: '#0D9488',
        borderRadius: [0, 4, 4, 0],
      },
      label: { show: true, position: 'right', formatter: '{c}' },
    }],
  } : null;

  // 情感趋势面积图
  const sentimentTrendOption = stats?.sentiment_trend ? {
    tooltip: { trigger: 'axis' },
    legend: { data: ['正面', '中性', '负面'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: stats.sentiment_trend.map((d) => d.date.slice(5)) },
    yAxis: { type: 'value' },
    series: [
      {
        name: '正面', type: 'line', stack: 'total', areaStyle: {},
        data: stats.sentiment_trend.map((d) => d.positive),
        itemStyle: { color: '#52C41A' },
      },
      {
        name: '中性', type: 'line', stack: 'total', areaStyle: {},
        data: stats.sentiment_trend.map((d) => d.neutral),
        itemStyle: { color: '#FAAD14' },
      },
      {
        name: '负面', type: 'line', stack: 'total', areaStyle: {},
        data: stats.sentiment_trend.map((d) => d.negative),
        itemStyle: { color: '#FF4D4F' },
      },
    ],
  } : null;

  // ── Computed ──

  const totalSatisfaction = stats?.satisfaction_stats?.reduce((sum, d) => sum + d.count, 0) || 0;
  const totalTickets = stats?.ticket_distribution?.reduce((sum, d) => sum + d.count, 0) || 0;
  const avgSatisfaction = stats?.agent_performance?.length
    ? (stats.agent_performance.reduce((sum, d) => sum + d.satisfaction, 0) / stats.agent_performance.length).toFixed(1)
    : '0';
  const totalHotTopics = stats?.hot_topics?.reduce((sum, d) => sum + d.count, 0) || 0;
  const totalProductEvals = stats?.product_ratings?.reduce((sum, d) => sum + d.count, 0) || 0;
  const topProduct = stats?.product_ratings?.[0];

  // 商品评价表格列
  const productColumns = [
    { title: '商品名称', dataIndex: 'product_name', key: 'product_name', ellipsis: true },
    { title: '均分', dataIndex: 'avg_rating', key: 'avg_rating', width: 80, sorter: (a: any, b: any) => a.avg_rating - b.avg_rating },
    { title: '评价数', dataIndex: 'count', key: 'count', width: 80, sorter: (a: any, b: any) => a.count - b.count },
  ];

  // ── Tab configuration ──

  const tabItems = [
    {
      key: 'satisfaction',
      label: '服务评价',
      children: (
        <div>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={12} lg={6}><Card><Statistic title="总评价数" value={totalSatisfaction} /></Card></Col>
            <Col xs={24} sm={12} lg={6}><Card><Statistic title="总工单数" value={totalTickets} /></Card></Col>
            <Col xs={24} sm={12} lg={6}><Card><Statistic title="客服均分" value={avgSatisfaction} suffix="分" /></Card></Col>
            <Col xs={24} sm={12} lg={6}><Card><Statistic title="热点主题数" value={totalHotTopics} /></Card></Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={12}>
              <Card title="满意度分布" style={{ marginBottom: 16 }}>
                <div style={{ height: 350 }}>
                  {satisfactionOption && <ReactECharts option={satisfactionOption} style={{ height: '100%' }} />}
                </div>
              </Card>
            </Col>
            <Col xs={24} lg={12}>
              <Card title="工单类型分布" style={{ marginBottom: 16 }}>
                <div style={{ height: 350 }}>
                  {ticketDistributionOption && <ReactECharts option={ticketDistributionOption} style={{ height: '100%' }} />}
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      ),
    },
    {
      key: 'product_eval',
      label: '商品评价',
      children: (
        <div>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={24} sm={8}><Card><Statistic title="已评价商品数" value={stats?.product_ratings?.length || 0} /></Card></Col>
            <Col xs={24} sm={8}><Card><Statistic title="评价总量" value={totalProductEvals} /></Card></Col>
            <Col xs={24} sm={8}>
              <Card>
                <Statistic
                  title="最高分商品"
                  value={topProduct?.product_name ? (topProduct.product_name.length > 12 ? topProduct.product_name.slice(0, 12) + '…' : topProduct.product_name) : '—'}
                  suffix={topProduct ? `${topProduct.avg_rating}分` : ''}
                />
              </Card>
            </Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <Card title="商品评分排行" style={{ marginBottom: 16 }}>
                <div style={{ height: 450 }}>
                  {productRatingOption && <ReactECharts option={productRatingOption} style={{ height: '100%' }} />}
                </div>
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card title="评价明细" style={{ marginBottom: 16 }}>
                <Table
                  dataSource={stats?.product_ratings || []}
                  columns={productColumns}
                  rowKey="product_name"
                  size="small"
                  pagination={{ pageSize: 8 }}
                  scroll={{ y: 380 }}
                />
              </Card>
            </Col>
          </Row>
        </div>
      ),
    },
    {
      key: 'performance',
      label: '客服绩效',
      children: (
        <div>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col span={24}><Card><Statistic title="客服均分" value={avgSatisfaction} suffix="分" /></Card></Col>
          </Row>
          <Card title="客服绩效对比">
            <div style={{ height: 400 }}>
              {agentPerformanceOption && <ReactECharts option={agentPerformanceOption} style={{ height: '100%' }} />}
            </div>
          </Card>
        </div>
      ),
    },
    {
      key: 'hot_topics',
      label: '热点问题',
      children: (
        <div>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col span={24}><Card><Statistic title="热点出现总次数" value={totalHotTopics} /></Card></Col>
          </Row>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <Card title="评价热点主题">
                <div style={{ height: 400 }}>
                  {hotTopicsOption && <ReactECharts option={hotTopicsOption} style={{ height: '100%' }} />}
                </div>
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card title="情感趋势（近30天）" style={{ marginBottom: 16 }}>
                <div style={{ height: 400 }}>
                  {sentimentTrendOption && <ReactECharts option={sentimentTrendOption} style={{ height: '100%' }} />}
                </div>
              </Card>
            </Col>
          </Row>
        </div>
      ),
    },
    {
      key: 'ai_insight',
      label: 'AI 洞察',
      children: (
        <div>
          <Card style={{ marginBottom: 16 }}>
            <Space>
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={handleAIInsight}
                loading={aiLoading}
              >
                开始分析
              </Button>
              {aiMarkdown && (
                <Button icon={<FileTextOutlined />} onClick={handleExportReport}>
                  导出报告
                </Button>
              )}
            </Space>
            <span style={{ marginLeft: 12, color: 'rgba(0,0,0,0.35)', fontSize: 13 }}>
              分析所选时间范围内的评价数据，生成 AI 洞察报告
            </span>
          </Card>

          {aiError && <Alert type="error" message={aiError} showIcon style={{ marginBottom: 16 }} />}

          <Spin spinning={aiLoading} tip="AI 正在分析评价数据，请稍候...">
            {aiMarkdown ? (
              <Card>
                <div style={{ padding: '16px 8px', lineHeight: 1.8, fontSize: 15 }} className="ai-insight-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{aiMarkdown}</ReactMarkdown>
                </div>
              </Card>
            ) : !aiLoading ? (
              <Empty description="点击「开始分析」让 AI 解读评价数据" />
            ) : null}
          </Spin>
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
        <RangePicker
          onChange={(dates) => {
            if (dates?.[0] && dates?.[1]) {
              setDateRange([dates[0].format('YYYY-MM-DD'), dates[1].format('YYYY-MM-DD')]);
            } else {
              setDateRange(null);
            }
          }}
          placeholder={['开始日期', '结束日期']}
        />
        <Button icon={<ReloadOutlined />} onClick={fetchStats}>
          刷新
        </Button>
        <Button type="primary" icon={<DownloadOutlined />} onClick={handleExport}>
          导出报表
        </Button>
      </div>

      {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}

      <Spin spinning={loading}>
        {stats ? (
          <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
        ) : !loading && !error ? (
          <Empty description="暂无统计数据" />
        ) : null}
      </Spin>
    </div>
  );
}
