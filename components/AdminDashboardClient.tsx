'use client'

import React, { useState } from 'react'
import AnalyticsPanel from '@/components/AnalyticsPanel'
import AdminUserManagement from '@/components/AdminUserManagement'
import Link from 'next/link'

interface AdminDashboardClientProps {
  user: { email?: string }
  isAdmin: boolean
  isManager?: boolean
  department: string
  userRole: 'admin' | 'manager' | 'user'
  initialMembers?: any[] // 接收伺服器端傳來的同仁名單，解決報錯
}

export default function AdminDashboardClient({
  user,
  isAdmin,
  isManager = false,
  department,
  userRole,
  initialMembers = [],
}: AdminDashboardClientProps) {
  const [activeTab, setActiveTab] = useState<'global' | 'department' | 'personal' | 'users'>(
    isAdmin ? 'global' : isManager ? 'department' : 'personal',
  )

  // ③ 角色分級頁籤：主管 (Manager) 也能查看本部門同仁名單
  const tabs: Array<{
    id: 'global' | 'department' | 'personal' | 'users'
    label: string
    visible: boolean
  }> = [
    { id: 'global', label: '全域數據', visible: isAdmin },
    { id: 'department', label: '部門分析', visible: isManager },
    { id: 'personal', label: '個人歷史', visible: true },
    {
      id: 'users',
      label: isAdmin ? '全域用戶管理' : '部門同仁名單',
      visible: isAdmin || isManager,
    },
  ]

  const visibleTabs = tabs.filter((t) => t.visible)

  const roleLabel = isAdmin ? '最高管理員' : isManager ? '部門主管' : '一般同仁'

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* 頂部導航 */}
      <header className="h-14 border-b border-slate-800 bg-slate-950 px-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="text-xl">📊</div>
          <div>
            <h1 className="text-sm font-bold text-white">
              {isAdmin
                ? 'SOP 知識庫全域監控'
                : isManager
                  ? `【${department}】部門數據分析`
                  : '我的提問歷史後台'}
            </h1>
            <p className="text-xs text-slate-400">{roleLabel}視圖</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-slate-400">{user.email}</span>
          <Link
            href="/"
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 rounded border border-slate-700 transition text-slate-200"
          >
            ← 返回對話
          </Link>
        </div>
      </header>

      {/* Tab 導航列 */}
      <div className="border-b border-slate-800 bg-slate-900 px-6">
        <div className="flex gap-1">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium transition border-b-2 ${
                activeTab === tab.id
                  ? 'border-emerald-500 text-emerald-400'
                  : 'border-transparent text-slate-400 hover:text-slate-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 內容區域 */}
      <main className="flex-1 p-6 max-w-6xl mx-auto w-full">
        {activeTab === 'users' ? (
          <AdminUserManagement
            isAdmin={isAdmin}
            isManager={isManager}
            currentDepartment={department}
            initialMembers={initialMembers}
          />
        ) : (
          <AnalyticsPanel
            scope={activeTab as 'global' | 'department' | 'personal'}
            department={activeTab === 'department' ? department : undefined}
            userRole={userRole}
          />
        )}
      </main>
    </div>
  )
}