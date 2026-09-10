import { createClient as createSupabaseClient } from '@supabase/supabase-js'

/**
 * ⚠️ 僅能在「伺服器端」使用（API Route / Server Component），
 * 絕對禁止 import 進任何 'use client' 元件，否則會把 service role key 洩漏到瀏覽器。
 *
 * 用途：
 * 一般的 utils/supabase/server.ts 是用 anon key + 使用者 cookie 建立連線，
 * 所有查詢都會受到 Supabase 的 RLS（Row Level Security）限制，
 * 也就是說「主管」或「管理員」用那個 client 去查其他同仁的 profiles / chat_history，
 * 只要 RLS 政策是預設的 `auth.uid() = id` / `auth.uid() = user_id`，
 * 就一定查不到別人的資料（這正是主管後台數據沒有同步的根本原因）。
 *
 * 這個 admin client 用 service role key 建立連線，會「繞過 RLS」，
 * 所以只能在 API 路由裡「先用一般 client 驗證身份與角色」，
 * 確認使用者真的有權限之後，才用這個 client 去讀取跨使用者的資料。
 */
export function createAdminClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY

  if (!url || !serviceRoleKey) {
    throw new Error(
      '缺少 SUPABASE_SERVICE_ROLE_KEY 環境變數。請至 Supabase 專案 Settings > API，' +
        '複製 "service_role" secret key，加入 .env.local 後重新啟動伺服器。',
    )
  }

  return createSupabaseClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  })
}