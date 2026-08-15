import { useState } from 'react'

const ZFILL_OPTIONS = [
  { value: 0, label: '1, 2, 3...' },
  { value: 2, label: '01, 02, 03...' },
  { value: 3, label: '001, 002, 003...' },
  { value: 4, label: '0001, 0002, 0003...' },
  { value: 5, label: '00001, 00002, 00003...' },
]

export default function FileRename() {
  const [imageDir, setImageDir] = useState('')
  const [prefix, setPrefix] = useState('')
  const [zfill, setZfill] = useState(0)
  const [outputDir, setOutputDir] = useState('')
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const handlePreview = async (e) => {
    e.preventDefault()
    if (!imageDir) { setError('请输入图片目录路径'); return }
    setError('')
    setPreview(null)
    setDone(false)
    setLoading(true)
    try {
      const formData = new FormData()
      formData.append('image_dir', imageDir)
      formData.append('prefix', prefix)
      formData.append('zfill', zfill)
      formData.append('output_dir', outputDir)
      const res = await fetch('/api/rename/preview', { method: 'POST', body: formData })
      const data = await res.json()
      if (data.error) setError(data.error)
      else setPreview(data)
    } catch {
      setError('请求失败，请确认后端服务已启动')
    } finally { setLoading(false) }
  }

  const handleExecute = async () => {
    if (!preview?.results?.length) return
    setExecuting(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('image_dir', imageDir)
      formData.append('prefix', prefix)
      formData.append('zfill', zfill)
      formData.append('output_dir', outputDir)
      const res = await fetch('/api/rename/execute', { method: 'POST', body: formData })
      const data = await res.json()
      if (data.error) setError(data.error)
      else { setDone(true); setPreview(data) }
    } catch {
      setError('重命名失败，请确认后端服务已启动')
    } finally { setExecuting(false) }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* Input Panel */}
      <div>
        <form onSubmit={handlePreview} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <h2 className="text-base font-semibold text-white">批量重命名</h2>
          <p className="text-sm text-gray-500">
            对文件夹内所有文件按文件名排序后，统一重命名为 自定义前缀_序号 格式，不改变扩展名。
          </p>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">图片目录路径</label>
            <input
              type="text"
              value={imageDir}
              onChange={(e) => setImageDir(e.target.value)}
              placeholder="如: D:/fire-images/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1.5">自定义字段（可选）</label>
              <input
                type="text"
                value={prefix}
                onChange={(e) => setPrefix(e.target.value)}
                placeholder="留空则纯数字"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex-1">
              <label className="block text-sm text-gray-400 mb-1.5">数字格式</label>
              <select
                value={zfill}
                onChange={(e) => setZfill(parseInt(e.target.value))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                {ZFILL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              导出目录（可选）
              <span className="text-gray-600 ml-1">留空则在原文件夹重命名</span>
            </label>
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              placeholder="如: D:/renamed/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {error && <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</div>}
          {done && <div className="text-sm text-green-400 bg-green-400/10 border border-green-400/20 rounded-lg px-3 py-2">重命名完成！</div>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
          >
            {loading ? '加载中...' : '预览重命名'}
          </button>
        </form>
      </div>

      {/* Preview / Result Panel */}
      <div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 min-h-[400px]">
          <h2 className="text-base font-semibold text-white mb-4">
            预览结果
            {preview && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                共 {preview.total} 个文件
              </span>
            )}
          </h2>

          {loading && (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          )}

          {!preview && !loading && (
            <p className="text-gray-600 text-sm">输入目录路径后点"预览重命名"查看变更</p>
          )}

          {preview && preview.total === 0 && (
            <p className="text-gray-400 text-sm">目录中没有文件</p>
          )}

          {preview && preview.results?.length > 0 && (
            <>
              <div className="mb-4 p-3 bg-gray-800 rounded-lg">
                <div className="flex items-center gap-4 text-sm">
                  <div className="text-gray-400">
                    命名示例：
                    <span className="text-white ml-1">
                      {prefix ? `${prefix}_${String(1).padStart(zfill || 1, '0')}${preview.results[0]?.old_name?.match(/\.[^.]+$/)?.[0] || ''}` : `${String(1).padStart(zfill || 1, '0')}${preview.results[0]?.old_name?.match(/\.[^.]+$/)?.[0] || ''}`}
                    </span>
                  </div>
                </div>
              </div>

              <div className="max-h-[280px] overflow-y-auto border border-gray-800 rounded-lg">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-800 text-gray-400">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">原文件名</th>
                      <th className="text-center px-2 py-2 font-medium w-8"></th>
                      <th className="text-left px-3 py-2 font-medium">新文件名</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800">
                    {preview.results.map((r) => (
                      <tr key={r.old_path} className="text-gray-300 hover:bg-gray-800/50">
                        <td className="px-3 py-2 truncate max-w-[180px]">{r.old_name}</td>
                        <td className="px-2 py-2 text-center text-gray-600">→</td>
                        <td className="px-3 py-2 text-green-400 truncate max-w-[180px]">{r.new_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <button
                onClick={handleExecute}
                disabled={executing || done}
                className="mt-4 w-full py-2.5 rounded-lg bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
              >
                {executing ? '执行中...' : done ? '已完成' : '确认重命名'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
