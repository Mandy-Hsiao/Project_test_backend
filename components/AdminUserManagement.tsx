'use client'

import React, { useState, useEffect } from 'react'
import { createClient } from '@/utils/supabase/client'

export interface ProfileItem {
  id: string
  email: string
  em_name: string | null
  role: 'admin' | 'manager' | 'user' | 'resigned'
  department: string | null
  created_at: string
}

interface AdminUserManagementProps {
  isAdmin: boolean
  isManager: boolean
  currentDepartment: string
  initialMembers?: ProfileItem[] // 👈 補上此型別宣告，解決上一層傳遞時的報錯
}

// 預設可選擇的部門清單
const DEPARTMENT_OPTIONS = ['資訊部', '業務部', '風控部', '稽核部', '財務部', '管理部', '一般部門']

export default function AdminUserManagement({
  isAdmin,
  isManager,
  currentDepartment,
  initialMembers = [], // 👈 預設為空陣列
}: AdminUserManagementProps) {
  const supabase = createClient()
  // 以伺服器傳入的名單作為初始值；若已有名單則不需進入載入中狀態
  const [members, setMembers] = useState<ProfileItem[]>(initialMembers)
  const [loading, setLoading] = useState<boolean>(initialMembers.length === 0)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [deptFilter, setDeptFilter] = useState<string>('all')

  // 1. 若伺服器端未帶入資料，則由前端客戶端補抓（③ 名單分級）
  useEffect(() => {
    if (initialMembers.length === 0) {
      fetchMembers()
    }
  }, [])

  const fetchMembers = async () => {
    setLoading(true)
    let query = supabase.from('profiles').select('*').order('created_at', { ascending: true })

    // 若為主管，強制只抓取所屬部門名單
    if (isManager && !isAdmin) {
      query = query.eq('department', currentDepartment)
    }

    const { data, error } = await query
    if (!error && data) {
      setMembers(data as ProfileItem[])
    }
    setLoading(false)
  }

  // 2. 更新同仁資料（④ 角色/離職、⑤ 部門、⑥ 姓名）
  const handleUpdate = async (id: string, updates: Partial<ProfileItem>) => {
    setSavingId(id)

    const { error } = await supabase.from('profiles').update(updates).eq('id', id)

    if (error) {
      alert(`更新失敗：${error.message}`)
    } else {
      setMembers((prev) =>
        prev.map((item) => (item.id === id ? { ...item, ...updates } : item))
      )
    }
    setSavingId(null)
  }

  // 篩選後名單
  const filteredMembers = members.filter((member) => {
    if (isAdmin && deptFilter !== 'all') {
      return member.department === deptFilter
    }
    return true
  })

  return (
    <div className="space-y-6">
      {/* 頂部說明與篩選列 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-950 p-4 rounded-xl border border-slate-800">
        <div>
          <h2 className="text-base font-bold text-white">同仁帳號與職務維護</h2>
          <p className="text-xs text-slate-400 mt-1">
            {isAdmin
              ? '可調整全公司人員之部門歸屬、操作權限或標記為已離職'
              : `僅檢視與管理【${currentDepartment}】同仁`}
          </p>
        </div>

        {/* Admin 專用部門快速篩選 */}
        {isAdmin && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">篩選部門：</span>
            <select
              value={deptFilter}
              onChange={(e) => setDeptFilter(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="all">全公司部門 (全部)</option>
              {DEPARTMENT_OPTIONS.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* 同仁清單表格 */}
      <div className="bg-slate-950 rounded-xl border border-slate-800 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-xs text-slate-400">資料讀取中...</div>
        ) : filteredMembers.length === 0 ? (
          <div className="p-8 text-center text-xs text-slate-400">目前尚無同仁資料</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900 text-slate-400 border-b border-slate-800 uppercase text-[11px]">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">同仁姓名</th>
                  <th className="py-3.5 px-4 font-semibold">電子信箱 (帳號)</th>
                  <th className="py-3.5 px-4 font-semibold">所屬部門</th>
                  <th className="py-3.5 px-4 font-semibold">系統身分 / 在職狀態</th>
                  <th className="py-3.5 px-4 font-semibold text-center">狀態</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filteredMembers.map((member) => (
                  <tr
                    key={member.id}
                    className={`hover:bg-slate-900/50 transition ${
                      member.role === 'resigned' ? 'opacity-60 bg-red-950/10' : ''
                    }`}
                  >
                    {/* ⑥ 員工姓名（輸入後失焦自動儲存） */}
                    <td className="py-3 px-4">
                      <input
                        type="text"
                        defaultValue={member.em_name || ''}
                        placeholder="請輸入姓名"
                        onBlur={(e) => {
                          if (e.target.value !== (member.em_name || '')) {
                            handleUpdate(member.id, { em_name: e.target.value })
                          }
                        }}
                        className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 w-28 focus:outline-none focus:border-emerald-500"
                      />
                    </td>

                    {/* Email 帳號 */}
                    <td className="py-3 px-4 font-mono text-slate-400">{member.email}</td>

                    {/* ⑤ 可更改部門（下拉選單） */}
                    <td className="py-3 px-4">
                      <select
                        value={member.department || '一般部門'}
                        disabled={!isAdmin && isManager}
                        onChange={(e) => handleUpdate(member.id, { department: e.target.value })}
                        className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-200 focus:outline-none focus:border-emerald-500 disabled:opacity-50"
                      >
                        {DEPARTMENT_OPTIONS.map((dept) => (
                          <option key={dept} value={dept}>
                            {dept}
                          </option>
                        ))}
                      </select>
                    </td>

                    {/* ④ 角色維護（包含已離職 resigned） */}
                    <td className="py-3 px-4">
                      <select
                        value={member.role}
                        onChange={(e) =>
                          handleUpdate(member.id, {
                            role: e.target.value as 'admin' | 'manager' | 'user' | 'resigned',
                          })
                        }
                        className={`rounded px-2.5 py-1 text-xs font-medium border focus:outline-none ${
                          member.role === 'admin'
                            ? 'bg-purple-900/30 text-purple-300 border-purple-700'
                            : member.role === 'manager'
                              ? 'bg-blue-900/30 text-blue-300 border-blue-700'
                              : member.role === 'resigned'
                                ? 'bg-red-900/30 text-red-300 border-red-700 font-bold'
                                : 'bg-slate-800 text-slate-300 border-slate-700'
                        }`}
                      >
                        <option value="user">一般同仁 (User)</option>
                        <option value="manager">部門主管 (Manager)</option>
                        <option value="admin">最高管理員 (Admin)</option>
                        <option value="resigned">🚫 已離職 (Resigned)</option>
                      </select>
                    </td>

                    {/* 儲存中狀態提示 */}
                    <td className="py-3 px-4 text-center">
                      {savingId === member.id ? (
                        <span className="text-[11px] text-emerald-400 animate-pulse">儲存中...</span>
                      ) : member.role === 'resigned' ? (
                        <span className="inline-block px-2 py-0.5 text-[10px] rounded bg-red-500/10 text-red-400 border border-red-500/20">
                          已停用
                        </span>
                      ) : (
                        <span className="inline-block px-2 py-0.5 text-[10px] rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          在職中
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}