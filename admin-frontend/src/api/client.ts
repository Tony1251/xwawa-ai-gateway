// xwawa-ai-gateway API Client
import axios, { AxiosInstance } from "axios";

const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || "http://localhost:8800";

export interface ChatRequest {
  model: string;
  messages: Array<{ role: string; content: string }>;
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;
}

export interface ChatResponse {
  id: string;
  model: string;
  content: string;
  input_tokens: number;
  output_tokens: number;
  cost_user: string;
  cost_provider: string;
  provider: string;
}

export interface WalletBalance {
  balance: string;
  credit_limit: string;
  used_this_month: string;
  daily_limit: string;
  per_call_limit: string;
}

export interface Transaction {
  id: number;
  type: string;
  amount: string;
  balance_after: string;
  reference: string | null;
  note: string | null;
  created_at: string;
}

export interface UsageLog {
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

class ApiClient {
  private client: AxiosInstance;
  private token: string | null = null;
  private apiKey: string | null = null;

  constructor(baseURL: string = API_BASE) {
    this.client = axios.create({ baseURL, timeout: 30000 });
    this.client.interceptors.request.use((config) => {
      if (this.token) config.headers.Authorization = "Bearer " + this.token;
      else if (this.apiKey) config.headers.Authorization = "ApiKey " + this.apiKey;
      return config;
    });
    this.client.interceptors.response.use(
      (r) => r,
      (e) => Promise.reject(new Error(e.response?.data?.error?.message || e.message))
    );
  }

  setToken(t: string) { this.token = t; this.apiKey = null; }
  setApiKey(k: string) { this.apiKey = k; this.token = null; }
  clearAuth() { this.token = null; this.apiKey = null; }

  async register(email: string, password: string, nickname?: string) {
    const r = await this.client.post("/v1/auth/register", { email, password, nickname });
    return (r.data as any).data;
  }

  async login(email: string, password: string) {
    const r = await this.client.post("/v1/auth/login", { email, password });
    return (r.data as any).data;
  }

  async createApiKey(name: string, scopes?: { chat?: boolean; images?: boolean; music?: boolean }) {
    const r = await this.client.post("/v1/auth/api-keys", { name, ...scopes });
    return (r.data as any).data;
  }

  async chat(req: ChatRequest): Promise<ChatResponse> {
    const r = await this.client.post("/v1/chat", req);
    return (r.data as any).data;
  }

  async listModels(provider?: string) {
    const r = await this.client.get("/v1/models", { params: provider ? { provider } : {} });
    return (r.data as any).data;
  }

  async getBalance(): Promise<WalletBalance> {
    const r = await this.client.get("/v1/wallet/balance");
    return (r.data as any).data;
  }

  async recharge(amount: number) {
    const r = await this.client.post("/v1/wallet/recharge", { amount });
    return (r.data as any).data;
  }

  async getTransactions(limit = 50, offset = 0): Promise<Transaction[]> {
    const r = await this.client.get("/v1/wallet/transactions", { params: { limit, offset } });
    return (r.data as any).data;
  }

  async getUsage(limit = 100, offset = 0, provider?: string): Promise<UsageLog[]> {
    const r = await this.client.get("/v1/wallet/usage", { params: { limit, offset, provider } });
    return (r.data as any).data;
  }

  async registerAgent(did: string, name: string, agentType: string) {
    const r = await this.client.post("/v1/wallet/agents", { did, name, agent_type: agentType });
    return (r.data as any).data;
  }

  async adminGetUser(userId: number) {
    const r = await this.client.get("/admin/users/" + userId);
    return (r.data as any).data;
  }

  async adminGetStats() {
    const r = await this.client.get("/admin/stats/overview");
    return (r.data as any).data;
  }
}

export const apiClient = new ApiClient();
export default apiClient;
