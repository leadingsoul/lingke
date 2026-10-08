import React, { Suspense, lazy, useState } from 'react';
import { Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { Layout, Menu, Button, Dropdown, Avatar, Spin, ConfigProvider } from 'antd';
import {
  DashboardOutlined,
  MessageOutlined,
  FileTextOutlined,
  BookOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  TrophyOutlined,
} from '@ant-design/icons';
import useAuthStore from './stores/authStore';
import { ProtectedRoute, LoadingSpinner } from './router';

const { Header, Sider, Content } = Layout;

const LoginPage = lazy(() => import('./views/LoginPage'));
const DashboardPage = lazy(() => import('./views/DashboardPage'));
const ConversationListPage = lazy(() => import('./views/ConversationListPage'));
const ConversationDetailPage = lazy(() => import('./views/ConversationDetailPage'));
const TicketListPage = lazy(() => import('./views/TicketListPage'));
const TicketDetailPage = lazy(() => import('./views/TicketDetailPage'));
const PerformancePage = lazy(() => import('./views/PerformancePage'));
const KnowledgePage = lazy(() => import('./views/KnowledgePage'));
const SettingsPage = lazy(() => import('./views/SettingsPage'));

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '工作台' },
  { key: '/conversations', icon: <MessageOutlined />, label: '会话管理' },
  { key: '/tickets', icon: <FileTextOutlined />, label: '工单管理' },
  { key: '/performance', icon: <TrophyOutlined />, label: '我的绩效' },
  { key: '/knowledge', icon: <BookOutlined />, label: '知识库' },
  { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
];

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const [collapsed, setCollapsed] = useState(false);

  const currentKey = '/' + location.pathname.split('/')[1];

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const userMenuItems = [
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', onClick: handleLogout },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        {/* Brand */}
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
        }}>
          <h2 style={{
            margin: 0,
            fontSize: collapsed ? 16 : 18,
            fontWeight: 800,
            letterSpacing: '-0.02em',
            background: collapsed
              ? 'linear-gradient(135deg, #14B8A6, #60A5FA)'
              : 'linear-gradient(135deg, #14B8A6, #60A5FA)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
          }}>
            {collapsed ? '聆' : '聆客 · 客服工作台'}
          </h2>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[currentKey]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'margin-left 0.3s cubic-bezier(0.32,0.72,0,1)' }}>
        <Header style={{
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 9,
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16, width: 48, height: 48 }}
          />
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
              <Avatar
                icon={<UserOutlined />}
                style={{
                  background: 'linear-gradient(135deg, #0D9488, #2563EB)',
                  boxShadow: '0 2px 8px rgba(13,148,136,0.3)',
                }}
              />
              <span style={{ fontWeight: 500, color: 'var(--text)' }}>
                {user?.display_name || user?.username || '客服人员'}
              </span>
            </div>
          </Dropdown>
        </Header>
        <Content>
          <Suspense fallback={<LoadingSpinner />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
              <Route path="/conversations" element={<ProtectedRoute><ConversationListPage /></ProtectedRoute>} />
              <Route path="/conversations/:id" element={<ProtectedRoute><ConversationDetailPage /></ProtectedRoute>} />
              <Route path="/tickets" element={<ProtectedRoute><TicketListPage /></ProtectedRoute>} />
              <Route path="/tickets/:id" element={<ProtectedRoute><TicketDetailPage /></ProtectedRoute>} />
              <Route path="/performance" element={<ProtectedRoute><PerformancePage /></ProtectedRoute>} />
              <Route path="/knowledge" element={<ProtectedRoute><KnowledgePage /></ProtectedRoute>} />
              <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </Suspense>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();

  if (location.pathname === '/login') {
    return (
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#0D9488',
            colorInfo: '#0D9488',
            colorSuccess: '#16A34A',
            colorWarning: '#EA580C',
            colorError: '#DC2626',
            borderRadius: 8,
            fontFamily: '"Plus Jakarta Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
            colorBgContainer: '#FFFFFF',
            colorBorderSecondary: 'rgba(0,0,0,0.06)',
          },
        }}
      >
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
          </Routes>
        </Suspense>
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#0D9488',
          colorInfo: '#0D9488',
          colorSuccess: '#16A34A',
          colorWarning: '#EA580C',
          colorError: '#DC2626',
          borderRadius: 8,
          fontFamily: '"Plus Jakarta Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
          colorBgContainer: '#FFFFFF',
          colorBorderSecondary: 'rgba(0,0,0,0.06)',
        },
      }}
    >
      <AppLayout />
    </ConfigProvider>
  );
}
