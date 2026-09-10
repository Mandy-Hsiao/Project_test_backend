import { NextResponse } from 'next/server'

export async function POST(request: Request) {
  try {
    const { question } = await request.json()

    if (!question || typeof question !== 'string') {
      return NextResponse.json({ error: '缺少 question 參數' }, { status: 400 })
    }

    const apiUrl = process.env.CHAT_API_URL

    if (!apiUrl) {
      return NextResponse.json(
        { error: '缺少 CHAT_API_URL 環境變數' },
        { status: 500 }
      )
    }

    // 去除結尾斜線，確保路徑組合正常
    const cleanUrl = apiUrl.replace(/\/$/, '')

    // 轉發給獨立部署的 Python FastAPI（對齊 Swagger 的 /chat）
    const response = await fetch(`${cleanUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })

    if (!response.ok) {
      const text = await response.text()
      console.error('Python API 回應失敗:', response.status, text)
      return NextResponse.json({ error: 'Python API 呼叫失敗' }, { status: 502 })
    }

    const data = await response.json()

    return NextResponse.json({ answer: data.answer })
  } catch (error: any) {
    console.error('Chat API 錯誤:', error)
    return NextResponse.json({ error: error.message || '伺服器錯誤' }, { status: 500 })
  }
}