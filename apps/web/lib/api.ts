'use client';

import { getAccessToken, clearAccessToken } from '@/lib/auth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  meta?: Record<string, unknown>;
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

type ApiErrorLike = {
  error?: { code?: string; message?: string; details?: Record<string, unknown> };
  detail?: { code?: string; message?: string; details?: Record<string, unknown> };
};

type ConnectionStatus = {
  active_integrations_count: number;
  has_active_integrations: boolean;
  has_historical_data: boolean;
  notice?: string | null;
};


type DataUpdatedDetail = {
  reason?: 'sync' | 'task' | string;
  message?: string;
  [key: string]: unknown;
};

const DATA_UPDATED_EVENT = 'clearflow:data-updated';

export function notifyDataUpdated(detail?: DataUpdatedDetail) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<DataUpdatedDetail>(DATA_UPDATED_EVENT, { detail }));
}

export function bindDataUpdated(listener: (detail?: DataUpdatedDetail) => void) {
  if (typeof window === 'undefined') {
    return () => {};
  }

  const handler = (event: Event) => {
    const customEvent = event as CustomEvent<DataUpdatedDetail>;
    listener(customEvent.detail);
  };

  window.addEventListener(DATA_UPDATED_EVENT, handler as EventListener);
  return () => {
    window.removeEventListener(DATA_UPDATED_EVENT, handler as EventListener);
  };
}

function mapErrorMessage(code?: string, fallback?: string): string {
  const messageMap: Record<string, string> = {
    INTEGRATION_LIMIT_REACHED: '免費版目前最多只能連接 1 個來源。若要同時使用 Gmail 與 Google Calendar，請升級個人版。',
    OAUTH_NOT_CONFIGURED: '目前尚未完成正式 Google OAuth 設定，請先確認開發模式或 OAuth 設定。',
    UNAUTHORIZED: '登入已失效，請重新登入。',
    FORBIDDEN: '你目前沒有權限執行這個操作。',
    NOT_FOUND: '找不到指定資料，請重新整理後再試。',
    INTEGRATION_NOT_READY: '來源尚未完成連接，暫時無法同步。',
    SYNC_FAILED: '同步失敗，請稍後再試。',
    SUMMARY_NOT_FOUND: '找不到這筆摘要資料。',
    TASK_NOT_FOUND: '找不到這筆待辦事項。',
    VALIDATION_ERROR: '送出的資料格式有誤，請確認後再試。',
    INTERNAL_ERROR: '系統目前發生問題，請稍後再試。',
  };

  return messageMap[code || ''] || fallback || '請求失敗';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && options.method && options.method !== 'GET') {
    headers.set('Content-Type', 'application/json');
  }

  if (token) headers.set('Authorization', `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    cache: 'no-store',
  });

  const json = (await response.json()) as ApiEnvelope<T> | ApiErrorLike;

  if (!response.ok) {
    const code = (json as ApiErrorLike)?.error?.code || (json as ApiErrorLike)?.detail?.code;
    const rawMessage = (json as ApiErrorLike)?.error?.message || (json as ApiErrorLike)?.detail?.message;

    if (response.status === 401) {
      clearAccessToken();
    }

    throw new Error(mapErrorMessage(code, rawMessage));
  }

  if ('success' in json && json.success) {
    return json.data;
  }

  throw new Error('取得資料失敗');
}

export async function devLogin(devCode: string) { return request<any>(`${API_PREFIX}/auth/google/callback?code=${encodeURIComponent(devCode)}&state=login:gmail`); }
export async function getMe() { return request<any>(`${API_PREFIX}/me`); }
export async function getPlan() { return request<any>(`${API_PREFIX}/me/plan`); }
export async function getUsage() { return request<any>(`${API_PREFIX}/me/usage`); }
export async function getSettings() { return request<any>(`${API_PREFIX}/settings`); }
export async function updateNotifications(payload: { daily_summary_enabled?: boolean; preferred_hour?: number }) { return request<any>(`${API_PREFIX}/settings/notifications`, { method: 'PATCH', body: JSON.stringify(payload) }); }
export async function getIntegrations() { return request<any>(`${API_PREFIX}/integrations`); }
export async function connectIntegration(providerKey: 'gmail' | 'gcal') { return request<any>(`${API_PREFIX}/integrations/connect`, { method: 'POST', body: JSON.stringify({ provider_key: providerKey }) }); }
export async function completeIntegration(providerKey: 'gmail' | 'gcal', code: string) { return request<any>(`${API_PREFIX}/integrations/callback`, { method: 'POST', body: JSON.stringify({ provider_key: providerKey, code }) }); }
export async function syncIntegration(integrationId: string) { return request<any>(`${API_PREFIX}/integrations/${integrationId}/sync`, { method: 'POST' }); }
export async function deleteIntegration(integrationId: string) { return request<any>(`${API_PREFIX}/integrations/${integrationId}`, { method: 'DELETE' }); }

export async function getDashboard() {
  return request<{
    today_highlights: Array<{
      title: string;
      description?: string;
      priority_score?: number;
      related_type?: string;
      related_id?: string;
      source_type?: string;
      source_label?: string;
      display_label?: string;
      due_at?: string | null;
      task_kind?: string;
      status?: string;
      priority?: string;
    }>;
    daily_summary_preview?: {
      summary_id?: string;
      summary_date?: string;
      summary_text_preview?: string;
      source_breakdown?: Record<string, number>;
      signal_breakdown?: Record<string, number>;
    } | null;
    email_highlights?: Array<{
      title: string;
      description?: string;
      priority_score?: number;
      related_type?: string;
      related_id?: string;
      source_type?: string;
      source_label?: string;
      display_label?: string;
    }>;
    event_highlights?: Array<{
      title: string;
      description?: string;
      priority_score?: number;
      related_type?: string;
      related_id?: string;
      source_type?: string;
      source_label?: string;
      display_label?: string;
    }>;
    task_preview?: {
      open_count?: number;
      due_soon_count?: number;
      items?: Array<{
        id: string;
        title: string;
        description?: string;
        status: string;
        priority: string;
        due_at?: string | null;
        source?: string | null;
        source_label?: string;
        source_type?: string;
        task_kind?: string;
        display_hint?: string | null;
      }>;
    } | null;
    reminder_preview?: {
      items?: Array<{
        title: string;
        message?: string;
        source_type?: string;
        source_label?: string;
        trigger_at?: string | null;
      }>;
    } | null;
    recent_activity_preview?: {
      items?: Array<{ id?: string; event_type?: string; message: string; created_at: string }>;
    } | null;
    source_overview?: {
      email_count?: number;
      calendar_count?: number;
      active_sources?: number;
      today_data_sources_count?: number;
      today_data_source_labels?: string[];
    } | null;
    usage_preview?: { monthly_ai_usage: number; monthly_ai_quota: number };
    connection_status?: ConnectionStatus;
  }>(`${API_PREFIX}/dashboard`);
}

export async function getSummaries() {
  return request<{
    items: Array<{ id: string; summary_type: string; summary_date: string; summary_text_preview: string; created_at: string }>;
    connection_status?: ConnectionStatus;
  }>(`${API_PREFIX}/summaries?type=daily`);
}

export async function getSummary(summaryId: string) {
  return request<{
    id: string;
    summary_type: string;
    summary_date: string;
    summary_text: string;
    items: Array<{ id: string; item_type: string; title: string; description?: string; priority_score?: number; related_source_item_id?: string | null; meta?: Record<string, unknown> }>;
    connection_status?: ConnectionStatus;
  }>(`${API_PREFIX}/summaries/${summaryId}`);
}

export async function getTasks() {
  return request<{
    items: Array<{ id: string; title: string; description?: string; status: string; priority: string; due_at?: string | null; source?: string | null; created_by_type?: string }>;
    connection_status?: ConnectionStatus;
  }>(`${API_PREFIX}/tasks`);
}

export async function getTask(taskId: string) { return request<any>(`${API_PREFIX}/tasks/${taskId}`); }
export async function patchTask(taskId: string, payload: { status?: string; priority?: string }) { return request<any>(`${API_PREFIX}/tasks/${taskId}`, { method: 'PATCH', body: JSON.stringify(payload) }); }
