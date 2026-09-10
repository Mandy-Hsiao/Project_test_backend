# 快速設置指南 - 管理端系統

## 前置條件

確保 Supabase 的 `profiles` 表包含以下欄位：

```sql
ALTER TABLE profiles ADD COLUMN role TEXT DEFAULT 'user'; -- 'admin' | 'manager' | 'user'
ALTER TABLE profiles ADD COLUMN department TEXT DEFAULT ''; -- 部門名稱
```

---

## 1. 初始化測試帳號

在 Supabase 中執行：

```sql
-- 系統管理員
UPDATE profiles SET role = 'admin', department = 'IT' WHERE email = 'admin@company.com';

-- 部門主管（HR）
UPDATE profiles SET role = 'manager', department = 'HR' WHERE email = 'hr-manager@company.com';

-- 部門主管（Sales）
UPDATE profiles SET role = 'manager', department = 'Sales' WHERE email = 'sales-manager@company.com';

-- 普通員工
UPDATE profiles SET role = 'user', department = 'HR' WHERE email = 'employee@company.com';
```

---

## 2. 測試權限流程

### 2.1 管理員視圖
```
✅ 訪問 /admin
✅ 可看「全域數據」- 跨部門統計
✅ 可看「用戶管理」- 修改用戶角色
✅ 可看「個人歷史」- 自己的提問
❌ 無法訪問他人個人數據
```

### 2.2 主管視圖
```
✅ 訪問 /admin (自動顯示部門視圖)
✅ 可看「部門分析」- 部門內的高頻提問
✅ 可看「個人歷史」- 自己的提問
❌ 看不到其他部門數據
❌ 無法訪問用戶管理
```

### 2.3 普通員工
```
✅ 訪問 /
✅ 提交提問
❌ 無法訪問 /admin
❌ 無法看其他人的數據
```

---

## 3. API 端點測試

### 3.1 全域數據分析
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://your-domain.com/api/analytics/stats?scope=global"

# 響應示例
{
  "totalQuestions": 1248,
  "uniqueUsers": 142,
  "questionsPerDay": { "2025-01-15": 42, ... },
  "departmentBreakdown": {
    "HR": { "count": 350, "percentage": "28.0" },
    "Sales": { "count": 290, "percentage": "23.2" },
    ...
  },
  "topQuestions": [
    { "question": "假期如何申請?", "count": 45 },
    { "question": "薪資何時發放?", "count": 38 },
    ...
  ]
}
```

### 3.2 部門數據分析
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://your-domain.com/api/analytics/stats?scope=department&department=HR"
```

### 3.3 個人歷史
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://your-domain.com/api/analytics/stats?scope=personal"
```

### 3.4 用戶管理（修改角色）
```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://your-domain.com/api/admin/users" \
  -d '{ "userId": "abc-123", "newRole": "manager" }'
```

---

## 4. 前端組件使用

### 4.1 在頁面中使用分析面板
```tsx
import AnalyticsPanel from '@/components/AnalyticsPanel'

export default function MyDashboard() {
  return (
    <AnalyticsPanel
      scope="global"
      userRole="admin"
    />
  )
}
```

### 4.2 在頁面中使用用戶管理
```tsx
import AdminUserManagement from '@/components/AdminUserManagement'

export default function UserMgmtPage() {
  return <AdminUserManagement />
}
```

---

## 5. 常見問題排查

### 問題: 無法訪問 /admin
**原因:** 用戶角色為 'user'  
**解決:** 在 Supabase 中修改 `role` 為 'admin' 或 'manager'

### 問題: 看不到跨部門數據
**原因:** 角色為 'manager' 且試圖跨部門查看  
**解決:** 改用 'admin' 角色或使用 'department' scope

### 問題: API 返回 403
**原因:** 權限檢查失敗  
**解決:** 檢查 Token 對應用戶的角色是否正確

### 問題: 統計數據為空
**原因:** chat_history 表無數據  
**解決:** 先提交幾個問題，讓系統積累數據

---

## 6. 常用 SQL 查詢

### 查看所有用戶角色分佈
```sql
SELECT role, COUNT(*) as count FROM profiles GROUP BY role;
```

### 查看各部門提問數
```sql
SELECT p.department, COUNT(ch.id) as questions
FROM profiles p
LEFT JOIN chat_history ch ON p.id = ch.user_id
GROUP BY p.department
ORDER BY questions DESC;
```

### 查看高頻提問
```sql
SELECT question, COUNT(*) as count
FROM chat_history
GROUP BY question
ORDER BY count DESC
LIMIT 10;
```

### 查看用戶提問時間分佈
```sql
SELECT DATE(created_at) as date, COUNT(*) as count
FROM chat_history
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;
```

---

## 7. 部署檢查清單

- [ ] Supabase profiles 表已添加 role 和 department 欄位
- [ ] 環境變數配置正確 (NEXT_PUBLIC_SUPABASE_*)
- [ ] 管理員帳號已設置
- [ ] 測試 /admin 頁面可正常載入
- [ ] API 端點權限檢查正常
- [ ] 數據隱私：主管無法跨部門查看 ✓
- [ ] 數據隱私：普通員工無法訪問 /admin ✓

---

## 8. 後續優化方向

1. **數據導出**: 添加 CSV/Excel 導出功能
2. **預警機制**: 當異常提問率 > 閾值時自動通知
3. **圖表視覺化**: 集成 Recharts 顯示趨勢圖
4. **高級過濾**: 按日期範圍、部門、提問類型篩選
5. **AI 分類**: 使用 NLP 自動分類提問主題
6. **審計日誌**: 記錄管理員所有操作

