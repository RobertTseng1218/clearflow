export type Highlight = {
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  type: 'task' | 'email' | 'event';
};

export type TaskItem = {
  id: string;
  title: string;
  description: string;
  status: 'open' | 'in_progress' | 'done';
  priority: 'high' | 'medium' | 'low';
  dueAt: string;
  source: 'gmail' | 'gcal';
};

export const dashboardData = {
  plan: '免費版',
  aiUsage: { used: 8, total: 20 },
  highlights: [
    { title: '回覆客戶 A 的合作確認信', description: '今天內需要完成回覆與下一步安排。', priority: 'high', type: 'task' },
    { title: '下午 3:00 與產品討論會議', description: '先整理目前 MVP 範圍與 Sprint 0 進度。', priority: 'high', type: 'event' },
    { title: '檢查 Gmail 同步結果', description: '確認 source_items 與摘要產生是否正常。', priority: 'medium', type: 'email' },
  ] as Highlight[],
  summary: {
    date: '2026-03-12',
    preview: '今天有 3 封重要郵件、2 個行程，以及 5 個待處理事項。',
  },
  tasks: [
    { id: 't1', title: '回覆客戶 A', description: '跟進昨日來信並確認需求', status: 'open', priority: 'high', dueAt: '今天 18:00', source: 'gmail' },
    { id: 't2', title: '整理 Sprint 0 完成項目', description: '同步目前後端骨架進度', status: 'in_progress', priority: 'medium', dueAt: '今天 20:00', source: 'gcal' },
    { id: 't3', title: '檢查免費版限制文案', description: '確認升級提示位置與字句', status: 'open', priority: 'low', dueAt: '明天', source: 'gmail' },
  ] as TaskItem[],
  reminders: [
    { title: '今天 18:00 前需回覆客戶 A', message: '這項任務即將到期。' },
    { title: '明天上午會議前要先整理摘要', message: '建議今晚先完成重點彙整。' },
  ],
  activities: [
    { time: '11:00', message: 'Gmail 同步完成，新增 12 筆來源資料' },
    { time: '11:02', message: '已生成今日摘要' },
    { time: '11:03', message: '已提取 4 筆待辦事項' },
  ],
  integrations: [
    { id: 'i1', provider: 'Gmail', status: 'connected', lastSyncedAt: '2026-03-12 11:00' },
    { id: 'i2', provider: 'Google Calendar', status: 'connected', lastSyncedAt: '2026-03-12 11:01' },
  ],
  summaries: [
    { id: 's1', type: 'daily', date: '2026-03-12', preview: '今天有 3 封重要郵件、2 個行程與 5 個待辦。' },
    { id: 's2', type: 'daily', date: '2026-03-11', preview: '昨天的重點工作已完成 4 項，還有 2 項待跟進。' },
  ]
};

export const onboardingTemplates = [
  { key: 'solo_worker', name: '個人工作者', description: '適合接案者、自營工作者、小主管。' },
  { key: 'consultant', name: '顧問 / 接案者', description: '適合多客戶、多專案的工作型態。' },
  { key: 'pm_worker', name: 'PM / 專案型', description: '適合任務多、協作密度高的角色。' },
  { key: 'engineering', name: '工程 / 研發型', description: '適合需要整理技術事項與待辦的人。' },
];
