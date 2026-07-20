import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "../api/client";

interface ApiKeyInfo {
  id: number;
  name: string;
  key_preview: string;
  scopes: Record<string, boolean>;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
}

function formatTime(iso: string | null) {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function ApiKeysPage() {
  const [userId, setUserId] = useState("");
  const [searchedUserId, setSearchedUserId] = useState<number | null>(null);

  const { data, isLoading, isError, error } = useQuery<ApiKeyInfo[]>({
    queryKey: ["admin-api-keys", searchedUserId],
    queryFn: () => apiClient.adminGetUserApiKeys(searchedUserId!) as Promise<ApiKeyInfo[]>,
    enabled: searchedUserId !== null && searchedUserId > 0,
  });

  const handleSearch = () => {
    const id = parseInt(userId, 10);
    if (isNaN(id) || id <= 0) return;
    setSearchedUserId(id);
  };

  return (
    <div className="page-content">
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>API 密钥查询</h2>

      <div className="card">
        <div className="card-header">
          <span className="card-title">查询用户 API 密钥</span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <label className="form-label" htmlFor="userId">用户 ID</label>
            <input
              id="userId"
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
            <span className="card-title">用户 #{searchedUserId} 的 API 密钥</span>
          </div>

          {isLoading ? (
            <div className="loading"><span className="spinner" /></div>
          ) : isError ? (
            <p style={{ color: "#ef4444" }}>加载失败: {(error as Error).message}</p>
          ) : !data || data.length === 0 ? (
            <p style={{ color: "#888", fontSize: 14, padding: "16px 0" }}>该用户暂无 API 密钥</p>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>名称</th>
                    <th>密钥预览</th>
                    <th>权限</th>
                    <th>状态</th>
                    <th>最后使用</th>
                    <th>创建时间</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((key) => (
                    <tr key={key.id}>
                      <td>{key.id}</td>
                      <td>{key.name}</td>
                      <td>
                        <code style={{ background: "#f5f5f5", padding: "2px 6px", borderRadius: 4, fontSize: 12 }}>
                          {key.key_preview}
                        </code>
                      </td>
                      <td>
                        {Object.entries(key.scopes || {}).map(([scope, enabled]) => (
                          enabled && (
                            <span key={scope} className="badge badge-info" style={{ marginRight: 4 }}>
                              {scope}
                            </span>
                          )
                        ))}
                        {(!key.scopes || Object.keys(key.scopes).length === 0) && "-"}
                      </td>
                      <td>
                        {key.is_active ? (
                          <span className="badge badge-success">启用</span>
                        ) : (
                          <span className="badge badge-error">禁用</span>
                        )}
                      </td>
                      <td>{formatTime(key.last_used_at)}</td>
                      <td>{formatTime(key.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
