'use client'

import React, { useEffect, useState } from 'react'

interface TopQuestion {
  question: string
  count: number
}

interface StatsData {
  totalQuestions: number
  uniqueUsers: number
  questionsPerDay: Record<string, number>
  departmentBreakdown?: Record<string, { count: number; percentage: string }>
  topQuestions: TopQuestion[]
}

interface AnalyticsPanelProps {
  scope: 'global' | 'department' | 'personal'
  department?: string
  userRole: 'admin' | 'manager' | 'user'
}

export default function AnalyticsPanel({
  scope,
  department,
  userRole,
}: AnalyticsPanelProps) {
  const [data, setData] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchStats() {
      try {
        setLoading(true)
        setError(null)
        const params = new URLSearchParams({ scope })
        if (department) params.append('department', department)

        console.log(`[AnalyticsPanel] Fetching ${scope} data for department: ${department}`)

        const res = await fetch(`/api/analytics/stats?${params}`)
        const result = await res.json()

        if (!res.ok) {
          throw new Error(result.error || `HTTP ${res.status}`)
        }

        console.log(`[AnalyticsPanel] Data loaded successfully:`, result)
        setData(result)
      } catch (err) {
        const errorMsg = String(err)
        console.error(`[AnalyticsPanel] Error:`, errorMsg)
        setError(errorMsg)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
  }, [scope, department])

  if (loading)
    return (
      <div className="text-center text-slate-400 py-12 bg-slate-800/40 rounded-lg border border-slate-700">
        ⏳ 載入數據中...
      </div>
    )

  if (error)
    return (
      <div className="text-center py-8 bg-red-900/20 border border-red-700 rounded-lg p-4">
        <div className="text-red-400 font-bold mb-2">⚠️ 錯誤</div>
        <div className="text-red-300 text-sm">{error}</div>
        <div className="text-slate-400 text-xs mt-2">
          {scope === 'global'
            ? '無法載入全域數據，請確認您有管理員權限'
            : scope === 'department'
              ? '無法載入部門數據，請確認您是該部門的主管'
              : '無法載入個人數據'}
        </div>
      </div>
    )

  if (!data)
    return (
      <div className="text-center text-slate-400 py-12">
        暫無數據
      </div>
    )

  const weekTrend = getWeekTrend(data.questionsPerDay)
  const isPersonal = scope === 'personal'

  return (
    <div className="space-y-6">
      {/* 核心指標：個人歷史不需要「活躍人數」與「平均每人提問」，這兩個指標只在部門/全域才有意義 */}
      <div className={`grid gap-4 ${isPersonal ? 'grid-cols-1 sm:w-64' : 'grid-cols-3'}`}>
        <MetricCard
          label={isPersonal ? '我的總提問數' : '總提問數'}
          value={data.totalQuestions}
          trend={weekTrend}
          color="emerald"
        />
        {!isPersonal && (
          <>
            <MetricCard
              label="活躍人數"
              value={data.uniqueUsers}
              color="blue"
            />
            <MetricCard
              label="平均每人提問"
              value={(data.totalQuestions / Math.max(data.uniqueUsers, 1)).toFixed(1)}
              color="amber"
            />
          </>
        )}
      </div>

      {/* 高頻提問分析 */}
      <div className="bg-slate-800/60 border border-slate-700 p-4 rounded-lg">
        <h3 className="text-sm font-bold text-white mb-3">
          {isPersonal ? '我的常見提問（前 10）' : '常見提問（前 10）'}
        </h3>
        {data.topQuestions.length === 0 ? (
          <div className="text-slate-400 text-xs py-4 text-center">暫無提問數據</div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {data.topQuestions.map((q, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="text-slate-300 flex-1 truncate pr-2">
                  {i + 1}. {q.question}
                </span>
                <span className="text-emerald-400 font-bold">{q.count}x</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 部門分佈（管理員視圖） */}
      {userRole === 'admin' && data.departmentBreakdown && Object.keys(data.departmentBreakdown).length > 0 && (
        <div className="bg-slate-800/60 border border-slate-700 p-4 rounded-lg">
          <h3 className="text-sm font-bold text-white mb-3">
            部門提問分佈
          </h3>
          <div className="space-y-2">
            {Object.entries(data.departmentBreakdown)
              .sort(([, a], [, b]) => b.count - a.count)
              .map(([dept, { count, percentage }]) => (
                <div key={dept} className="flex items-center gap-2 text-xs">
                  <div className="flex-1 bg-slate-700 rounded-full h-5 relative overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all"
                      style={{
                        width: `${Number(percentage)}%`,
                      }}
                    />
                  </div>
                  <span className="w-32 text-slate-300">{dept}</span>
                  <span className="text-slate-400 w-12 text-right">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

function MetricCard({
  label,
  value,
  trend,
  color = 'slate',
}: {
  label: string
  value: string | number
  trend?: string
  color?: string
}) {
  const colorMap: Record<string, string> = {
    emerald: 'from-emerald-500 to-emerald-400',
    blue: 'from-blue-500 to-cyan-400',
    amber: 'from-amber-500 to-orange-400',
    slate: 'from-slate-500 to-slate-400',
  }

  return (
    <div className="bg-slate-800/60 border border-slate-700 p-4 rounded-lg overflow-hidden relative">
      <div
        className={`absolute inset-0 bg-gradient-to-br ${colorMap[color]} opacity-5`}
      />
      <div className="relative z-10">
        <span className="text-xs text-slate-400">{label}</span>
        <div className="text-2xl font-bold text-white mt-1">{value}</div>
        {trend && <span className="text-xs text-emerald-400 mt-1 block">↑ {trend}</span>}
      </div>
    </div>
  )
}

function getWeekTrend(dailyData: Record<string, number>): string {
  const dates = Object.keys(dailyData)
    .sort()
    .slice(-7)
  if (dates.length < 2) return '0%'

  const prev = dates.slice(0, Math.floor(dates.length / 2))
  const curr = dates.slice(Math.floor(dates.length / 2))

  const prevSum = prev.reduce((a, d) => a + (dailyData[d] || 0), 0)
  const currSum = curr.reduce((a, d) => a + (dailyData[d] || 0), 0)

  if (prevSum === 0) return '0%'
  const growth = (((currSum - prevSum) / prevSum) * 100).toFixed(0)
  return `${growth}% (本週)`
}