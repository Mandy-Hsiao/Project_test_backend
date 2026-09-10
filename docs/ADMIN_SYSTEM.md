# 管理端後台系統 & 多層級數據分析

## 系統架構

### 三層權限模型

```
┌─────────────────────────────────────┐
│     系統管理員 (Admin)              │ → 查看全域數據、管理用戶
├─────────────────────────────────────┤
│     部門主管 (Manager)              │ → 查看部門數據
├─────────────────────────────────────┤
│     一般同仁 (User)                 │ → 查看個人歷史
└─────────────────────────────────────┘
```

---

## 功能模塊

### 1. **全域數據分析** (Admin Only)
📊 路徑: `/admin` → 「全域數據」標籤

**顯示內容:**
- 全公司/全系統總提問次數
- 跨部門提問分佈與百分比
- 高頻提問前10名（系統痛點分析）
- 周趨勢成長率
- 活躍用戶數

**API Endpoint:**
```bash
GET /api/analytics/stats?scope=global
```

**用途:** 幫助 IT/HR 識別哪些 SOP 說明不足，作為制度改善的依據

---

### 2. **部門數據分析** (Manager Only)
🏢 路徑: `/admin` → 「部門分析」標籤

**顯示內容:**
- 部門內總提問次數
- 該部門高頻提問Top 10
- 周趨勢分析
- 部門活躍同仁數

**限制:**
- 主管只能看自己的部門
- 無法跨部門查看

**API Endpoint:**
```bash
GET /api/analytics/stats?scope=department&department=HR
```

---

### 3. **個人提問歷史** (All Roles)
👤 路徑: `/admin` → 「個人歷史」標籤

**顯示內容:**
- 自己的提問記錄
- 個人趨勢分析

**API Endpoint:**
```bash
GET /api/analytics/stats?scope=personal
```

---

### 4. **用戶管理面板** (Admin Only)
👥 路徑: `/admin` → 「用戶管理」標籤

**功能:**
- 查看所有用戶及角色統計
- 即時修改用戶角色（user ↔ manager ↔ admin）
- 顯示用戶建立日期與部門

**API Endpoints:**
```bash
# 獲取所有用戶
GET /api/admin/users

# 修改用戶角色
POST /api/admin/users
Body: { userId: string, newRole: 'admin' | 'manager' | 'user' }
```

---

## 核心代碼結構

### 權限檢查工具 (`utils/auth.ts`)
```typescript
// 獲取用戶認證上下文
const auth = await getAuthContext()
// { userId, email, role, department }

// 檢查權限
const { allowed } = checkPermission(auth, ['admin'], department)

// 過濾敏感數據
const filtered = filterDataByRole(data, role, department)
```

### API 路由權限檢查
```typescript
// 在 API 路由中使用
const auth = await getAuthContext()
if (!auth) return NextResponse.json({ error: '未授權' }, { status: 401 })

const { allowed } = checkPermission(auth, ['admin'])
if (!allowed) return NextResponse.json({ error: '無權限' }, { status: 403 })
```

---

## 數據流程

### 1. 用戶發起提問
```
ChatDashboard
  ↓ (提交問題)
  ↓
chat_history 表 (儲存: user_id, question, created_at)
  ↓
profiles 表 (查詢: role, department)
```

### 2. 管理員查看數據
```
AdminDashboard (前端)
  ↓ (請求數據)
  ↓
/api/analytics/stats (API 層)
  ↓ (權限檢查)
  ↓
Database Query (根據 scope 篩選)
  ↓
AnalyticsPanel (可視化呈現)
```

---

## 高頻提問分析算法

系統自動識別常見提問類別：

| 關鍵詞             | 類別           |
|--------------------|----------------|
| 假/請假/休假      | 假期/請假      |
| 薪/帳/薪資        | 薪資/帳戶      |
| 系統/工具/IT      | 系統/工具      |
| 會議/出差/報告    | 會議/出差      |
| 考績/績效         | 考績/評核      |
| 招/應徵/離職      | 招聘/離職      |

**輸出:** 每個類別的提問數 + 示例問題（幫助 HR 改進 SOP）

---

## 異常檢測

系統自動標記以下異常：

1. **高頻提問用戶** - 24小時內提問 > 10 次
2. **系統高負載** - 過去24小時提問 > 50 次
3. **角色異常** - 用戶角色被異常修改

**用途:** 識別 IT 問題或員工培訓不足

---

## 代碼簡潔性設計

- **最小化重複代碼**: 統一的權限檢查工具 (`utils/auth.ts`)
- **複用 API 邏輯**: 同一個 `/api/analytics/stats` 支持多種 scope
- **組件參數化**: `<AnalyticsPanel scope={scope} ... />`
- **無冗長計算**: 所有統計直接在數據庫層完成

---

## 快速開始

### 1. 設置用戶角色
```sql
-- Supabase SQL 編輯器
UPDATE profiles SET role = 'admin' WHERE id = 'user-id';
UPDATE profiles SET role = 'manager', department = 'HR' WHERE id = 'user-id';
```

### 2. 訪問管理端
```
管理員: /admin (查看全域 + 用戶管理)
主管:   /admin (查看部門 + 個人)
同仁:   / (查看個人歷史)
```

### 3. 權限自動檢查
- ✅ 自動檢查用戶角色
- ✅ 自動過濾數據範圍
- ✅ API 層級權限驗證
- ✅ 無權限自動 403 / 401

---

## 擴展方向

1. **導出報表** - 添加 CSV/PDF 導出
2. **趨勢預測** - 基於歷史數據預測未來高頻問題
3. **智能通知** - 異常時自動通知管理員
4. **圖表可視化** - 集成 Recharts / Chart.js
5. **審計日誌** - 記錄管理員的所有操作

