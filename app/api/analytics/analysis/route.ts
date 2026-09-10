import { createClient } from '@/utils/supabase/server'
import { createAdminClient } from '@/utils/supabase/admin'
import { NextResponse } from 'next/server'

/**
 * 常見提問分析 - 按主題分類並識別高頻問題
 */
export async function GET(req: Request) {
  try {
    const supabase = await createClient()
    const {
      data: { user },
    } = await supabase.auth.getUser()

    if (!user) {
      return NextResponse.json({ error: '未授權' }, { status: 401 })
    }

    const { searchParams } = new URL(req.url)
    const scope = (searchParams.get('scope') as 'global' | 'department' | 'personal') || 'personal'
    const department = searchParams.get('department') || ''

    // 權限檢查
    const { data: profile, error: profileError } = await supabase
      .from('profiles')
      .select('role, department')
      .eq('id', user.id)
      .single()

    if (profileError) {
      console.warn('[Analysis API] Profile error:', profileError.message)
    }

    const userRole = profile?.role || 'user'
    const userDept = profile?.department || ''

    if (scope === 'global' && userRole !== 'admin') {
      return NextResponse.json({ error: '無全域權限' }, { status: 403 })
    }
    if (scope === 'department' && userRole !== 'admin' && userRole !== 'manager') {
      return NextResponse.json({ error: '無部門權限' }, { status: 403 })
    }
    if (scope === 'department' && userRole === 'manager' && department && department !== userDept) {
      return NextResponse.json({ error: '只能查看自己部門' }, { status: 403 })
    }

    // 個人數據用一般 client，部門與全域數據使用 admin client 繞過 RLS
    const db: any = scope === 'personal' ? supabase : createAdminClient()

    // 查詢提問
    let query = db.from('chat_history').select('*')

    if (scope === 'personal') {
      query = query.eq('user_id', user.id)
    } else if (scope === 'department') {
      const deptToQuery = department || userDept
      if (deptToQuery) {
        // 排除 admin 帳號，只統計該部門的主管與員工
        const { data: deptUsers, error: deptUsersError } = await db
          .from('profiles')
          .select('id')
          .eq('department', deptToQuery)
          .neq('role', 'admin')

        if (deptUsersError) {
          console.error('[Analysis API] Department users query error:', deptUsersError)
        }

        const userIds = deptUsers?.map((u: any) => u.id) || []
        if (userIds.length > 0) {
          query = query.in('user_id', userIds)
        } else {
          return NextResponse.json({
            totalQuestions: 0,
            uniqueQuestions: 0,
            categories: [],
            uncategorized: [],
            summary: {
              mostCommonCategory: '暫無數據',
              averageQuestionsPerDay: '0',
              peakHour: '-- (需時間數據)',
            },
          })
        }
      }
    }

    const { data: chats, error } = await query.order('created_at', { ascending: false })

    if (error) {
      console.error('[Analysis] Query error:', error)
      return NextResponse.json({ error: '查詢失敗' }, { status: 500 })
    }

    // 分析提問內容
    const analysis = analyzeQuestions(chats || [])

    console.log('[Analysis] Analyzed', chats?.length || 0, 'questions')

    return NextResponse.json(analysis)
  } catch (error) {
    console.error('[Analysis] Unexpected error:', error)
    return NextResponse.json({ error: String(error) }, { status: 500 })
  }
}

/**
 * 核心分析邏輯 - 分類常見提問
 */
function analyzeQuestions(chats: any[]) {
  const categories = {
    假期請假: { keywords: ['假', '請假', '休假', '補班', '年假', '病假', '特休'], issues: [] as any[] },
    薪資帳戶: { keywords: ['薪', '帳', '薪資', '薪水', '發薪', '扣款'], issues: [] as any[] },
    系統工具: { keywords: ['系統', '工具', '軟體', '應用', 'app', 'it', '登入', '帳號'], issues: [] as any[] },
    會議出差: { keywords: ['會議', '出差', '報告', '簽核', '核准', '差旅'], issues: [] as any[] },
    考績評核: { keywords: ['考績', '評核', '績效', '考核', '獎金', '晉升'], issues: [] as any[] },
    招聘人事: { keywords: ['招', '招聘', '應徵', '離職', '辭職', '員工'], issues: [] as any[] },
    福利保險: { keywords: ['福利', '保險', '醫療', '體檢', '保障'], issues: [] as any[] },
    流程規定: { keywords: ['流程', '規定', '規則', '政策', '標準', '辦法'], issues: [] as any[] },
  }

  const questionFrequency = new Map<string, number>()
  const uncategorized: any[] = []

  // 第一遍：統計重複問題
  chats.forEach((chat) => {
    const q = (chat.question || '').trim()
    if (q.length === 0) return

    const normalized = q.replace(/[？?。，、！\s]+$/g, '').toLowerCase()
    if (normalized.length === 0) return

    questionFrequency.set(q, (questionFrequency.get(q) || 0) + 1)
  })

  // 第二遍：分類問題
  Array.from(questionFrequency.entries())
    .sort((a, b) => b[1] - a[1])
    .forEach(([question, count]) => {
      let categorized = false
      const lowerQ = question.toLowerCase()

      for (const [categoryName, categoryData] of Object.entries(categories)) {
        if (
          categoryData.keywords.some((kw) => lowerQ.includes(kw))
        ) {
          categoryData.issues.push({
            question: question.substring(0, 80),
            count,
          })
          categorized = true
          break
        }
      }

      if (!categorized) {
        uncategorized.push({
          question: question.substring(0, 80),
          count,
        })
      }
    })

  // 構建最終分析結果
  const categorizedIssues = Object.entries(categories)
    .filter(([, data]) => data.issues.length > 0)
    .map(([name, data]) => ({
      category: name,
      count: data.issues.reduce((sum, issue) => sum + issue.count, 0),
      issues: data.issues.slice(0, 5), // 每個分類最多顯示 5 個
      percentage: '0',
    }))
    .sort((a, b) => b.count - a.count)

  // 計算百分比
  const totalIssues = categorizedIssues.reduce((sum, c) => sum + c.count, 0)
  categorizedIssues.forEach((c) => {
    c.percentage = totalIssues > 0 ? ((c.count / totalIssues) * 100).toFixed(1) : '0'
  })

  // 高頻未分類問題
  const topUncategorized = uncategorized.slice(0, 5)

  return {
    totalQuestions: chats.length,
    uniqueQuestions: questionFrequency.size,
    categories: categorizedIssues,
    uncategorized: topUncategorized,
    summary: {
      mostCommonCategory: categorizedIssues[0]?.category || '暫無數據',
      averageQuestionsPerDay: calculateDailyAverage(chats),
      peakHour: '-- (需時間數據)',
    },
  }
}

function calculateDailyAverage(chats: any[]): string {
  if (chats.length === 0) return '0'

  const dates = new Set(
    chats.map((c: any) => new Date(c.created_at).toISOString().split('T')[0]),
  )

  const avg = (chats.length / dates.size).toFixed(1)
  return avg
}