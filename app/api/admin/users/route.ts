import { createClient } from '@/utils/supabase/server'
import { createAdminClient } from '@/utils/supabase/admin'
import { NextResponse } from 'next/server'

// 管理員獲取所有用戶及其角色
export async function GET(req: Request) {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) return NextResponse.json({ error: '未授權' }, { status: 401 })

    const { data: profile, error: profileError } = await supabase
      .from('profiles')
      .select('role')
      .eq('id', user.id)
      .single()

    if (profileError) {
      console.warn('[Admin Users] Profile error:', profileError)
      // 降級：不允許訪問
      return NextResponse.json({ error: '無管理員權限' }, { status: 403 })
    }

    if (profile?.role !== 'admin') {
      return NextResponse.json({ error: '需要管理員權限' }, { status: 403 })
    }

    // 讀取「所有」使用者要用 service role client 繞過 RLS，
    // 一般 client 若 RLS 只允許 `auth.uid() = id`，管理員也只會查到自己那一列
    const adminDb = createAdminClient()
    const { data: users, error: usersError } = await adminDb
      .from('profiles')
      .select('id, role, department, created_at')
      .order('created_at', { ascending: false })

    if (usersError) {
      console.error('[Admin Users] Query error:', usersError)
      return NextResponse.json({ error: '查詢失敗' }, { status: 500 })
    }

    // 統計各角色人數
    const roleStats = { admin: 0, manager: 0, user: 0 }
    users?.forEach((u) => {
      const role = u.role as keyof typeof roleStats
      if (roleStats.hasOwnProperty(role)) {
        roleStats[role]++
      }
    })

    return NextResponse.json({ users: users || [], roleStats })
  } catch (error) {
    console.error('[Admin Users] Unexpected error:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}

// 管理員修改用戶角色
export async function POST(req: Request) {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) return NextResponse.json({ error: '未授權' }, { status: 401 })

    const { data: profile, error: profileError } = await supabase
      .from('profiles')
      .select('role')
      .eq('id', user.id)
      .single()

    if (profileError || profile?.role !== 'admin') {
      return NextResponse.json({ error: '需要管理員權限' }, { status: 403 })
    }

    const { userId, newRole } = await req.json()

    if (!userId || !newRole) {
      return NextResponse.json({ error: '缺少必要參數' }, { status: 400 })
    }

    if (!['admin', 'manager', 'user'].includes(newRole)) {
      return NextResponse.json({ error: '無效的角色' }, { status: 400 })
    }

    // 修改「別人」的角色同樣要用 service role client 繞過 RLS
    const adminDb = createAdminClient()
    const { error: updateError } = await adminDb
      .from('profiles')
      .update({ role: newRole })
      .eq('id', userId)

    if (updateError) {
      console.error('[Admin Users] Update error:', updateError)
      return NextResponse.json({ error: '更新失敗' }, { status: 500 })
    }

    return NextResponse.json({ success: true, message: '角色已更新' })
  } catch (error) {
    console.error('[Admin Users] Unexpected error:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}