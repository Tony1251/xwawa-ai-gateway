import React, { useState, useEffect } from "react";
import apiClient, { type WalletBalance, type Transaction } from "../api/client";

export default function WalletPage() {
  const [balance, setBalance] = useState<WalletBalance | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rechargeAmount, setRechargeAmount] = useState("");
  const [recharging, setRecharging] = useState(false);

  const loadData = async () => {
    try {
      const [bal, txns] = await Promise.all([
        apiClient.getBalance(),
        apiClient.getTransactions(50),
      ]);
      setBalance(bal);
      setTransactions(txns);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadData(); }, []);

  const handleRecharge = async () => {
    const amount = parseFloat(rechargeAmount);
    if (isNaN(amount) || amount <= 0) return;
    setRecharging(true);
    try {
      await apiClient.recharge(amount);
      setRechargeAmount("");
      await loadData();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRecharging(false);
    }
  };

  if (loading) return <div className="page-loading">加载中...</div>;

  return (
    <div className="wallet-page">
      <h2>我的钱包</h2>

      {error && <div className="error-banner">{error}</div>}

      {balance && (
        <div className="balance-cards">
          <div className="balance-card">
            <div className="balance-label">账户余额</div>
            <div className="balance-value">¥{parseFloat(balance.balance).toFixed(2)}</div>
          </div>
          <div className="balance-card">
            <div className="balance-label">信用额度</div>
            <div className="balance-value">¥{parseFloat(balance.credit_limit).toFixed(2)}</div>
          </div>
          <div className="balance-card">
            <div className="balance-label">本月已用</div>
            <div className="balance-value used">¥{parseFloat(balance.used_this_month).toFixed(2)}</div>
          </div>
          <div className="balance-card">
            <div className="balance-label">日限额</div>
            <div className="balance-value">¥{parseFloat(balance.daily_limit).toFixed(2)}</div>
          </div>
          <div className="balance-card">
            <div className="balance-label">单次限额</div>
            <div className="balance-value">¥{parseFloat(balance.per_call_limit).toFixed(2)}</div>
          </div>
        </div>
      )}

      <div className="recharge-section">
        <h3>充值</h3>
        <div className="recharge-form">
          <input
            type="number"
            value={rechargeAmount}
            onChange={(e) => setRechargeAmount(e.target.value)}
            placeholder="输入充值金额"
            min="1"
            step="0.01"
          />
          <button onClick={handleRecharge} disabled={recharging || !rechargeAmount}>
            {recharging ? "处理中..." : "充值 (Mock)"}
          </button>
        </div>
        <p className="recharge-note">⚠️ MVP 阶段为 Mock 充值，直接到账</p>
      </div>

      <div className="transactions-section">
        <h3>交易记录</h3>
        {transactions.length === 0 ? (
          <p className="empty-state">暂无交易记录</p>
        ) : (
          <table className="txn-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>类型</th>
                <th>金额</th>
                <th>余额</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((txn) => (
                <tr key={txn.id}>
                  <td>{new Date(txn.created_at).toLocaleString("zh-CN")}</td>
                  <td>
                    <span className={`txn-type txn-type-${txn.type}`}>{txn.type}</span>
                  </td>
                  <td className={parseFloat(txn.amount) >= 0 ? "positive" : "negative"}>
                    {parseFloat(txn.amount) >= 0 ? "+" : ""}¥{parseFloat(txn.amount).toFixed(2)}
                  </td>
                  <td>¥{parseFloat(txn.balance_after).toFixed(2)}</td>
                  <td>{txn.note || txn.reference || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
