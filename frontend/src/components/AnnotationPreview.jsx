import { useEffect, useRef, useState } from 'react'

function getErrorMessage(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail
  if (typeof payload?.error === 'string') return payload.error
  return fallback
}

export default function AnnotationPreview() {
  const [imageDir, setImageDir] = useState('')
  const [labelDir, setLabelDir] = useState('')
  const [classMapping, setClassMapping] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [images, setImages] = useState([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [missingLabels, setMissingLabels] = useState(0)
  const [loadingList, setLoadingList] = useState(false)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [previewError, setPreviewError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [previewMeta, setPreviewMeta] = useState(null)
  const previewUrlRef = useRef('')
  const loadControllerRef = useRef(null)

  const selectedImage = images[selectedIndex] || null

  const replacePreviewUrl = (nextUrl = '') => {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    previewUrlRef.current = nextUrl
    setPreviewUrl(nextUrl)
  }

  const resetPreview = () => {
    replacePreviewUrl('')
    setPreviewMeta(null)
    setPreviewError('')
    setLoadingPreview(false)
  }

  useEffect(() => () => {
    loadControllerRef.current?.abort()
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
  }, [])

  useEffect(() => {
    if (!sessionId || !selectedImage) return undefined

    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      setLoadingPreview(true)
      setPreviewError('')

      try {
        const response = await fetch('/api/annotations/preview/render', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            image_id: selectedImage.id,
            class_mapping: classMapping,
          }),
          signal: controller.signal,
        })

        if (!response.ok) {
          let payload = null
          try {
            payload = await response.json()
          } catch {
            // The backend normally returns JSON errors; fall back below if it does not.
          }
          throw new Error(getErrorMessage(payload, '标注图片生成失败'))
        }

        const blob = await response.blob()
        if (controller.signal.aborted) return

        replacePreviewUrl(URL.createObjectURL(blob))
        setPreviewMeta({
          labelFound: response.headers.get('X-Label-Found') === 'true',
          boxCount: Number(response.headers.get('X-Box-Count') || 0),
          skippedCount: Number(response.headers.get('X-Skipped-Box-Count') || 0),
        })
      } catch (error) {
        if (error.name === 'AbortError') return
        replacePreviewUrl('')
        setPreviewMeta(null)
        setPreviewError(error.message || '标注图片生成失败')
      } finally {
        if (!controller.signal.aborted) setLoadingPreview(false)
      }
    }, classMapping ? 300 : 0)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [sessionId, selectedImage, classMapping])

  const handleLoad = async (event) => {
    event.preventDefault()
    loadControllerRef.current?.abort()
    const controller = new AbortController()
    loadControllerRef.current = controller
    setLoadingList(true)
    setLoadError('')
    setSessionId('')
    setImages([])
    setMissingLabels(0)
    setSelectedIndex(0)
    resetPreview()

    try {
      const response = await fetch('/api/annotations/preview/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_dir: imageDir, label_dir: labelDir }),
        signal: controller.signal,
      })
      const payload = await response.json()
      if (!response.ok) {
        throw new Error(getErrorMessage(payload, '图片目录加载失败'))
      }

      setSessionId(payload.session_id)
      setImages(payload.images || [])
      setMissingLabels(payload.missing_labels || 0)
      setSelectedIndex(0)
    } catch (error) {
      if (error.name !== 'AbortError') {
        setLoadError(error.message || '请求失败，请确认后端服务已启动')
      }
    } finally {
      if (loadControllerRef.current === controller) {
        loadControllerRef.current = null
        setLoadingList(false)
      }
    }
  }

  const selectPrevious = () => setSelectedIndex((index) => Math.max(0, index - 1))
  const selectNext = () => setSelectedIndex((index) => Math.min(images.length - 1, index + 1))

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[340px_minmax(0,1fr)] gap-6">
      <div className="space-y-4">
        <form onSubmit={handleLoad} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-5">
          <div>
            <h2 className="text-base font-semibold text-white">标注预览配置</h2>
            <p className="text-sm text-gray-500 mt-2">
              读取当前目录中的图片及同名 YOLO TXT，由后台绘制标注框。
            </p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">图片文件夹</label>
            <input
              type="text"
              value={imageDir}
              onChange={(event) => setImageDir(event.target.value)}
              placeholder="如: D:/dataset/images/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">YOLO 标签文件夹</label>
            <input
              type="text"
              value={labelDir}
              onChange={(event) => setLabelDir(event.target.value)}
              placeholder="如: D:/dataset/labels/"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              类别名称映射
              <span className="ml-1 text-gray-600">（可选）</span>
            </label>
            <textarea
              value={classMapping}
              onChange={(event) => setClassMapping(event.target.value)}
              rows={5}
              placeholder={'0:火焰\n1:烟雾\n2:灭火器'}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-y font-mono"
            />
            <p className="text-xs text-gray-600 mt-1.5">
              每行填写 ID:名称；未填写或未映射的类别显示数字 ID。
            </p>
          </div>

          {loadError && (
            <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
              {loadError}
            </div>
          )}

          <button
            type="submit"
            disabled={loadingList || !imageDir || !labelDir}
            className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium transition-colors"
          >
            {loadingList ? '加载中...' : '加载图片'}
          </button>
        </form>

        {images.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between text-xs mb-3">
              <span className="text-gray-400">图片列表</span>
              <span className="text-gray-500">
                {images.length} 张 · {missingLabels} 张缺少标签
              </span>
            </div>
            <div className="max-h-[320px] overflow-y-auto space-y-1 pr-1">
              {images.map((image, index) => (
                <button
                  type="button"
                  key={image.id}
                  onClick={() => setSelectedIndex(index)}
                  className={`w-full flex items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                    index === selectedIndex
                      ? 'bg-blue-600/20 border border-blue-500/40 text-white'
                      : 'border border-transparent text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                  }`}
                >
                  <span className="w-7 text-right text-gray-600">{index + 1}</span>
                  <span className="truncate flex-1">{image.name}</span>
                  <span className={image.has_label ? 'text-green-400' : 'text-yellow-400'}>
                    {image.has_label ? '有标签' : '缺标签'}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl min-h-[620px] overflow-hidden flex flex-col">
        <div className="border-b border-gray-800 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-semibold text-white">标注结果</h2>
              {selectedImage && (
                <p className="text-xs text-gray-500 mt-1 truncate" title={selectedImage.name}>
                  {selectedIndex + 1} / {images.length} · {selectedImage.name}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={selectPrevious}
              disabled={!selectedImage || selectedIndex === 0 || loadingList}
              className="px-3 py-2 rounded-lg border border-gray-700 text-sm text-gray-300 hover:border-blue-500/60 hover:text-white disabled:text-gray-600 disabled:hover:border-gray-700 transition-colors"
            >
              ← 上一张
            </button>
            <button
              type="button"
              onClick={selectNext}
              disabled={!selectedImage || selectedIndex === images.length - 1 || loadingList}
              className="px-3 py-2 rounded-lg border border-gray-700 text-sm text-gray-300 hover:border-blue-500/60 hover:text-white disabled:text-gray-600 disabled:hover:border-gray-700 transition-colors"
            >
              下一张 →
            </button>
          </div>

          {selectedImage && previewMeta && (
            <div className="flex flex-wrap gap-2 mt-3 text-xs">
              <span className={`rounded-full px-2.5 py-1 ${
                previewMeta.labelFound
                  ? 'bg-green-400/10 text-green-400 border border-green-400/20'
                  : 'bg-yellow-400/10 text-yellow-400 border border-yellow-400/20'
              }`}>
                {previewMeta.labelFound ? '已读取同名标签' : '未找到同名标签'}
              </span>
              <span className="rounded-full px-2.5 py-1 bg-blue-400/10 text-blue-400 border border-blue-400/20">
                已绘制 {previewMeta.boxCount} 个框
              </span>
              {previewMeta.skippedCount > 0 && (
                <span className="rounded-full px-2.5 py-1 bg-red-400/10 text-red-400 border border-red-400/20">
                  已跳过 {previewMeta.skippedCount} 条无效标注
                </span>
              )}
            </div>
          )}
        </div>

        <div className="flex-1 min-h-0 p-4 flex items-center justify-center bg-gray-950/50">
          {!selectedImage && !loadingList && (
            <div className="text-center text-sm text-gray-600 max-w-sm">
              输入图片和标签文件夹路径，加载后即可选择图片查看标注框。
            </div>
          )}

          {(loadingList || loadingPreview) && (
            <div className="flex items-center text-sm text-gray-500">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
              <span className="ml-3">{loadingList ? '正在读取图片目录...' : '正在绘制标注框...'}</span>
            </div>
          )}

          {previewError && !loadingPreview && (
            <div className="text-sm text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-3 max-w-lg">
              {previewError}
            </div>
          )}

          {previewUrl && !loadingPreview && !previewError && (
            <img
              src={previewUrl}
              alt={selectedImage?.name || '标注预览'}
              className="block max-w-full max-h-[72vh] object-contain rounded-lg shadow-2xl"
            />
          )}
        </div>
      </div>
    </div>
  )
}
