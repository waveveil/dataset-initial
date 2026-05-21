import { useState } from 'react'

export default function IntegrityCheck() {
  const [imageDir, setImageDir] = useState('')
  const [labelDir, setLabelDir] = useState('')
  const [labelExts, setLabelExts] = useState('txt,xml,json')
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
      formData.append('label_dir', labelDir)
      formData.append('label_extensions', labelExts)

      const res = await fetch('/api/integrity/check', { method: 'POST', body: formData })
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

  const isHealthy = results && results.images_without_labels.length === 0 && results.labels_without_images.length === 0

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      {/* Input Panel */}
      <div>
        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <h2 className="text-base font-semibold text-white">数据集完整性检验</h2>
          <p className="text-sm text-gray-500">
            检查每张图片是否都有对应的同名标注文件，以及是否存在孤立的标注文件。
          </p>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">图片文件夹</label>
            <input
              type="text"
              value={imageDir}
              onChange={(e) => setImageDir(e.target.value)}
              placeholder="如: D:/dataset/images/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">标注文件夹</label>
            <input
              type="text"
              value={labelDir}
              onChange={(e) => setLabelDir(e.target.value)}
              placeholder="如: D:/dataset/labels/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              标注文件扩展名
              <span className="ml-1 text-gray-600">（逗号分隔，默认 txt,xml,json）</span>
            </label>
            <input
              type="text"
              value={labelExts}
              onChange={(e) => setLabelExts(e.target.value)}
              placeholder="txt,xml,json"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {error && <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">{error}</div>}

          <button
            type="submit"
            disabled={loading || !imageDir || !labelDir}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
          >
            {loading ? '检验中...' : '开始检验'}
          </button>
        </form>
      </div>

      {/* Results Panel */}
      <div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 min-h-[400px]">
          <h2 className="text-base font-semibold text-white mb-4">检验结果</h2>
          {loading && (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          )}
          {!results && !loading && (
            <p className="text-gray-600 text-sm">输入图片和标注文件夹路径后，开始检验</p>
          )}

          {results && (
            <>
              {/* Summary badges */}
              <div className="mb-4 grid grid-cols-2 gap-3">
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <span className="text-gray-500 text-xs">图片总数</span>
                  <span className="ml-2 text-white font-medium">{results.total_images}</span>
                </div>
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <span className="text-gray-500 text-xs">标注总数</span>
                  <span className="ml-2 text-white font-medium">{results.total_labels}</span>
                </div>
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <span className="text-gray-500 text-xs">匹配成功</span>
                  <span className="ml-2 text-green-400 font-medium">{results.matched}</span>
                </div>
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <span className="text-gray-500 text-xs">缺失 / 孤立</span>
                  <span className={`ml-2 font-medium ${isHealthy ? 'text-green-400' : 'text-red-400'}`}>
                    {results.images_without_labels.length} / {results.labels_without_images.length}
                  </span>
                </div>
              </div>

              {/* Health banner */}
              {isHealthy && (
                <div className="text-sm text-green-400 bg-green-400/10 border border-green-400/20 rounded-lg px-3 py-2 mb-3">
                  数据集完整，所有图片均有对应标注文件
                </div>
              )}

              {/* Images without labels */}
              {results.images_without_labels.length > 0 && (
                <div className="mb-3">
                  <div className="text-sm text-red-400 mb-2">
                    缺少标注的图片 ({results.images_without_labels.length})
                  </div>
                  <div className="max-h-[150px] overflow-y-auto space-y-1">
                    {results.images_without_labels.map((name, i) => (
                      <div key={i} className="text-xs text-gray-400 bg-red-400/5 border border-red-400/10 rounded px-2 py-1 truncate">
                        {name}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Labels without images */}
              {results.labels_without_images.length > 0 && (
                <div className="mb-3">
                  <div className="text-sm text-yellow-400 mb-2">
                    孤立的标注文件 ({results.labels_without_images.length})
                  </div>
                  <div className="max-h-[150px] overflow-y-auto space-y-1">
                    {results.labels_without_images.map((name, i) => (
                      <div key={i} className="text-xs text-gray-400 bg-yellow-400/5 border border-yellow-400/10 rounded px-2 py-1 truncate">
                        {name}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Matched pairs (scrollable if many) */}
              {results.matched > 0 && (
                <div>
                  <div className="text-sm text-gray-400 mb-2">
                    已匹配 ({results.matched})
                  </div>
                  <div className="max-h-[200px] overflow-y-auto space-y-1">
                    {results.matched_pairs.map((pair, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs text-gray-400 bg-gray-800 rounded px-2 py-1">
                        <span className="text-gray-500 w-6 text-right">{i + 1}</span>
                        <span className="text-gray-300 truncate flex-1">{pair.image}</span>
                        <span className="text-gray-600">↔</span>
                        <span className="text-green-400 truncate flex-1">{pair.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
