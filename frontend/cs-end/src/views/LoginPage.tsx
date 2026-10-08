import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Typography } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import useAuthStore from '../stores/authStore';

const { Title, Text } = Typography;

export default function LoginPage() {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { login, loading } = useAuthStore();
  const [errorMsg, setErrorMsg] = useState('');
  const [mounted, setMounted] = useState(false);

  useEffect(() => { requestAnimationFrame(() => setMounted(true)); }, []);

  const onFinish = async (values: { username: string; password: string }) => {
    setErrorMsg('');
    try {
      await login(values.username, values.password);
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.detail || '登录失败，请检查用户名和密码';
      setErrorMsg(msg);
    }
  };

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100dvh', background: '#FDFBF7', position: 'relative', overflow: 'hidden',
      fontFamily: '"Plus Jakarta Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
      padding: 24,
    }}>
      {/* Grain */}
      <div style={{
        position: 'fixed', inset: 0, zIndex: 100, pointerEvents: 'none', opacity: 0.025,
        backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
        backgroundSize: '256px 256px',
      }} />

      {/* Soft ambient orbs */}
      <div style={{ position: 'fixed', borderRadius: '50%', filter: 'blur(140px)', pointerEvents: 'none', zIndex: 0,
        width: 600, height: 600, top: -200, right: -150,
        background: 'radial-gradient(circle, rgba(20,184,166,0.10), transparent 70%)' }} />
      <div style={{ position: 'fixed', borderRadius: '50%', filter: 'blur(140px)', pointerEvents: 'none', zIndex: 0,
        width: 500, height: 500, bottom: -180, left: -120,
        background: 'radial-gradient(circle, rgba(59,130,246,0.06), transparent 70%)' }} />

      {/* Double-Bezel Shell */}
      <div style={{
        position: 'relative', zIndex: 1, width: 420, borderRadius: '2rem', padding: '1px',
        background: 'linear-gradient(135deg, rgba(0,0,0,0.06), rgba(0,0,0,0.02))',
        boxShadow: '0 8px 60px rgba(0,0,0,0.06), 0 2px 12px rgba(0,0,0,0.04)',
        opacity: mounted ? 1 : 0, transform: mounted ? 'translateY(0)' : 'translateY(24px)',
        filter: mounted ? 'blur(0)' : 'blur(4px)',
        transition: 'all 0.9s cubic-bezier(0.32,0.72,0,1)',
      }}>
        {/* Card Core */}
        <div style={{
          borderRadius: 'calc(2rem - 4px)', padding: '44px 40px 36px',
          background: 'rgba(255,255,255,0.88)', backdropFilter: 'blur(40px)',
          border: '1px solid rgba(0,0,0,0.05)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.8)',
        }}>
          {/* Logo */}
          <div style={{
            width: 72, height: 72, borderRadius: 18, margin: '0 auto 20px',
            background: 'rgba(20,184,166,0.08)', border: '1px solid rgba(20,184,166,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            opacity: mounted ? 1 : 0, transform: mounted ? 'scale(1)' : 'scale(0.8)',
            transition: 'all 0.7s cubic-bezier(0.32,0.72,0,1) 0.15s',
          }}>
            <span style={{ fontSize: 34 }}>🎧</span>
          </div>

          {/* Branding */}
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
            <Title level={2} style={{
              margin: 0, fontWeight: 800, letterSpacing: '-0.02em', fontSize: 26,
              background: 'linear-gradient(135deg, #0D9488, #2563EB)',
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
              opacity: mounted ? 1 : 0, transform: mounted ? 'none' : 'translateY(8px)',
              transition: 'all 0.7s cubic-bezier(0.32,0.72,0,1) 0.25s',
            }}>聆客 · 客服工作台</Title>
            <Text style={{
              color: 'rgba(0,0,0,0.35)', fontSize: 13,
              opacity: mounted ? 1 : 0, transition: 'opacity 0.7s ease 0.35s',
            }}>LingKe — Customer Service Platform</Text>
          </div>

          {/* Error */}
          {errorMsg && (
            <div style={{
              background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 12,
              padding: '10px 16px', marginBottom: 20, color: '#DC2626', fontSize: 13,
            }}>
              {errorMsg}
            </div>
          )}

          {/* Form */}
          <div style={{ opacity: mounted ? 1 : 0, transition: 'opacity 0.7s ease 0.45s' }}>
            <Form form={form} name="login" onFinish={onFinish} autoComplete="off" size="large">
              <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
                <Input
                  prefix={<UserOutlined style={{ color: 'rgba(0,0,0,0.25)' }} />}
                  placeholder="用户名"
                  style={{
                    background: 'rgba(0,0,0,0.03)', border: '1px solid rgba(0,0,0,0.08)',
                    borderRadius: 14, color: '#1a1a1a', height: 48, fontSize: 15,
                  }}
                  styles={{
                    input: { background: 'transparent', color: '#1a1a1a' },
                  }}
                />
              </Form.Item>

              <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }]}>
                <Input.Password
                  prefix={<LockOutlined style={{ color: 'rgba(0,0,0,0.25)' }} />}
                  placeholder="密码"
                  style={{
                    background: 'rgba(0,0,0,0.03)', border: '1px solid rgba(0,0,0,0.08)',
                    borderRadius: 14, color: '#1a1a1a', height: 48, fontSize: 15,
                  }}
                  styles={{
                    input: { background: 'transparent', color: '#1a1a1a' },
                    suffix: { color: 'rgba(0,0,0,0.3)' },
                  }}
                />
              </Form.Item>

              <Form.Item style={{ marginBottom: 12 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  loading={loading}
                  block
                  style={{
                    height: 50, borderRadius: 9999, fontSize: 16, fontWeight: 700,
                    background: 'linear-gradient(135deg, #0D9488, #2563EB)',
                    border: 'none', boxShadow: '0 4px 20px rgba(13,148,136,0.25)',
                    color: '#fff', marginTop: 4,
                  }}
                >
                  {loading ? '登录中...' : '登 录'}
                  {!loading && (
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                      width: 26, height: 26, borderRadius: '50%', background: 'rgba(255,255,255,0.25)',
                      marginLeft: 10, transition: 'transform 0.5s cubic-bezier(0.32,0.72,0,1)',
                    }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                    </span>
                  )}
                </Button>
              </Form.Item>
            </Form>
          </div>

          <div style={{ textAlign: 'center' }}>
            <Text style={{
              color: 'rgba(0,0,0,0.25)', fontSize: 12,
              opacity: mounted ? 1 : 0, transition: 'opacity 0.7s ease 0.6s',
            }}>
              聆客 · 客服人员专用入口
            </Text>
          </div>
        </div>
      </div>
    </div>
  );
}
