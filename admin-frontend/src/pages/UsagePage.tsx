import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "../api/client";

interface UsageRecord {
  id: number;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_provider: string;
  cost_user: string;
  is_anomalous: boolean;
  anomaly_reason: string | null;
  created_at: string;
}

interface PaginatedUsage {
  items: UsageRecord[];
  total: number;
  page: number;
  page_size: number;
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const providerOptions = [
  { value: "", label: "全部" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "google", label: "Google" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "azure", label: "Azure" },
];

export default function UsagePage() {
  const [userId, setUserId] = useState("");
  const [searchedUserId, setSearchedUserId] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [providerFilter, setProviderFilter] = useState("");
  const pageSize = 20;

  const { data, isLoading, isError, error } = useQuery<PaginatedUsage>({
    queryKey: ["admin-usage", searchedUserId, page, providerFilter],
    queryFn: () =>
      apiClient.adminGetUserUsage(searchedUserId!, page, pageSize) as Promise<PaginatedUsage>,
    enabled: searchedUserId !== null && searchedUserId > 0,
  });

  const handleSearch = () => {
    const id = parseInt(userId, 10);
    if (isNaN(id) || id <= 0) return;
    setSearchedUserId(id);
    setPage(1);
  };

  // Client-side filter by provider
  const filtered = data?.items.filter((rec) => !providerFilter || rec.provider === providerFilter) ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / pageSize));

  return (
    <div className="page-content">
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>用量查询</h2>

      {/* Search Card */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">查询用户用量</span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label className="form-label" htmlFor="usageUserId">用户 ID</label>
            <input
              id="usageUserId"
              className="form-input"
              type="number"
              min="1"
              placeholder="输入用户 ID"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <button className="btn btn-primary" onClick={handleSearch} disabled={!userId.trim()}>
            查询
          </button>
        </div>
      </div>

      {searchedUserId !== null && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">用户 #{searchedUserId} 的用量记录</span>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <label className="form-label" style={{ marginBottom: 0, whiteSpace: "nowrap" }}>Provider:</label>
              <select
                className="form-input"
                style={{ width: "auto", padding: "6px 12px" }}
                value={providerFilter}
                onChange={(e) => setProviderFilter(e.target.value)}
              >
                {providerOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>

          {isLoading ? (
            <div className="loading"><span className="spinner" /></div>
          ) : isError ? (
            <p style={{ color: "#ef4444" }}>加载失败: {(error as Error).message}</p>
          ) : !data || data.items.length === 0 ? (
            <p style={{ color: "#888", fontSize: 14, padding: "16px 0" }}>暂无用量记录</p>
          ) : (
            <>
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Provider</th>
                      <th>模型</th>
                      <th>输入 Tokens</th>
                      <th>输出 Tokens</th>
                      <th>成本(用户)</th>
                      <th>成本(Provider)</th>
                      <th>异常</th>
                      <th>时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((rec) => (
                      <tr key={rec.id}>
                        <td>{rec.id}</td>
                        <td>
                          <span className="badge badge-info">{rec.provider}</span>
                        </td>
                        <td style={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {rec.model}
                        </td>
                        <td>{rec.input_tokens.toLocaleString()}</td>
                        <td>{rec.output_tokens.toLocaleString()}</td>
                        <td style={{ fontWeight: 600 }}>¥{parseFloat(rec.cost_user || "0").toFixed(6)}</td>
                        <td>¥{parseFloat(rec.cost_provider || "0").toFixed(6)}</td>
                        <td>
                          {rec.is_anomalous ? (
                            <span title={rec.anomaly_reason || ""} className="badge badge-error" style={{ cursor: "help" }}>
                              异常
                            </span>
                          ) : (
                            <span className="badge badge-success">正常</span>
                          )}
                        </td>
                        <td>{formatTime(rec.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div style={{ display: "flex", justifyContent: "center", gap: 8, paddingTop: 20 }}>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: "6px 14px" }}
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    上一页
                  </button>
                  <span style={{ display: "flex", alignItems: "center", fontSize: 14, color: "#666" }}>
                    第 {page} / {totalPages} 页
                  </span>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: "6px 14px" }}
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    下一页
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
