import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "../api/client";
import { useToast } from "../App";

interface AdminUser {
  id: number;
  email: string;
  nickname: string | null;
  balance: string;
  credit_limit: string;
  kyc_level: number;
  status: string;
  is_admin: boolean;
  created_at: string;
}

interface PaginatedUsers {
  items: AdminUser[];
  total: number;
  page: number;
  page_size: number;
}

function formatTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function statusBadge(status: string) {
  if (status === "active") return <span className="badge badge-success">正常</span>;
  if (status === "locked") return <span className="badge badge-error">已锁定</span>;
  return <span className="badge badge-info">{status}</span>;
}

function kycBadge(level: number) {
  const labels = ["未认证", "初级", "高级"];
  const cls = ["badge-warning", "badge-info", "badge-success"];
  return <span className={`badge ${cls[level] || "badge-warning"}`}>{labels[level] || `Lv.${level}`}</span>;
}

export default function UsersPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data, isLoading, isError, error } = useQuery<PaginatedUsers>({
    queryKey: ["admin-users", page],
    queryFn: () => apiClient.adminListUsers(page, pageSize) as Promise<PaginatedUsers>,
  });

  const lockMutation = useMutation({
    mutationFn: (userId: number) => apiClient.adminLockUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast("用户已锁定", "success");
    },
    onError: (err: Error) => toast(err.message, "error"),
  });

  const unlockMutation = useMutation({
    mutationFn: (userId: number) => apiClient.adminUnlockUser(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-users"] });
      toast("用户已解锁", "success");
    },
    onError: (err: Error) => toast(err.message, "error"),
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

  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / pageSize));

  return (
    <div className="page-content">
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 24 }}>用户管理</h2>

      <div className="card">
        <div className="card-header">
          <span className="card-title">用户列表 (共 {data?.total ?? 0} 人)</span>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>邮箱</th>
                <th>昵称</th>
                <th>余额</th>
                <th>KYC</th>
                <th>状态</th>
                <th>管理员</th>
                <th>注册时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.email}</td>
                  <td>{user.nickname || "-"}</td>
                  <td style={{ fontWeight: 600 }}>¥{parseFloat(user.balance).toFixed(2)}</td>
                  <td>{kycBadge(user.kyc_level)}</td>
                  <td>{statusBadge(user.status)}</td>
                  <td>{user.is_admin ? <span className="badge badge-info">是</span> : "否"}</td>
                  <td>{formatTime(user.created_at)}</td>
                  <td>
                    {user.status === "locked" ? (
                      <button
                        className="btn btn-primary"
                        style={{ padding: "4px 12px", fontSize: 12 }}
                        disabled={unlockMutation.isPending}
                        onClick={() => unlockMutation.mutate(user.id)}
                      >
                        {unlockMutation.isPending ? "..." : "解锁"}
                      </button>
                    ) : (
                      <button
                        className="btn btn-danger"
                        style={{ padding: "4px 12px", fontSize: 12 }}
                        disabled={lockMutation.isPending}
                        onClick={() => lockMutation.mutate(user.id)}
                      >
                        {lockMutation.isPending ? "..." : "锁定"}
                      </button>
                    )}
                  </td>
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
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const start = Math.max(1, Math.min(page - 3, totalPages - 6));
              const p = start + i;
              if (p > totalPages) return null;
              return (
                <button
                  key={p}
                  className="btn"
                  style={{
                    padding: "6px 12px",
                    background: p === page ? "#6c63ff" : "#f0f0f0",
                    color: p === page ? "#fff" : "#333",
                  }}
                  onClick={() => setPage(p)}
                >
                  {p}
                </button>
              );
            })}
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
      </div>
    </div>
  );
}
