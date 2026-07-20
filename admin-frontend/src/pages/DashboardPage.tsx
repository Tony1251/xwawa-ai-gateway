import { useQuery } from "@tanstack/react-query";
import apiClient from "../api/client";

interface Stats {
  total_users: number;
  total_balance: string;
  total_transactions: number;
  active_agents: number;
  recent_transactions: Array<{
    id: number;
    type: string;
    amount: string;
    balance_after: string;
    reference: string | null;
    note: string | null;
    created_at: string;
  }>;
}

async function fetchStats(): Promise<Stats> {
  const raw: any = await apiClient.adminGetStats();
  return {
    total_users: raw.total_users ?? 0,
    total_balance: raw.total_balance ?? "0",
    total_transactions: raw.total_transactions ?? 0,
    active_agents: raw.active_agents ?? 0,
    recent_transactions: raw.recent_transactions ?? [],
  };
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function DashboardPage() {
  const { data, isLoading, isError, error } = useQuery<Stats>({
    queryKey: ["admin-stats"],
    queryFn: fetchStats,
  });

  if (isLoading) {
    return (
      <div className="page-content">
        <div className="loading"><span className="spinner" /></div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-content">
        <div className="card"><p style={{ color: "#ef4444" }}>加载失败: {(error as Error).message}</p></div>
      </div>
    );
  }

  return (
    <div className="page-content">
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>仪表盘</h2>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">总用户数</div>
          <div className="stat-value">{data!.total_users.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">总余额</div>
          <div className="stat-value">¥{parseFloat(data!.total_balance).toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">总交易数</div>
          <div className="stat-value">{data!.total_transactions.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">活跃 Agent</div>
          <div className="stat-value">{data!.active_agents.toLocaleString()}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">最近交易</span>
        </div>
        {data!.recent_transactions.length === 0 ? (
          <p style={{ color: "#888", fontSize: 14, padding: "16px 0" }}>暂无交易记录</p>
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>类型</th>
                  <th>金额</th>
                  <th>余额后</th>
                  <th>备注</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {data!.recent_transactions.map((tx) => (
                  <tr key={tx.id}>
                    <td>{tx.id}</td>
                    <td>
                      <span className={`badge ${tx.type === "recharge" ? "badge-success" : tx.type === "deduct" ? "badge-error" : "badge-info"}`}>
                        {tx.type === "recharge" ? "充值" : tx.type === "deduct" ? "扣费" : tx.type === "refund" ? "退款" : tx.type}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600, color: ["recharge", "refund"].includes(tx.type) ? "#10b981" : "#ef4444" }}>
                      {tx.type === "deduct" ? "-" : "+"}¥{parseFloat(tx.amount).toFixed(2)}
                    </td>
                    <td>¥{parseFloat(tx.balance_after).toFixed(2)}</td>
                    <td style={{ color: "#888", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {tx.note || tx.reference || "-"}
                    </td>
                    <td>{formatTime(tx.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
