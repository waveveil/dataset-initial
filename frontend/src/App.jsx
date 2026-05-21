import { useState } from 'react'
import SceneFilter from './components/SceneFilter'
import DedupSample from './components/DedupSample'
import FileRename from './components/FileRename'
import LabelExtract from './components/LabelExtract'
import IntegrityCheck from './components/IntegrityCheck'

const TABS = [
  { id: 'filter', label: '场景筛选', component: SceneFilter },
  { id: 'dedup', label: '去重采样', component: DedupSample },
  { id: 'labels', label: '标签提取', component: LabelExtract },
  { id: 'integrity', label: '完整性检验', component: IntegrityCheck },
  { id: 'rename', label: '批量重命名', component: FileRename },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('filter')

  const ActiveComponent = TABS.find((t) => t.id === activeTab).component

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 bg-gray-900">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-8">
          <h1 className="text-lg font-semibold text-white">数据集初筛工具</h1>
          <nav className="flex gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 py-8">
        <ActiveComponent />
      </main>
    </div>
  )
}
