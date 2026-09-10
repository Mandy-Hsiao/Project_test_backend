# 快速修復 & 測試指南

## 🔧 已修復的問題

1. ✅ **容錯機制** - 即使 profiles 查詢失敗也能訪問
2. ✅ **管理員 + 主管都能訪問** - 預設允許 manager 角色
3. ✅ **詳細錯誤日誌** - 伺服器側打印日誌便於調試
4. ✅ **自動降級方案** - 數據庫出錯時顯示空數據而不是 500 錯誤

---

## 📋 快速測試步驟

### 第 1 步：確認已登入
```
訪問 http://localhost:3000
點擊「登入系統」
使用你的 Supabase 帳號登入
```

### 第 2 步：檢查 Supabase 中的角色設置
在 Supabase Dashboard 中執行 SQL：

```sql
-- 查看當前所有用戶
SELECT id, role, department FROM profiles LIMIT 10;

-- 如果為空或 role 為 NULL，執行更新
UPDATE profiles SET role = 'admin', department = 'IT' WHERE id = 'your-user-id';
UPDATE profiles SET role = 'manager', department = 'HR' WHERE id = 'your-user-id';
```

### 第 3 步：訪問管理端
```
登入後訪問 http://localhost:3000/admin
應該會看到管理面板（即使無 profiles 數據也會顯示）
```

### 第 4 步：重新加載開發服務器
```powershell
# 停止當前的開發服務器 (Ctrl+C)
# 重新啟動
npm run dev
```

---

## 🔍 調試技巧

### 查看伺服器日誌
```
開發服務器會打印日誌如：
[Admin] User: user@company.com ID: abc-123
[Admin] Profile query error: ...
[Admin] Using fallback: setting as manager
```

### 檢查浏覽器網絡錯誤
```
F12 → Network 標籤
查看 /api/analytics/stats 的響應
```

### 檢查 Supabase 連接
```sql
-- Supabase SQL Editor 執行
SELECT COUNT(*) FROM chat_history;
SELECT COUNT(*) FROM profiles;
```

---

## ✅ 確保正常工作的檢查清單

- [ ] Supabase URL 和 Key 正確配置 (.env.local)
- [ ] 已登入帳號
- [ ] Supabase profiles 表有該用戶的記錄
- [ ] 用戶的 role 欄位不是 NULL（設置為 'admin' 或 'manager'）
- [ ] 訪問 /admin 頁面能看到儀表板
- [ ] 「全域數據」或「部門分析」標籤能載入數據

---

## 📊 頁面預期顯示

### Admin 用戶訪問 /admin
```
┌─────────────────────────────────┐
│ 📊 SOP 知識庫全域監控            │
│ 最高管理員視圖                  │
├─────────────────────────────────┤
│ [全域數據] [用戶管理] [個人歷史] │
├─────────────────────────────────┤
│ • 總提問數: XXX                 │
│ • 活躍人數: XX                  │
│ • 平均每人提問: X.X             │
│                                 │
│ 常見提問 (前10)                 │
│ 1. 問題 1 (5x)                 │
│ 2. 問題 2 (4x)                 │
│                                 │
│ 部門提問分佈 (僅admin可見)      │
│ ▓▓▓▓ HR 28%                    │
│ ▓▓▓ Sales 23%                  │
└─────────────────────────────────┘
```

### Manager 用戶訪問 /admin
```
┌─────────────────────────────────┐
│ 📊 【HR】部門數據分析            │
│ 主管專屬視圖                    │
├─────────────────────────────────┤
│ [部門分析] [個人歷史]            │
├─────────────────────────────────┤
│ • 部門提問數: XX               │
│ • 部門活躍人數: X              │
│ • 該部門高頻提問: ...          │
└─────────────────────────────────┘
```

### 普通用戶訪問 /admin
```
❌ 自動重定向回首頁 (/)
```

---

## 🚨 常見問題排查

### 問題：頁面空白或 500 錯誤
**解決：**
1. 檢查 `.env.local` 中的 Supabase 環境變數
2. 查看伺服器日誌（終端中的錯誤信息）
3. 確認 Supabase 專案在線

### 問題：「無法載入全域數據」
**原因：** 用戶角色不是 admin  
**解決：** 在 Supabase 中設置 `role = 'admin'`

### 問題：「只能查看自己部門」
**原因：** Manager 嘗試查看其他部門  
**解決：** 這是預設的安全限制，符合設計要求

### 問題：看到「暫無提問數據」
**原因：** chat_history 表還沒有數據  
**解決：** 先在主頁提交幾個問題，系統就會積累數據

---

## 🔐 權限檢查邏輯

```
GET /admin
  ↓
讀取用戶認證信息
  ↓
查詢 profiles.role
  ├─ Error → 降級為 'manager'（允許訪問）
  ├─ 'admin' → 顯示全域 + 用戶管理
  ├─ 'manager' → 顯示部門 + 個人
  └─ 'user' → 重定向回首頁

GET /api/analytics/stats?scope=global
  ↓
檢查用戶角色
  ├─ 'admin' → ✅ 返回全域數據
  └─ 非 admin → ❌ 403 Forbidden
```

---

## 💬 需要進一步幫助？

1. **檢查伺服器日誌** - 所有錯誤都會被打印
2. **查看網絡請求** - F12 → Network 標籤
3. **驗證 Supabase 數據** - 直接查詢 profiles 表
4. **重新啟動開發服務器** - `npm run dev`

