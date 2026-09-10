import { NextResponse } from 'next/server'
import { Pinecone } from '@pinecone-database/pinecone'

export async function GET() {
  try {
    const apiKey = process.env.PINECONE_API_KEY
    const indexName = process.env.PINECONE_INDEX

    if (!apiKey || !indexName) {
      return NextResponse.json(
        { connected: false, error: '缺少 PINECONE_API_KEY 或 PINECONE_INDEX 環境變數' },
        { status: 500 }
      )
    }

    // 1. 初始化 Pinecone 客戶端
    const pc = new Pinecone({ apiKey })

    // 2. 指定 Index
    const index = pc.index(indexName)

    // 3. 向 Pinecone 索取 Index 狀態與資料統計（不需消耗 OpenAI）
    const stats = await index.describeIndexStats()

    return NextResponse.json({
      connected: true,
      indexName,
      totalRecordCount: stats.totalRecordCount || 0,
      dimension: stats.dimension,
      namespaces: stats.namespaces || {},
    })
  } catch (error: any) {
    console.error('Pinecone 連線失敗:', error)
    return NextResponse.json(
      { connected: false, error: error.message || '無法連線至 Pinecone' },
      { status: 500 }
    )
  }
}