import React, { useState, useEffect } from "react";
import apiClient, { type UsageLog } from "../api/client";

interface Agent {
  id: number;
  did: string;
  name: string;
  agent_type: string;
  per_call_limit: string;
  daily_limit: string;
  is_active: boolean;
  created_at: string;
}

const AGENT_TYPES = ["chat", "image", "music", "custom"];

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [usage, setUsage] = useState<UsageLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ did: "", name: "", agentType: "chat" });
  const [submitting, setSubmitting] = useState(false);

  const loadData = async () => {
    try {
      const usageData = await apiClient.getUsage(100);
      setUsage(usageData);
      // Agent list from API not in client yet, just show usage
      setAgents([]);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.did || !formData.name) return;
    setSubmitting(true);
    try {
      await apiClient.registerAgent(formData.did, formData.name, formData.agentType);
      setFormData({ did: "", name: "", agentType: "chat" });
      setShowForm(false);
      await loadData();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="page-loading">加载中...</div>;

  const totalCost = usage.reduce((sum, u) => sum + parseFloat(u.cost_user), 0);
  const anomalousCount = usage.filter((u) => u.is_anomalous).length;

  return (
    <div className="agents-page">
      <div className="page-header">
        <h2>我的 Agent</h2>
        <button className="primary-btn" onClick={() => setShowForm(!showForm)}>
          {showForm ? "取消" : "注册 Agent"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showForm && (
        <form className="agent-form" onSubmit={handleSubmit}>
          <h3>注册新 Agent</h3>
          <div className="form-group">
            <label>DID</label>
            <input
              type="text"
              value={formData.did}
              onChange={(e) => setFormData({ ...formData, did: e.target.value })}
              placeholder="agent:xxxx"
              required
            />
          </div>
          <div className="form-group">
            <label>名称</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="我的助手"
              required
            />
          </div>
          <div className="form-group">
            <label>类型</label>
            <select
              value={formData.agentType}
              onChange={(e) => setFormData({ ...formData, agentType: e.target.value })}
            >
              {AGENT_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="primary-btn" disabled={submitting}>
            {submitting ? "注册中..." : "注册"}
          </button>
        </form>
      )}

      <div className="stats-row">
        <div className="stat-card">
          <span className="stat-label">总调用</span>
          <span className="stat-value">{usage.length}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">总费用</span>
          <span className="stat-value">¥{totalCost.toFixed(4)}</span>
        </div>
        <div className="stat-card warning">
          <span className="stat-label">异常调用</span>
          <span className="stat-value">{anomalousCount}</span>
        </div>
      </div>

      <div className="usage-section">
        <h3>用量明细</h3>
        {usage.length === 0 ? (
          <p className="empty-state">暂无用量记录</p>
        ) : (
          <table className="usage-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>Provider</th>
                <th>模型</th>
                <th>输入 tokens</th>
                <th>输出 tokens</th>
                <th>费用</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {usage.slice(0, 50).map((log) => (
                <tr key={log.id} className={log.is_anomalous ? "anomalous-row" : ""}>
                  <td>{new Date(log.created_at).toLocaleString("zh-CN")}</td>
                  <td>{log.provider}</td>
                  <td>{log.model}</td>
                  <td>{log.input_tokens.toLocaleString()}</td>
                  <td>{log.output_tokens.toLocaleString()}</td>
                  <td>¥{parseFloat(log.cost_user).toFixed(4)}</td>
                  <td>
                    {log.is_anomalous ? (
                      <span className="badge badge-danger" title={log.anomaly_reason || ""}>
                        异常
                      </span>
                    ) : (
                      <span className="badge badge-ok">正常</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
