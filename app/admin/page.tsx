import { createClient } from '@/utils/supabase/server'
import { redirect } from 'next/navigation'
import AdminDashboardClient from '@/components/AdminDashboardClient'

export default async function AdminDashboardPage() {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // 1. 查詢當前使用者的身分、部門與姓名
  const { data: profile, error: profileError } = await supabase
    .from('profiles')
    .select('role, department, em_name')
    .eq('id', user.id)
    .single()

  if (profileError) {
    console.error('[Admin] Profile query error:', profileError)
  }

  const role = (profile?.role as 'admin' | 'manager' | 'user' | 'resigned') || 'user'
  const department = profile?.department || '未分配部門'

  // 2. 資安防護：已離職人員直接踢出後台
  if (role === 'resigned') {
    redirect('/')
  }

  const isAdmin = role === 'admin'
  const isManager = role === 'manager'

  // 3. 依角色權限抓取同仁名單（實作 ③ 權限分級檢視）
  let membersQuery = supabase
    .from('profiles')
    .select('id, email, em_name, role, department, created_at')
    .order('created_at', { ascending: true })

  // 主管只能看自己部門的同仁，Admin 可以看全公司
  if (isManager) {
    membersQuery = membersQuery.eq('department', department)
  }

  const { data: members, error: membersError } = await membersQuery

  if (membersError) {
    console.error('[Admin] 取得同仁名單失敗:', membersError.message)
  }

  return (
    <AdminDashboardClient
      user={user}
      isAdmin={isAdmin}
      isManager={isManager}
      department={department}
      userRole={role}
      initialMembers={members || []} 
    />
  )
}