'use client'

import React, { useState } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  source?: string
}

export default function ChatContainer() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userQuery = input
    const userMessage: Message = { role: 'user', content: userQuery }
    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    // TODO: 後續在此串接真實 RAG 檢索 API（fetch('/api/chat')）
    setIsLoading(false)
  }

  return (
    <main className="flex-1 flex flex-col bg-slate-50 overflow-hidden">
      {/* 頂部狀態列 */}
      <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
          <span>兆豐SOP問答系統</span>
        </div>
      </header>

      {/* 聊天對話區 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          /* 純淨歡迎畫面 */
          <div className="max-w-xl mx-auto mt-20 text-center">
            <div className="h-12 w-12 rounded-2xl bg-blue-600 text-white flex items-center justify-center font-bold text-xl mx-auto mb-4 shadow-lg shadow-blue-500/20">
              SOP
            </div>
            <h2 className="text-xl font-bold text-slate-800">歡迎使用企業 SOP 智能知識庫</h2>
            <p className="mt-2 text-sm text-slate-500">
              請在下方輸入框輸入欲查詢的內部 SOP 或規章問題。
            </p>
          </div>
        ) : (
          /* 真實訊息列表 */
          <div className="max-w-3xl mx-auto space-y-4">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="h-8 w-8 rounded-lg bg-blue-600 text-white text-xs font-bold flex items-center justify-center shrink-0">
                    SOP
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-white text-slate-800 border border-slate-200 rounded-tl-none'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  {msg.source && (
                    <div className="mt-3 pt-2 border-t border-slate-100 text-[11px] text-slate-400">
                      <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-mono">
                        {msg.source}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex gap-3 items-center text-xs text-slate-400">
                <div className="h-2 w-2 rounded-full bg-blue-600 animate-ping"></div>
                正在檢索知識庫...
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
              className="w-full rounded-2xl border border-slate-300 bg-slate-50 py-3.5 pl-4 pr-24 text-sm text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
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
  )
}