import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { Spin } from 'antd';
import useAuthStore from '../stores/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

export function LoadingSpinner() {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100%',
      minHeight: 200,
    }}>
      <Spin size="large" tip="加载中..." />
    </div>
  );
}

export const routeConfig = [
  { path: '/login', element: 'LoginPage', title: '登录' },
  { path: '/dashboard', element: 'DashboardPage', title: '工作台', protected: true },
  { path: '/conversations', element: 'ConversationListPage', title: '会话管理', protected: true },
  { path: '/conversations/:id', element: 'ConversationDetailPage', title: '会话详情', protected: true },
  { path: '/tickets', element: 'TicketListPage', title: '工单管理', protected: true },
  { path: '/tickets/:id', element: 'TicketDetailPage', title: '工单详情', protected: true },
  { path: '/performance', element: 'PerformancePage', title: '我的绩效', protected: true },
  { path: '/knowledge', element: 'KnowledgePage', title: '知识库', protected: true },
  { path: '/settings', element: 'SettingsPage', title: '系统设置', protected: true },
];
