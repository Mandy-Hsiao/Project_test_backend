'use client'

import React, { useState, useEffect } from 'react'
import { createClient } from '@/utils/supabase/client'
import Sidebar, { HistoryItem } from './Sidebar'

interface ChatDashboardProps {
  userEmail?: string
  employeeName?: string
  userId?: string
  userRole?: 'admin' | 'manager' | 'user'
  department?: string
  isAdmin?: boolean
  onSignOut: () => void
}

export default function ChatDashboard({
  userEmail,
  employeeName,
  userId,
  userRole = 'user',
  department = '',
  isAdmin,
  onSignOut,
}: ChatDashboardProps) {
  const supabase = createClient()
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<string>('')
  const [currentAnswer, setCurrentAnswer] = useState<string>('')
  const [currentRating, setCurrentRating] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string>('')
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isRatingLoading, setIsRatingLoading] = useState(false)

  // 1. 初始化時載入此使用者的歷史提問紀錄
  useEffect(() => {
    async function loadHistory() {
      if (!userId) return

      const { data, error } = await supabase
        .from('chat_history')
        .select('*')
        .eq('user_id', userId)
        .order('created_at', { ascending: false })

      if (!error && data) {
        setHistory(data)
      }
    }

    loadHistory()
  }, [userId, supabase])

  // 2. 送出問題並呼叫 AI API
  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const questionText = input.trim()
    setInput('')
    setCurrentQuestion(questionText)
    setCurrentAnswer('')
    setCurrentRating(null)
    setErrorMessage('')
    setIsLoading(true)

    let newChatId: string | null = null

    // A. 寫入 Supabase chat_history 資料表
    if (userId) {
      const { data, error } = await supabase
        .from('chat_history')
        .insert([{ user_id: userId, question: questionText }])
        .select()
        .single()

      if (!error && data) {
        newChatId = data.id
        setActiveHistoryId(data.id)
        setHistory((prev) => [data, ...prev])
      }
    }

    // B. 呼叫後端 API 取得回答
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: questionText }),
      })

      const data = await res.json()

      if (!res.ok) {
        throw new Error(data.error || '取得回答失敗')
      }

      const generatedAnswer = data.answer || '未取得有效回覆'
      setCurrentAnswer(generatedAnswer)

      // C. 將 AI 回答同步回存至 Supabase，方便歷史紀錄讀取
      if (newChatId) {
        await supabase
          .from('chat_history')
          .update({ answer: generatedAnswer })
          .eq('id', newChatId)

        setHistory((prev) =>
          prev.map((item) =>
            item.id === newChatId ? { ...item, answer: generatedAnswer } : item
          )
        )
      }
    } catch (error: any) {
      console.error('呼叫 Chat API 失敗:', error)
      setErrorMessage(error.message || '無法取得回答，請稍後再試。')
    } finally {
      setIsLoading(false)
    }
  }

  // 3. 處理評分（Rating 機制）
  const handleRate = async (ratingValue: number) => {
    if (!activeHistoryId || isRatingLoading) return

    const newRating = currentRating === ratingValue ? null : ratingValue
    setIsRatingLoading(true)
    setCurrentRating(newRating)

    const { error } = await supabase
      .from('chat_history')
      .update({ rating: newRating })
      .eq('id', activeHistoryId)

    if (error) {
      console.error('評分失敗:', error.message)
      setCurrentRating(currentRating)
    } else {
      setHistory((prev) =>
        prev.map((item) =>
          item.id === activeHistoryId ? { ...item, rating: newRating } : item
        )
      )
    }
    setIsRatingLoading(false)
  }

  // 4. 點選左側歷史紀錄（同步還原歷史問答與評分狀態）
  const handleSelectHistory = (item: HistoryItem) => {
    setActiveHistoryId(item.id)
    setCurrentQuestion(item.question)
    setCurrentAnswer(item.answer || '（此為舊版提問紀錄，未留存回答文字）')
    setCurrentRating(item.rating ?? null)
    setErrorMessage('')
  }

  // 5. 刪除提問歷史紀錄
  const handleDeleteHistory = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()

    const { error } = await supabase.from('chat_history').delete().eq('id', id)

    if (!error) {
      setHistory((prev) => prev.filter((item) => item.id !== id))
      if (activeHistoryId === id) {
        setActiveHistoryId(null)
        setCurrentQuestion('')
        setCurrentAnswer('')
        setCurrentRating(null)
      }
    }
  }

  // 6. 點選開啟新對話
  const handleNewChat = () => {
    setActiveHistoryId(null)
    setCurrentQuestion('')
    setCurrentAnswer('')
    setCurrentRating(null)
    setErrorMessage('')
    setInput('')
  }

  // 7. 編輯歷史紀錄名稱（Rename）
  const handleRenameHistory = async (id: string, newTitle: string) => {
    const { error } = await supabase
      .from('chat_history')
      .update({ question: newTitle })
      .eq('id', id)

    if (error) {
      console.error('更名失敗:', error.message)
      alert('更新名稱失敗，請稍後再試。')
      return
    }

    setHistory((prev) =>
      prev.map((item) => (item.id === id ? { ...item, question: newTitle } : item))
    )

    // 若當前正在檢視該歷史紀錄，同步更新右側主畫面的提問文字
    if (activeHistoryId === id) {
      setCurrentQuestion(newTitle)
    }
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-900">
      {/* 左側邊欄 */}
      <Sidebar
        userEmail={userEmail}
        employeeName={employeeName}
        userRole={userRole}
        department={department}
        isAdmin={isAdmin}
        onSignOut={onSignOut}
        history={history}
        activeHistoryId={activeHistoryId}
        onSelectHistory={handleSelectHistory}
        onDeleteHistory={handleDeleteHistory}
        onRenameHistory={handleRenameHistory}
        onNewChat={handleNewChat}
      />

      {/* 右側主對話區 */}
      <main className="flex-1 flex flex-col bg-slate-50 overflow-hidden">
        {/* 頂部狀態列 */}
        <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>SOP 企業知識庫對話系統</span>
          </div>
          <div className="text-xs text-slate-400">
            <span>模式：提問檢索中</span>
          </div>
        </header>

        {/* 聊天呈現區 */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!currentQuestion ? (
            <div className="max-w-xl mx-auto mt-24 text-center">
              <div className="h-12 w-12 rounded-2xl bg-blue-600 text-white flex items-center justify-center font-bold text-xl mx-auto mb-4 shadow-lg shadow-blue-500/20">
                SOP
              </div>
              <h2 className="text-xl font-bold text-slate-800">歡迎使用 SOP 智能知識庫</h2>
              <p className="mt-2 text-sm text-slate-500">
                請在下方輸入框輸入欲查詢的內部 SOP 或規章問題。
              </p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {/* 使用者提問 */}
              <div className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-tr-none px-4 py-3 text-sm leading-relaxed bg-blue-600 text-white shadow-sm">
                  <p className="whitespace-pre-wrap">{currentQuestion}</p>
                </div>
              </div>

              {/* AI 思考狀態 */}
              {isLoading && (
                <div className="flex gap-3 items-center text-xs text-slate-400">
                  <div className="h-2 w-2 rounded-full bg-blue-600 animate-ping"></div>
                  <span>正在檢索內部規章並思考回答中...</span>
                </div>
              )}

              {/* AI 回答氣泡與 Rating 評分介面 */}
              {!isLoading && currentAnswer && (
                <div className="flex gap-3 justify-start items-start">
                  <div className="h-8 w-8 rounded-lg bg-blue-600 text-white text-xs font-bold flex items-center justify-center shrink-0 mt-1 shadow-sm">
                    SOP
                  </div>
                  <div className="max-w-[85%] space-y-2">
                    <div className="rounded-2xl rounded-tl-none px-5 py-4 text-sm leading-relaxed shadow-sm bg-white text-slate-800 border border-slate-200">
                      <p className="whitespace-pre-wrap">{currentAnswer}</p>
                    </div>

                    {/* Rating 評分按鈕列 */}
                    <div className="flex items-center gap-3 px-1">
                      <span className="text-[11px] text-slate-400">這個回答有幫助嗎？</span>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleRate(1)}
                          disabled={isRatingLoading || !activeHistoryId}
                          title="回答很有幫助"
                          className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition ${
                            currentRating === 1
                              ? 'bg-emerald-50 text-emerald-600 border-emerald-300 shadow-sm'
                              : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-100'
                          }`}
                        >
                          <span>👍</span>
                          <span>滿意</span>
                        </button>

                        <button
                          onClick={() => handleRate(-1)}
                          disabled={isRatingLoading || !activeHistoryId}
                          title="回答不夠精準或需要改進"
                          className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition ${
                            currentRating === -1
                              ? 'bg-rose-50 text-rose-600 border-rose-300 shadow-sm'
                              : 'bg-white text-slate-500 border-slate-200 hover:bg-slate-100'
                          }`}
                        >
                          <span>👎</span>
                          <span>待改進</span>
                        </button>
                      </div>

                      {currentRating !== null && (
                        <span className="text-[11px] text-emerald-600 font-medium">
                          ✓ 已記錄回饋
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 錯誤訊息 */}
              {!isLoading && errorMessage && (
                <div className="flex gap-3 justify-start">
                  <div className="max-w-[80%] rounded-2xl rounded-tl-none px-4 py-3 text-sm leading-relaxed shadow-sm bg-red-50 text-red-600 border border-red-200">
                    <p>{errorMessage}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 底部輸入框 */}
        <div className="p-4 bg-white border-t border-slate-200">
          <div className="max-w-3xl mx-auto">
            <div className="relative flex items-center">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="請輸入您想查詢的內部規章或 SOP 流程..."
                disabled={isLoading}
                className="w-full rounded-2xl border border-slate-300 bg-slate-50 py-3.5 pl-4 pr-24 text-sm text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:opacity-50"
              />
              <button
                onClick={handleSend}
                disabled={isLoading || !input.trim()}
                className="absolute right-2 rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500 disabled:bg-slate-300 transition shadow-sm active:scale-95"
              >
                發送
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}