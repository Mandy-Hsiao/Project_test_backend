import { createClient } from '@/utils/supabase/server'
import { signout } from './login/actions'
import ChatDashboard from '@/components/ChatDashboard'

export default async function HomePage() {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  let userRole: 'admin' | 'manager' | 'user' | 'resigned' = 'user'
  let department = ''
  let employeeName = ''

  if (user) {
    // 查詢角色、部門與員工姓名
    const { data: profile } = await supabase
      .from('profiles')
      .select('role, department, em_name')
      .eq('id', user.id)
      .single()

    if (profile) {
      userRole = (profile.role as 'admin' | 'manager' | 'user' | 'resigned') || 'user'
      department = profile.department || '一般部門'
      employeeName = profile.em_name || ''
    }
  }

  // 1. 資安阻擋：已離職同仁不可存取系統
  if (userRole === 'resigned') {
    return (
      <div className="flex h-screen w-screen flex-col items-center justify-center bg-slate-950 p-6 text-center text-slate-200">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-red-500/10 text-3xl text-red-400 border border-red-500/20 shadow-lg mb-4">
          🚫
        </div>
        <h1 className="text-xl font-bold text-white tracking-wide">帳號權限已停用</h1>
        <p className="mt-2 text-sm text-slate-400 max-w-sm">
          {employeeName ? `${employeeName} 同仁您好：` : '同仁您好：'}
          系統顯示您的帳號已處於「已離職」狀態，已解除企業知識庫與內部 SOP 之存取權限。
        </p>

        {/* 提供登出表單按鈕，避免使用者卡在封鎖頁面 */}
        <form action={signout} className="mt-6">
          <button
            type="submit"
            className="rounded-xl bg-slate-800 hover:bg-slate-700 px-5 py-2.5 text-xs font-semibold text-slate-300 transition border border-slate-700 active:scale-95"
          >
            登出此帳號
          </button>
        </form>
      </div>
    )
  }

  // 2. 正常同仁進入對話系統
  return (
    <ChatDashboard
      userEmail={user?.email}
      userId={user?.id}
      userRole={userRole}
      department={department}
      isAdmin={userRole === 'admin'}
      onSignOut={signout}
    />
  )
}