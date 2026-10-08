import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuthStore } from '../stores/authStore';

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((s) => s.login);
  const token = useAuthStore((s) => s.token);

  useEffect(() => { requestAnimationFrame(() => setMounted(true)); }, []);

  if (token) {
    const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';
    navigate(from, { replace: true });
    return null;
  }

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      message.success('登录成功');
      const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';
      navigate(from, { replace: true });
    } catch {
      // error handled by interceptor
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={`login-container ${mounted ? 'login-mounted' : ''}`}>
      {/* Grain */}
      <div className="login-grain" />

      {/* Soft ambient orbs */}
      <div className="login-orb login-orb-1" />
      <div className="login-orb login-orb-2" />

      {/* Double-Bezel Card Shell */}
      <div className="login-shell">
        <div className="login-core">
          {/* Logo */}
          <div className="login-mark">
            <span className="login-mark-icon">🎧</span>
          </div>

          <h1 className="login-brand">聆客 · 管理端</h1>
          <p className="login-brand-sub">LingKe — Admin Dashboard</p>

          <Form
            name="login"
            size="large"
            onFinish={onFinish}
            autoComplete="off"
            initialValues={{ username: '', password: '' }}
            className="login-form"
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input
                prefix={<UserOutlined className="login-input-icon" />}
                placeholder="用户名"
                className="login-input-glass"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined className="login-input-icon" />}
                placeholder="密码"
                className="login-input-glass"
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
                className="login-btn"
              >
                {loading ? '登录中...' : '登 录'}
                {!loading && <span className="login-btn-arrow" />}
              </Button>
            </Form.Item>
          </Form>

          <p className="login-footer-text">聆客 · 管理员专用入口</p>
        </div>
      </div>
    </div>
  );
}
