import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Input, Select, Tag, Typography, Spin, Empty, Modal, Collapse, Row, Col, Space, Pagination,
} from 'antd';
import {
  SearchOutlined, FileTextOutlined, ShoppingOutlined,
  SafetyCertificateOutlined, QuestionCircleOutlined, BookOutlined,
} from '@ant-design/icons';
import { knowledgeApi } from '../api';

const { Title, Paragraph, Text } = Typography;
const { Search } = Input;

const typeIconMap: Record<string, React.ReactNode> = {
  'FAQ': <QuestionCircleOutlined style={{ fontSize: 32, color: '#0D9488' }} />,
  '商品知识': <ShoppingOutlined style={{ fontSize: 32, color: '#16A34A' }} />,
  '售后政策': <SafetyCertificateOutlined style={{ fontSize: 32, color: '#EA580C' }} />,
};

const typeLabelMap: Record<string, string> = {
  'FAQ': 'FAQ',
  '商品知识': '商品知识',
  '售后政策': '售后政策',
};

const typeColorMap: Record<string, string> = {
  'FAQ': '#0D9488',
  '商品知识': '#16A34A',
  '售后政策': '#EA580C',
};

const mockKnowledgeList = [
  {
    id: 1,
    title: '七天无理由退货政策',
    type: '售后政策',
    tags: ['退货', '政策', '消费者权益'],
    summary: '自签收之日起7天内，商品完好不影响二次销售，可申请无理由退货。',
    content: `## 七天无理由退货政策

### 适用范围
- 自签收之日起7天内
- 商品完好，不影响二次销售
- 包装、配件、赠品齐全

### 不适用情况
- 定制类商品
- 鲜活易腐商品
- 数字化商品
- 交付的报纸、期刊

### 运费承担
- 非商品质量问题：买家承担退货运费
- 商品质量问题：卖家承担往返运费`,
  },
  {
    id: 2,
    title: '如何查询物流信息',
    type: 'FAQ',
    tags: ['物流', '订单', 'FAQ'],
    summary: '在订单详情页可查看实时物流信息，也可通过快递单号在各快递公司官网查询。',
    content: `## 如何查询物流信息

### 方法一：App内查询
1. 进入"我的订单"
2. 找到对应订单
3. 点击"查看物流"

### 方法二：快递官网查询
- 复制快递单号
- 前往对应快递公司官网
- 输入单号进行查询

### 物流异常处理
- 超过48小时未更新：联系客服
- 显示已签收但未收到：联系快递员确认`,
  },
  {
    id: 3,
    title: '商品保修政策说明',
    type: '售后政策',
    tags: ['保修', '售后', '政策'],
    summary: '电子产品享有一年质保，服装鞋帽30天内质量问题可退换。',
    content: `## 商品保修政策

### 电子产品
- 一年全国联保
- 凭购买凭证享受保修服务
- 人为损坏不在保修范围

### 服装鞋帽
- 30天内出现质量问题可退换
- 开线、掉色、缩水等属于质量问题`,
  },
  {
    id: 4,
    title: '优惠券使用常见问题',
    type: 'FAQ',
    tags: ['优惠券', 'FAQ', '使用规则'],
    summary: '优惠券的使用规则、叠加方式、有效期等常见问题解答。',
    content: `## 优惠券使用常见问题

### 基本规则
- 每笔订单限用一张优惠券
- 满减券需满足最低消费金额
- 优惠券不可拆分使用

### 叠加规则
- 优惠券可与满减活动叠加
- 优惠券不能与折扣商品同时使用（部分活动除外）`,
  },
  {
    id: 5,
    title: '热门商品规格对比',
    type: '商品知识',
    tags: ['商品', '对比', '规格'],
    summary: '当前热销商品的规格参数对比，帮助用户快速选择合适的商品。',
    content: `## 热销手机规格对比

| 型号 | 屏幕 | 处理器 | 内存 | 电池 | 价格 |
|------|------|--------|------|------|------|
| A款 | 6.7英寸 | 骁龙8Gen3 | 12GB | 5000mAh | 3999 |
| B款 | 6.5英寸 | 天玑9300 | 8GB | 4800mAh | 3299 |
| C款 | 6.8英寸 | 骁龙8Gen2 | 16GB | 5500mAh | 4599 |`,
  },
  {
    id: 6,
    title: '退换货地址及流程',
    type: '售后政策',
    tags: ['退货', '换货', '地址', '流程'],
    summary: '各品类商品的退换货地址及详细操作流程。',
    content: `## 退换货地址

### 电子产品类
- 收件人：XX电商售后部
- 地址：XX市XX区XX路XX号
- 电话：400-XXX-XXXX

### 服装类
- 收件人：XX电商服装售后
- 地址：XX市XX区XX大道XX号
- 电话：400-XXX-XXXX

### 退换货流程
1. 在订单页申请退换货
2. 等待审核（1-2个工作日）
3. 审核通过后寄回商品
4. 仓库签收后处理退款/换货`,
  },
];

export default function KnowledgePage() {
  const [list, setList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined);
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [activeKeys, setActiveKeys] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [total, setTotal] = useState(0);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: pageSize };
      if (keyword) params.keyword = keyword;
      if (typeFilter) params.type = typeFilter;
      const res: any = await knowledgeApi.list(params);
      const data = res.data || res;
      setList(data.items || []);
      setTotal(data.total || 0);
    } catch {
      // API 失败时清空列表显空状态
      setList([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [keyword, typeFilter, page, pageSize]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 筛选条件变化时重置到第 1 页
  const handleSearch = (value: string) => {
    setKeyword(value);
    setPage(1);
  };

  const handleTypeChange = (val: string | undefined) => {
    setTypeFilter(val);
    setPage(1);
  };

  const handleCardClick = (item: any) => {
    setSelectedItem(item);
    setModalOpen(true);
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>知识库</Title>

      {/* Search and Filter */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <Search
            placeholder="搜索知识库..."
            allowClear
            style={{ width: 320 }}
            onSearch={handleSearch}
            enterButton={<><SearchOutlined /> 搜索</>}
          />
          <Select
            placeholder="类型筛选"
            allowClear
            style={{ width: 150 }}
            value={typeFilter}
            onChange={handleTypeChange}
            options={[
              { label: 'FAQ', value: 'FAQ' },
              { label: '商品知识', value: '商品知识' },
              { label: '售后政策', value: '售后政策' },
            ]}
          />
        </Space>
      </Card>

      {/* Knowledge Cards */}
      <Spin spinning={loading}>
        {list.length > 0 ? (
          <Row gutter={[16, 16]}>
            {list.map((item) => (
              <Col xs={24} sm={12} lg={8} key={item.id}>
                <Card
                  hoverable
                  onClick={() => handleCardClick(item)}
                  style={{ height: '100%', borderRadius: 8 }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 12 }}>
                    <div style={{ flexShrink: 0, marginTop: 4 }}>
                      {typeIconMap[item.type] || <FileTextOutlined style={{ fontSize: 32 }} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <Title level={5} ellipsis={{ rows: 1 }} style={{ margin: 0 }}>
                        {item.title}
                      </Title>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        {typeLabelMap[item.type] || item.type}
                      </Text>
                    </div>
                  </div>
                  <Paragraph
                    ellipsis={{ rows: 2 }}
                    style={{ color: 'rgba(0,0,0,0.45)', marginBottom: 12, lineHeight: 1.6 }}
                  >
                    {item.summary}
                  </Paragraph>
                  <div>
                    {item.tags?.map((tag: string) => (
                      <Tag key={tag} style={{ marginBottom: 4 }}>{tag}</Tag>
                    ))}
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        ) : (
          <Card>
            <Empty description="未找到相关知识" />
          </Card>
        )}
      </Spin>

      {/* Pagination */}
      {total > pageSize && (
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <Pagination
            current={page}
            pageSize={pageSize}
            total={total}
            showSizeChanger
            pageSizeOptions={['8', '12', '24', '48']}
            showTotal={(t) => `共 ${t} 条`}
            onChange={(p, ps) => {
              setPage(p);
              if (ps !== pageSize) {
                setPageSize(ps);
                setPage(1);
              }
            }}
          />
        </div>
      )}

      {/* Detail Modal */}
      <Modal
        title={
          <Space>
            {selectedItem && typeIconMap[selectedItem.type]}
            <span>{selectedItem?.title}</span>
          </Space>
        }
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={760}
        style={{ top: 40 }}
      >
        {selectedItem && (
          <>
            <div style={{ marginBottom: 16 }}>
              {selectedItem.tags?.map((tag: string) => (
                <Tag key={tag} color="blue">{tag}</Tag>
              ))}
              <Tag color={typeColorMap[selectedItem.type] || 'default'}>
                {typeLabelMap[selectedItem.type] || selectedItem.type}
              </Tag>
            </div>
            <div style={{
              background: 'rgba(0,0,0,0.02)',
              padding: '16px 20px',
              borderRadius: 8,
              lineHeight: 1.8,
              maxHeight: '60vh',
              overflowY: 'auto',
            }}>
              <pre style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                fontFamily: 'inherit',
                fontSize: 14,
                margin: 0,
              }}>
                {selectedItem.content}
              </pre>
            </div>
          </>
        )}
      </Modal>
    </div>
  );
}
