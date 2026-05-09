import { useState, useRef } from 'react'

export default function DedupSample() {
  const [imageDir, setImageDir] = useState('')
  const [targetCount, setTargetCount] = useState(50)
  const [phashThreshold, setPhashThreshold] = useState(8)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [exportLoading, setExportLoading] = useState(false)
  const [exportMsg, setExportMsg] = useState('')
  const fileRef = useRef(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResults(null)
    setLoading(true)

    try {
      const formData = new FormData()
      if (file) {
        formData.append('file', file)
      } else if (imageDir) {
        formData.append('image_dir', imageDir)
      } else {
        setError('请指定图片目录或上传 ZIP 文件')
        setLoading(false)
        return
      }
      formData.append('target_count', targetCount)
      formData.append('phash_threshold', phashThreshold)

      const res = await fetch('/api/dedup/sample', { method: 'POST', body: formData })
      const data = await res.json()
      if (data.error) {
        setError(data.error)
      } else {
        setResults(data)
      }
    } catch {
      setError('请求失败，请确认后端服务已启动')
    } finally {
      setLoading(false)
    }
  }

  const summary = results?.results?.[0]
  const reduction = summary
    ? `${summary.total_input} → ${summary.after_dedup} → ${summary.after_sample}`
    : ''

  const handleExport = async () => {
    if (!results?.results?.length) return
    setExportLoading(true)
    setExportMsg('')
    try {
      const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_paths: results.results.map((r) => r.path),
          output_dir: outputDir,
        }),
      })
      const data = await res.json()
      setExportMsg(`已导出 ${data.exported} 个文件至 ${data.output_dir}`)
    } catch {
      setExportMsg('导出失败，请确认后端服务已启动')
    } finally {
      setExportLoading(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* Input Panel */}
      <div>
        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <h2 className="text-base font-semibold text-white">去重采样配置</h2>
          <p className="text-sm text-gray-500">
            适用于从视频中连续抽帧的图片集，通过感知哈希去重 + 特征聚类采样，
            提取出具有代表性的子集用于模型训练。
          </p>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">图片目录路径</label>
            <input
              type="text"
              value={imageDir}
              onChange={(e) => { setImageDir(e.target.value); setFile(null) }}
              placeholder="如: /data/video-frames/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">或</span>
            <label className="flex-1">
              <input
                ref={fileRef}
                type="file"
                accept=".zip"
                onChange={(e) => { setFile(e.target.files[0]); setImageDir('') }}
                className="w-full text-sm text-gray-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:bg-gray-700 file:text-gray-200 hover:file:bg-gray-600"
              />
            </label>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1.5">目标采样数量</label>
              <input
                type="number"
                value={targetCount}
                onChange={(e) => setTargetCount(parseInt(e.target.value) || 50)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                min={1}
                max={50000}
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1.5">
                汉明距离阈值
                <span className="text-gray-600 ml-1">(越小越相似)</span>
              </label>
              <input
                type="number"
                value={phashThreshold}
                onChange={(e) => setPhashThreshold(parseInt(e.target.value) || 8)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
                min={1}
                max={64}
              />
            </div>
          </div>

          {error && <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</div>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
          >
            {loading ? '处理中...' : '开始去重采样'}
          </button>
        </form>
      </div>

      {/* Results Panel */}
      <div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 min-h-[400px]">
          <h2 className="text-base font-semibold text-white mb-4">
            采样结果
            {results && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                共 {results.total} 张
              </span>
            )}
          </h2>
          {loading && (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          )}
          {!results && !loading && (
            <p className="text-gray-600 text-sm">输入配置并开始处理后，结果将在此展示</p>
          )}
          {results && results.results.length === 0 && (
            <p className="text-gray-400 text-sm">未找到可处理的图片</p>
          )}
          {summary && (
            <div className="mb-4 flex items-center gap-3 text-sm">
              <div className="bg-gray-800 rounded-lg px-3 py-2">
                <span className="text-gray-500">原始</span>
                <span className="ml-2 text-white font-medium">{summary.total_input}</span>
              </div>
              <span className="text-gray-600">→</span>
              <div className="bg-gray-800 rounded-lg px-3 py-2">
                <span className="text-gray-500">去重后</span>
                <span className="ml-2 text-white font-medium">{summary.after_dedup}</span>
              </div>
              <span className="text-gray-600">→</span>
              <div className="bg-gray-800 rounded-lg px-3 py-2">
                <span className="text-gray-500">采样后</span>
                <span className="ml-2 text-green-400 font-medium">{summary.after_sample}</span>
              </div>
            </div>
          )}
          {results && results.results.length > 0 && (
            <>
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={outputDir}
                onChange={(e) => setOutputDir(e.target.value)}
                placeholder="导出目录路径，如: D:/sampled/"
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={handleExport}
                disabled={exportLoading || !outputDir}
                className="px-4 py-2 rounded-lg bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors whitespace-nowrap"
              >
                {exportLoading ? '导出中...' : '导出结果'}
              </button>
            </div>
            {exportMsg && (
              <div className="text-sm text-green-400 bg-green-400/10 border border-green-400/20 rounded-lg px-3 py-2 mb-3">{exportMsg}</div>
            )}
            <div className="grid grid-cols-2 gap-2 max-h-[350px] overflow-y-auto">
              {results.results.map((r, i) => (
                <div key={r.path} className="bg-gray-800 rounded-lg overflow-hidden">
                  <img
                    src={`/api/image-file?path=${encodeURIComponent(r.path)}`}
                    alt={`sample-${i}`}
                    className="w-full h-24 object-cover"
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                  <div className="px-2 py-1.5 text-xs text-gray-400 truncate">
                    {r.path.split('/').pop()}
                  </div>
                </div>
              ))}
            </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
