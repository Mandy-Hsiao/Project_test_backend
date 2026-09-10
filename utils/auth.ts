import { createClient } from '@/utils/supabase/server'

export type UserRole = 'admin' | 'manager' | 'user'

export interface AuthContext {
  userId: string
  email: string
  role: UserRole
  department: string
}

/**
 * 從 Supabase 獲取用戶認證上下文
 */
export async function getAuthContext(): Promise<AuthContext | null> {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) return null

  const { data: profile } = await supabase
    .from('profiles')
    .select('role, department')
    .eq('id', user.id)
    .single()

  return {
    userId: user.id,
    email: user.email || '',
    role: (profile?.role as UserRole) || 'user',
    department: profile?.department || '',
  }
}

/**
 * 檢查權限 - 返回 true/false 及可選的錯誤訊息
 */
export function checkPermission(
  authCtx: AuthContext | null,
  requiredRoles: UserRole[],
  optionalDepartment?: string,
): { allowed: boolean; message?: string } {
  if (!authCtx) {
    return { allowed: false, message: '未授權' }
  }

  if (!requiredRoles.includes(authCtx.role)) {
    return { allowed: false, message: `需要 ${requiredRoles.join(',')} 角色` }
  }

  if (optionalDepartment && authCtx.role === 'manager') {
    if (authCtx.department !== optionalDepartment) {
      return { allowed: false, message: '只能訪問自己部門的數據' }
    }
  }

  return { allowed: true }
}

/**
 * 權限檢查裝飾器 - 用於 API 路由
 */
export async function requireAuth(
  requiredRoles: UserRole[] = ['user'],
) {
  const auth = await getAuthContext()
  const { allowed, message } = checkPermission(auth, requiredRoles)

  if (!allowed) {
    throw new Error(message || '無權限')
  }

  return auth!
}

/**
 * 根據用戶角色隱藏/篩選敏感數據
 */
export function filterDataByRole(
  data: any,
  role: UserRole,
  departmentFilter?: string,
) {
  if (role === 'admin') {
    return data // 管理員看全部
  }

  if (role === 'manager') {
    // 主管只看自己部門
    if (Array.isArray(data)) {
      return data.filter((item) => item.department === departmentFilter)
    }
    return data
  }

  // 普通用戶只看個人
  return null
}
