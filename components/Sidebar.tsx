'use client'

import React, { useState } from 'react'
import Link from 'next/link'

export interface HistoryItem {
  id: string
  question: string
  answer?: string | null
  rating?: number | null
  created_at: string
}

interface SidebarProps {
  userEmail?: string
  employeeName?: string
  userRole?: 'admin' | 'manager' | 'user' | string
  department?: string
  isAdmin?: boolean
  onSignOut: () => void
  history: HistoryItem[]
  activeHistoryId?: string | null
  onSelectHistory: (item: HistoryItem) => void
  onDeleteHistory?: (e: React.MouseEvent, id: string) => void
  onRenameHistory?: (id: string, newTitle: string) => Promise<void> // 👈 新增更名函式
  onNewChat: () => void
}

export default function Sidebar({
  userEmail,
  employeeName,
  userRole = 'user',
  department = '',
  isAdmin,
  onSignOut,
  history,
  activeHistoryId,
  onSelectHistory,
  onDeleteHistory,
  onRenameHistory,
  onNewChat,
}: SidebarProps) {
  // 編輯中的狀態管理
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingText, setEditingText] = useState<string>('')

  const normalizedRole = userRole?.toLowerCase() || 'user'
  const checkAdmin = isAdmin || normalizedRole === 'admin'
  const checkManager = normalizedRole === 'manager'
  const hasDashboardAccess = true

  const formatTime = (dateStr: string) => {
    try {
      const d = new Date(dateStr)
      const now = new Date()
      if (d.toDateString() === now.toDateString()) {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      return `${d.getMonth() + 1}/${d.getDate()}`
    } catch {
      return ''
    }
  }

  // 觸發開始編輯
  const handleStartRename = (e: React.MouseEvent, item: HistoryItem) => {
    e.stopPropagation()
    setEditingId(item.id)
    setEditingText(item.question)
  }

  // 儲存新標題
  const handleSaveRename = async (e: React.MouseEvent | React.KeyboardEvent, id: string) => {
    e.stopPropagation()
    const trimmed = editingText.trim()
    if (trimmed && onRenameHistory) {
      await onRenameHistory(id, trimmed)
    }
    setEditingId(null)
  }

  // 取消編輯
  const handleCancelRename = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation()
    setEditingId(null)
  }

  return (
    <aside className="w-72 bg-slate-900 text-slate-200 flex flex-col justify-between border-r border-slate-800 select-none">
      {/* 上半部：Logo 與歷史清單 */}
      <div className="p-4 flex flex-col h-full overflow-hidden">
        {/* 系統標題 */}
        <div className="flex items-center gap-2 mb-4 px-2">
          <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-md">
            SOP
          </div>
          <div>
            <h1 className="font-semibold text-sm text-white tracking-wide">企業智能知識庫</h1>
            <p className="text-[11px] text-slate-400">RAG AI 檢索系統</p>
          </div>
        </div>

        {/* 開啟新對話按鈕 */}
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-sm transition active:scale-[0.98]"
        >
          <span>+</span> 開啟新對話
        </button>

        {/* 歷史提問紀錄清單 */}
        <div className="mt-5 flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-2 mb-2">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              提問歷史紀錄
            </span>
            <span className="text-[10px] text-slate-500">{history.length} 則</span>
          </div>

          <div className="flex-1 overflow-y-auto space-y-1 pr-1 custom-scrollbar">
            {history.length === 0 ? (
              <div className="text-center py-10 text-xs text-slate-500">
                尚無提問紀錄<br />
                <span className="text-[10px] text-slate-600">在右側發問後將自動儲存</span>
              </div>
            ) : (
              history.map((item) => (
                <div
                  key={item.id}
                  onClick={() => onSelectHistory(item)}
                  className={`group relative flex items-center justify-between rounded-lg px-2.5 py-2 text-xs cursor-pointer transition ${
                    activeHistoryId === item.id
                      ? 'bg-blue-600/20 text-blue-300 border border-blue-500/30 font-medium'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  {/* 若正在編輯此項目，顯示輸入框 */}
                  {editingId === item.id ? (
                    <div className="flex items-center gap-1 w-full" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="text"
                        autoFocus
                        value={editingText}
                        onChange={(e) => setEditingText(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveRename(e, item.id)
                          if (e.key === 'Escape') handleCancelRename(e)
                        }}
                        className="flex-1 bg-slate-950 border border-blue-500 rounded px-1.5 py-0.5 text-xs text-white outline-none"
                      />
                      {/* 勾選儲存 */}
                      <button
                        title="儲存名稱"
                        onClick={(e) => handleSaveRename(e, item.id)}
                        className="p-1 text-emerald-400 hover:bg-emerald-500/10 rounded"
                      >
                        ✓
                      </button>
                      {/* 取消 */}
                      <button
                        title="取消"
                        onClick={handleCancelRename}
                        className="p-1 text-slate-400 hover:bg-slate-700 rounded"
                      >
                        ✕
                      </button>
                    </div>
                  ) : (
                    /* 正常顯示狀態 */
                    <>
                      <div className="flex items-center gap-1.5 truncate pr-14">
                        <span className="text-slate-500">💬</span>
                        <span className="truncate">{item.question}</span>
                        {item.rating === 1 && (
                          <span className="text-[10px] text-emerald-400 shrink-0" title="已評分：滿意">
                            👍
                          </span>
                        )}
                        {item.rating === -1 && (
                          <span className="text-[10px] text-rose-400 shrink-0" title="已評分：待改進">
                            👎
                          </span>
                        )}
                      </div>

                      <div className="absolute right-2 flex items-center gap-1">
                        {/* 平常顯示建立時間 */}
                        <span className="text-[10px] text-slate-500 group-hover:hidden">
                          {formatTime(item.created_at)}
                        </span>

                        {/* 編輯名稱按鈕（滑鼠懸浮時出現） */}
                        {onRenameHistory && (
                          <button
                            title="編輯名稱"
                            onClick={(e) => handleStartRename(e, item)}
                            className="hidden group-hover:flex items-center justify-center p-1 rounded text-slate-400 hover:text-blue-400 hover:bg-blue-500/10 transition"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              className="h-3.5 w-3.5"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                              />
                            </svg>
                          </button>
                        )}

                        {/* 垃圾桶刪除按鈕（滑鼠懸浮時出現） */}
                        {onDeleteHistory && (
                          <button
                            title="刪除此紀錄"
                            onClick={(e) => onDeleteHistory(e, item.id)}
                            className="hidden group-hover:flex items-center justify-center p-1 rounded text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition"
                          >
                            <svg
                              xmlns="http://www.w3.org/2000/svg"
                              className="h-3.5 w-3.5"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                              />
                            </svg>
                          </button>
                        )}
                      </div>
                    </>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* 下半部：後台入口 + 個人資訊名牌 */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/60 flex flex-col gap-2">
        {hasDashboardAccess && (
          <Link
            href="/admin"
            className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium border transition shadow-sm ${
              checkAdmin
                ? 'text-amber-300 bg-amber-500/10 border-amber-500/20 hover:bg-amber-500/20'
                : checkManager
                  ? 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20 hover:bg-emerald-500/20'
                  : 'text-blue-300 bg-blue-500/10 border-blue-500/20 hover:bg-blue-500/20'
            }`}
          >
            <span className="flex items-center gap-2">
              <span>📊</span>
              <span>
                {checkAdmin
                  ? '全系統管理後台'
                  : checkManager
                    ? `${department || '部門'}數據後台`
                    : '我的提問歷史後台'}
              </span>
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                checkAdmin
                  ? 'bg-amber-500/30 text-amber-200'
                  : checkManager
                    ? 'bg-emerald-500/30 text-emerald-200'
                    : 'bg-blue-500/30 text-blue-200'
              }`}
            >
              {checkAdmin ? 'Admin' : checkManager ? 'Manager' : 'User'}
            </span>
          </Link>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 px-1">
          <div className="flex items-center gap-2 truncate max-w-[170px]">
            <div
              className={`h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                checkAdmin
                  ? 'bg-amber-500/20 text-amber-400'
                  : checkManager
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-blue-500/20 text-blue-400'
              }`}
            >
              {employeeName ? employeeName.slice(0, 1) : checkAdmin ? 'A' : checkManager ? 'M' : 'U'}
            </div>
            <div className="flex flex-col truncate leading-tight">
              <span className="text-xs text-slate-200 font-medium truncate">
                {employeeName || userEmail || '使用者'}
              </span>
              <span className="text-[10px] text-slate-500 truncate">
                {department ? `${department}` : ''}
                {department && userEmail ? ' · ' : ''}
                {userEmail}
              </span>
            </div>
          </div>
          <button
            onClick={onSignOut}
            className="text-[11px] text-red-400 hover:text-red-300 font-medium px-2 py-1 rounded hover:bg-red-500/10 transition"
          >
            登出
          </button>
        </div>
      </div>
    </aside>
  )
}