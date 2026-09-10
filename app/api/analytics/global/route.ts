import { createClient } from '@/utils/supabase/server'
import { NextResponse } from 'next/server'

/**
 * 全域高級統計 API - 僅管理員可訪問
 * 返回：跨部門統計、高頻提問領域分析、異常檢測等
 */
export async function GET(req: Request) {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()

  if (!user) return NextResponse.json({ error: '未授權' }, { status: 401 })

  const { data: profile } = await supabase
    .from('profiles')
    .select('role')
    .eq('id', user.id)
    .single()

  if (profile?.role !== 'admin') {
    return NextResponse.json({ error: '需要管理員權限' }, { status: 403 })
  }

  try {
    const { data: chats, error } = await supabase
      .from('chat_history')
      .select('id, question, created_at, profiles(department, role)', {
        count: 'exact',
      })
      .order('created_at', { ascending: false })

    if (error) throw error

    const stats = {
      totalQuestions: chats?.length || 0,
      uniqueUsers: new Set(chats?.map((c) => c.user_id)).size,
      departmentBreakdown: analyzeDepartments(chats || []),
      frequentIssues: extractIssueCategories(chats || []),
      dailyTrend: calculateTrend(chats || []),
      anomalies: detectAnomalies(chats || []),
    }

    return NextResponse.json(stats)
  } catch (error) {
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}

function analyzeDepartments(
  chats: Array<{ profiles: { department: string } | null }>,
): Record<string, { count: number; percentage: number }> {
  const total = chats.length
  const breakdown: Record<string, number> = {}

  chats.forEach((chat) => {
    const dept = chat.profiles?.department || '未知'
    breakdown[dept] = (breakdown[dept] || 0) + 1
  })

  return Object.fromEntries(
    Object.entries(breakdown).map(([dept, count]) => [
      dept,
      { count, percentage: ((count / total) * 100).toFixed(1) },
    ]),
  )
}

function extractIssueCategories(
  chats: Array<{ question: string }>,
): Array<{
  category: string
  count: number
  examples: string[]
}> {
  const keywords: Record<string, RegExp> = {
    '假期/請假': /假|請假|休假|補班/i,
    '薪資/帳戶': /薪|帳|戶|薪資|薪水/i,
    '系統/工具': /系統|工具|軟體|應用|APP|IT/i,
    '會議/出差': /會議|出差|報告|簽核/i,
    '考績/評核': /考績|評核|績效|考核/i,
    '招聘/離職': /招|離職|辭職|應徵/i,
  }

  const categorized: Record<string, Set<string>> = {}

  chats.forEach((chat) => {
    const q = chat.question
    for (const [category, regex] of Object.entries(keywords)) {
      if (regex.test(q)) {
        if (!categorized[category]) categorized[category] = new Set()
        categorized[category].add(q.substring(0, 80))
        break
      }
    }
  })

  return Object.entries(categorized)
    .map(([category, examples]) => ({
      category,
      count: examples.size,
      examples: Array.from(examples).slice(0, 3),
    }))
    .sort((a, b) => b.count - a.count)
}

function calculateTrend(
  chats: Array<{ created_at: string }>,
): Record<string, number> {
  const trend: Record<string, number> = {}
  chats.forEach((chat) => {
    const date = new Date(chat.created_at).toISOString().split('T')[0]
    trend[date] = (trend[date] || 0) + 1
  })
  return trend
}

function detectAnomalies(
  chats: Array<{ created_at: string; user_id: string }>,
): Array<{ type: string; description: string; severity: 'low' | 'medium' | 'high' }> {
  const anomalies = []

  // 異常 1: 單一用戶短時間內大量提問
  const userCounts: Record<string, number> = {}
  chats.slice(0, 100).forEach((c) => {
    userCounts[c.user_id] = (userCounts[c.user_id] || 0) + 1
  })

  const suspicious = Object.entries(userCounts)
    .filter(([, count]) => count > 10)
    .map(([userId, count]) => ({
      type: '異常提問頻率',
      description: `用戶 ${userId.substring(0, 8)} 在短時間內提問 ${count} 次`,
      severity: 'medium' as const,
    }))

  anomalies.push(...suspicious)

  // 異常 2: 系統錯誤率高
  const last24h = new Date(Date.now() - 24 * 60 * 60 * 1000)
  const recentErrors = chats.filter(
    (c) => new Date(c.created_at) > last24h,
  ).length

  if (recentErrors > 50) {
    anomalies.push({
      type: '高提問量',
      description: `過去 24 小時內有 ${recentErrors} 次提問`,
      severity: 'low',
    })
  }

  return anomalies
}
