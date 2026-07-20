import React, { useState, useRef, useEffect } from "react";
import apiClient, { type ChatRequest, type ChatResponse } from "../api/client";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  model?: string;
  provider?: string;
  inputTokens?: number;
  outputTokens?: number;
  costUser?: string;
  loading?: boolean;
}

const MODELS = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet" },
  { value: "doubao-pro-32k", label: "豆包 Pro 32K" },
  { value: "deepseek-chat", label: "DeepSeek Chat" },
];

export default function ChatPage() {
  const [model, setModel] = useState("gpt-4o-mini");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "",
      loading: true,
    };
    setMessages((prev) => [...prev, assistantMsg]);

    try {
      const req: ChatRequest = {
        model,
        messages: messages
          .filter((m) => !m.loading)
          .concat([userMsg])
          .map((m) => ({ role: m.role, content: m.content })),
      };
      const res: ChatResponse = await apiClient.chat(req);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMsg.id
            ? {
                ...m,
                content: res.content,
                model: res.model,
                provider: res.provider,
                inputTokens: res.input_tokens,
                outputTokens: res.output_tokens,
                costUser: res.cost_user,
                loading: false,
              }
            : m
        )
      );
    } catch (e: any) {
      setError(e.message || "请求失败");
      setMessages((prev) => prev.filter((m) => m.id !== assistantMsg.id));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-header">
        <select value={model} onChange={(e) => setModel(e.target.value)} className="model-select">
          {MODELS.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>开始对话吧！模型：{MODELS.find((m) => m.value === model)?.label}</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`message message-${msg.role}`}>
            <div className="message-role">{msg.role === "user" ? "你" : "AI"}</div>
            <div className="message-content">
              {msg.loading ? (
                <span className="loading-dots">思考中...</span>
              ) : (
                msg.content
              )}
            </div>
            {msg.provider && !msg.loading && (
              <div className="message-meta">
                <span>{msg.model}</span>
                <span>{msg.provider}</span>
                {msg.inputTokens != null && <span>输入: {msg.inputTokens} tokens</span>}
                {msg.outputTokens != null && <span>输出: {msg.outputTokens} tokens</span>}
                {msg.costUser && <span>费用: ¥{msg.costUser}</span>}
              </div>
            )}
          </div>
        ))}
        {error && <div className="chat-error">{error}</div>}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
          rows={3}
          disabled={loading}
        />
        <button className="send-btn" onClick={sendMessage} disabled={loading || !input.trim()}>
          {loading ? "发送中..." : "发送"}
        </button>
      </div>
    </div>
  );
}
