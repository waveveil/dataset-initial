import { useState } from 'react'

export default function LabelExtract() {
  const [imageDir, setImageDir] = useState('')
  const [labelDirs, setLabelDirs] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResults(null)
    setLoading(true)

    try {
      const formData = new FormData()
      formData.append('image_dir', imageDir)
      formData.append('label_dirs', labelDirs)
      if (outputDir) formData.append('output_dir', outputDir)

      const res = await fetch('/api/labels/extract', { method: 'POST', body: formData })
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* Input Panel */}
      <div>
        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <h2 className="text-base font-semibold text-white">标签提取配置</h2>
          <p className="text-sm text-gray-500">
            根据筛选后的图片，从原始数据集标签文件夹中匹配并提取对应的标签文件。
          </p>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">目标图片文件夹</label>
            <input
              type="text"
              value={imageDir}
              onChange={(e) => setImageDir(e.target.value)}
              placeholder="如: D:/filtered-images/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              源标签文件夹（多个用逗号分隔）
            </label>
            <input
              type="text"
              value={labelDirs}
              onChange={(e) => setLabelDirs(e.target.value)}
              placeholder="如: D:/dataset/labels/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              标签输出目录
              <span className="ml-1 text-gray-600">（默认：目标文件夹同级的 label 目录）</span>
            </label>
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              placeholder="留空则默认为目标图片文件夹同级的 label 目录"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {error && <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</div>}

          <button
            type="submit"
            disabled={loading || !imageDir || !labelDirs}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
          >
            {loading ? '提取中...' : '开始提取标签'}
          </button>
        </form>
      </div>

      {/* Results Panel */}
      <div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 min-h-[400px]">
          <h2 className="text-base font-semibold text-white mb-4">
            提取结果
            {results && (
              <span className="ml-2 text-sm font-normal text-gray-400">
                匹配 {results.matched_images}/{results.total_images} 张图片，共 {results.labels_copied} 个标签
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
          {results && results.labels_copied === 0 && (
            <p className="text-gray-400 text-sm">未找到匹配的标签文件</p>
          )}
          {results && results.labels_copied > 0 && (
            <>
              <div className="mb-4 flex items-center gap-3 text-sm">
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <span className="text-gray-500">图片总数</span>
                  <span className="ml-2 text-white font-medium">{results.total_images}</span>
                </div>
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <span className="text-gray-500">匹配图片</span>
                  <span className="ml-2 text-blue-400 font-medium">{results.matched_images}</span>
                </div>
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <span className="text-gray-500">标签文件</span>
                  <span className="ml-2 text-green-400 font-medium">{results.labels_copied}</span>
                </div>
              </div>
              <div className="text-sm text-green-400 bg-green-400/10 border border-green-400/20 rounded-lg px-3 py-2 mb-3">
                标签已导出至 {results.output_dir}
              </div>
              <div className="max-h-[300px] overflow-y-auto space-y-1">
                {results.details.map((d, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-gray-400 bg-gray-800 rounded px-2 py-1">
                    <span className="text-gray-500 w-6 text-right">{i + 1}</span>
                    <span className="text-gray-300 truncate flex-1">{d.image}</span>
                    <span className="text-gray-600">→</span>
                    <span className="text-green-400 truncate flex-1">{d.label}</span>
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
