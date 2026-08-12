import { useState } from 'react'

const SIZE_COLORS = {
  small: { bg: 'bg-cyan-500/20', bar: 'bg-cyan-500', text: 'text-cyan-400' },
  medium: { bg: 'bg-amber-500/20', bar: 'bg-amber-500', text: 'text-amber-400' },
  large: { bg: 'bg-rose-500/20', bar: 'bg-rose-500', text: 'text-rose-400' },
}

const SIZE_LABELS = { small: 'Small', medium: 'Medium', large: 'Large' }

export default function DatasetStats() {
  const [imageDir, setImageDir] = useState('')
  const [labelDir, setLabelDir] = useState('')
  const [labelFormat, setLabelFormat] = useState('txt')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const [expandedChart, setExpandedChart] = useState(null)
  const [formOpen, setFormOpen] = useState(true)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResults(null)
    setLoading(true)

    try {
      const formData = new FormData()
      if (imageDir) formData.append('image_dir', imageDir)
      formData.append('label_dir', labelDir)
      formData.append('label_format', labelFormat)

      const res = await fetch('/api/stats', { method: 'POST', body: formData })
      const data = await res.json()
      if (data.error) {
        setError(data.error)
      } else {
        setResults(data)
        setFormOpen(false)
      }
    } catch {
      setError('请求失败，请确认后端服务已启动')
    } finally {
      setLoading(false)
    }
  }

  const sizePercentages = results?.size_percentages || {}
  const maxSizePct = Math.max(...Object.values(sizePercentages), 1)

  return (
    <div className="space-y-6">
      {/* ── Input bar ── */}
      {(!results || formOpen) && (
        <form onSubmit={handleSubmit} className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[180px]">
              <label className="block text-xs text-gray-500 mb-1">
                标签文件夹 <span className="text-red-400">*</span>
              </label>
              <input
                type="text" value={labelDir}
                onChange={(e) => setLabelDir(e.target.value)}
                placeholder="D:/dataset/labels/"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex-1 min-w-[180px]">
              <label className="block text-xs text-gray-500 mb-1">
                图片文件夹 <span className="text-gray-600">（可选，仅用于交叉比对）</span>
              </label>
              <input
                type="text" value={imageDir}
                onChange={(e) => setImageDir(e.target.value)}
                placeholder="填了也不影响统计结果，仅额外显示比对信息"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="w-[140px]">
              <label className="block text-xs text-gray-500 mb-1">标签格式</label>
              <select
                value={labelFormat}
                onChange={(e) => setLabelFormat(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
              >
                <option value="txt">YOLO (.txt)</option>
                <option value="xml">Pascal VOC (.xml)</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={loading || !labelDir}
              className="h-[38px] px-6 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors whitespace-nowrap"
            >
              {loading ? '统计中...' : '开始统计'}
            </button>
          </div>
          {error && (
            <div className="mt-3 text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
        </form>
      )}

      {/* ── Collapsed form bar (after results loaded) ── */}
      {results && !formOpen && (
        <div className="flex items-center gap-3 bg-gray-900 border border-gray-800 rounded-xl px-5 py-3">
          <span className="text-sm text-gray-400">
            标签文件夹：<span className="text-white font-medium">{labelDir}</span>
            {imageDir && <><span className="mx-2 text-gray-600">|</span>图片：<span className="text-white font-medium">{imageDir}</span></>}
            <span className="mx-2 text-gray-600">|</span>格式：<span className="text-white font-medium">{labelFormat === 'txt' ? 'YOLO' : 'VOC'}</span>
          </span>
          <button
            onClick={() => setFormOpen(true)}
            className="ml-auto text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 rounded-lg border border-gray-700 hover:border-blue-500/50 transition-colors"
          >
            修改参数
          </button>
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
          <span className="ml-3 text-sm text-gray-500">正在解析标签文件...</span>
        </div>
      )}

      {/* ── Results ── */}
      {results && !loading && (
        <div className="space-y-6">
          {/* ── cross check info (only when image_dir provided) ── */}
          {results.cross_check && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-3">
                <div className="text-xs text-gray-500">图片文件夹图片数</div>
                <div className="text-lg font-semibold text-white mt-0.5">{results.cross_check.total_images_in_dir}</div>
              </div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-3">
                <div className="text-xs text-gray-500">有对应标签</div>
                <div className="text-lg font-semibold text-green-400 mt-0.5">{results.cross_check.images_with_labels}</div>
              </div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-3">
                <div className="text-xs text-gray-500">缺少标签的图片</div>
                <div className={`text-lg font-semibold mt-0.5 ${results.cross_check.images_without_labels > 0 ? 'text-red-400' : 'text-gray-400'}`}>
                  {results.cross_check.images_without_labels}
                </div>
              </div>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-3">
                <div className="text-xs text-gray-500">无对应图片的标签</div>
                <div className={`text-lg font-semibold mt-0.5 ${results.cross_check.labels_without_images > 0 ? 'text-yellow-400' : 'text-gray-400'}`}>
                  {results.cross_check.labels_without_images}
                </div>
              </div>
            </div>
          )}

          {/* Summary cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-xs text-gray-500">标签文件数</div>
              <div className="text-2xl font-semibold text-white mt-0.5">{results.total_labels}</div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-xs text-gray-500">目标总数</div>
              <div className="text-2xl font-semibold text-white mt-0.5">{results.total_targets}</div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-xs text-gray-500">类别数</div>
              <div className="text-2xl font-semibold text-white mt-0.5">{results.num_classes || 0}</div>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
              <div className="text-xs text-gray-500">标签平均目标数</div>
              <div className="text-2xl font-semibold text-white mt-0.5">{results.targets_per_label_avg}</div>
            </div>
          </div>

          {/* Per-label stats + size distribution side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Per-label distribution */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="text-sm font-semibold text-white mb-4">每标签文件目标数分布</div>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: '最小', value: results.targets_per_label_min },
                  { label: '中位数', value: results.targets_per_label_median },
                  { label: '平均', value: results.targets_per_label_avg },
                  { label: '最大', value: results.targets_per_label_max },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-800 rounded-lg p-3 text-center">
                    <div className="text-xs text-gray-500">{label}</div>
                    <div className="text-lg font-semibold text-white mt-0.5">{value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Size distribution */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="text-sm font-semibold text-white mb-4">目标尺寸分布</div>
              {results.total_targets > 0 ? (
                <div className="space-y-3">
                  {['small', 'medium', 'large'].map((size) => {
                    const pct = sizePercentages[size] || 0
                    const count = results.size_distribution?.[size] || 0
                    const c = SIZE_COLORS[size]
                    return (
                      <div key={size} className="flex items-center gap-3">
                        <span className={`text-xs font-medium w-14 ${c.text}`}>{SIZE_LABELS[size]}</span>
                        <div className="flex-1 h-5 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${c.bar} rounded-full transition-all duration-700`}
                            style={{ width: `${Math.max((pct / maxSizePct) * 100, 3)}%` }}
                          />
                        </div>
                        <span className="text-sm text-white font-medium w-12 text-right">{count}</span>
                        <span className="text-xs text-gray-500 w-12 text-right">{pct}%</span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-sm text-gray-600">无目标数据</div>
              )}
            </div>
          </div>

          {/* Class Distribution - full width */}
          {results.class_counts && Object.keys(results.class_counts).length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <div className="text-sm font-semibold text-white mb-3">
                类别分布
                <span className="ml-2 text-xs text-gray-500 font-normal">
                  ({Object.keys(results.class_counts).length} 类)
                </span>
              </div>
              <div className="max-h-[300px] overflow-y-auto space-y-2">
                {Object.entries(results.class_counts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([cls, count]) => {
                    const pct = results.total_targets > 0
                      ? (count / results.total_targets * 100).toFixed(1)
                      : 0
                    return (
                      <div key={cls} className="flex items-center gap-2">
                        <span className="text-xs text-white font-mono w-10">{cls}</span>
                        <div className="flex-1 h-4 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all duration-700"
                            style={{ width: `${Math.max(pct, 0.5)}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-400 w-12 text-right">{count}</span>
                        <span className="text-xs text-gray-500 w-14 text-right">{pct}%</span>
                      </div>
                    )
                  })}
              </div>
            </div>
          )}

          {/* Charts - full width, stacked */}
          {results.charts && Object.keys(results.charts).length > 0 && (
            <>
              {results.charts.labels && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                  <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
                    <span className="text-sm font-semibold text-white">标签分布</span>
                    <button
                      onClick={() => setExpandedChart('labels')}
                      className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      点击放大
                    </button>
                  </div>
                  <div className="p-2">
                    <img
                      src={`data:image/png;base64,${results.charts.labels}`}
                      alt="标签分布图"
                      className="w-full cursor-pointer"
                      onClick={() => setExpandedChart('labels')}
                    />
                  </div>
                </div>
              )}
              {results.charts.correlogram && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                  <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
                    <span className="text-sm font-semibold text-white">相关性矩阵</span>
                    <button
                      onClick={() => setExpandedChart('correlogram')}
                      className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      点击放大
                    </button>
                  </div>
                  <div className="p-2">
                    <img
                      src={`data:image/png;base64,${results.charts.correlogram}`}
                      alt="相关性矩阵"
                      className="w-full cursor-pointer"
                      onClick={() => setExpandedChart('correlogram')}
                    />
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Empty state ── */}
      {!results && !loading && (
        <div className="text-center py-20 text-gray-600 text-sm">
          输入标签文件夹路径后，点击「开始统计」
        </div>
      )}

      {/* ── Expanded Chart Modal ── */}
      {expandedChart && results?.charts?.[expandedChart] && (
        <div
          className="fixed inset-0 bg-black/85 z-50 flex items-center justify-center p-8 cursor-pointer"
          onClick={() => setExpandedChart(null)}
        >
          <div
            className="max-w-[92vw] max-h-[92vh] overflow-auto bg-gray-900 rounded-xl border border-gray-700 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 sticky top-0 bg-gray-900 z-10">
              <span className="text-sm text-gray-300">
                {expandedChart === 'labels' ? '标签分布 (labels.jpg)' : '相关性矩阵 (correlogram.jpg)'}
              </span>
              <button
                onClick={() => setExpandedChart(null)}
                className="text-gray-500 hover:text-white text-xl leading-none px-2"
              >
                ×
              </button>
            </div>
            <img
              src={`data:image/png;base64,${results.charts[expandedChart]}`}
              alt="放大图表"
              className="max-w-full"
            />
          </div>
        </div>
      )}
    </div>
  )
}
