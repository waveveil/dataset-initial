# 数据集初筛工具

一个基于 CLIP + ResNet50 的图片数据集筛选 Web 应用，提供**场景语义筛选**、**去重多样性采样**和**批量重命名**三大功能，适用于计算机视觉任务的数据预处理。

## 项目架构

```
initial_datasets/
├── start.bat                   # 一键启动脚本
├── backend/                    # Python 后端 (FastAPI)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py           # 配置：模型名、设备、批大小
│   │   ├── main.py             # API 入口：7 个接口 + CORS + 静态文件
│   │   ├── scene_filter.py     # 场景筛选：CLIP 零样本图文匹配
│   │   ├── dedup.py            # 去重采样：pHash → ResNet50 → MiniBatchKMeans
│   │   └── rename.py           # 批量重命名：预览 → 确认执行
│   ├── requirements.txt
│   ├── uploads/                # ZIP 上传解压目录
│   └── output/                 # memmap 临时文件目录
├── frontend/                   # React 前端 (Vite + Tailwind CSS)
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx             # 三标签页布局
│   │   └── components/
│   │       ├── SceneFilter.jsx  # 场景筛选页
│   │       ├── DedupSample.jsx  # 去重采样页
│   │       └── FileRename.jsx   # 批量重命名页
│   ├── package.json
│   └── vite.config.js          # Vite 配置 + /api 代理
└── README.md
```

---

## 功能一：场景筛选

### 原理

使用 **OpenAI CLIP (ViT-B-32)** 模型的零样本图文匹配能力，无需任何标注即可从大批量图片中筛选出符合场景描述的图片。

```
文本描述 "aerial view of forest fire from drone"
      ↓ tokenize
  文本特征向量 (512维)  ──→  余弦相似度  ←──  图片特征向量 (512维)
                                                ↑
                                          CLIP ViT-B-32
                                                ↑
                                          输入图片集
```

1. **文本编码**：将用户输入的场景描述通过 CLIP text encoder 编码为 512 维特征向量
2. **图片编码**：将每张图片通过 CLIP image encoder (ViT-B-32) 编码为 512 维特征向量
3. **计算相似度**：文本向量与每张图片向量做余弦相似度（归一化后点积），得到 0~1 的匹配分数
4. **排序返回**：按相似度降序排列，返回 Top-K 张图片

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 图片目录路径 | 本地图片文件夹路径 | - |
| 场景描述 | 英文描述效果最好，越具体越准 | - |
| 返回数量 (Top-K) | 返回匹配度最高的前 K 张 | 50 |
| 最低相似度阈值 | 0.0~1.0，低于此分数的丢弃，留空表示不过滤 | 无 |

---

## 功能二：去重采样

### 原理

适用于从视频中连续抽帧的图片集。连续帧之间存在大量像素级重复和语义冗余，直接用于训练会导致模型过拟合。去重采样分两阶段进行：

### 第一阶段：pHash 感知哈希去重

```
原图 → 转灰度 → 缩放到 8×8 → 二值化（大于均值=1） → 64-bit 指纹

图1 hash: 1010111001100101...
图2 hash: 1010111001100001...
                    ↑ 差1bit → 汉明距离=1 → 判定为重复
```

- 计算每张图的 64-bit pHash 指纹
- 按文件名排序后，滑动窗口比较相邻图片的汉明距离
- 距离 < 阈值（默认8）的视为重复帧，丢弃
- **16 线程并行计算**，2 万张图约 15-20 秒

### 第二阶段：ResNet50 特征聚类采样

```
去重后的图片集
      ↓ ResNet50 (fc层替换为Identity, 输出2048维特征)
      ↓ 写入 np.memmap 磁盘文件（不占内存）
      ↓ 按行归一化
      ↓ MiniBatchKMeans 分块读取 → partial_fit 聚类
      ↓ 每个簇选离中心最近的图
最终 N 张语义最多样的代表图
```

- 使用在 ImageNet 上预训练的 ResNet50 提取 2048 维语义特征
- 特征直接写入 `np.memmap` 临时文件，内存恒定 ~10MB
- 使用 `MiniBatchKMeans` 分块训练，每次只加载 2048 行特征
- 将图片聚类为 N 个语义簇，每簇选离簇中心最近的图

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 图片目录路径 | 本地图片文件夹路径 | - |
| 目标采样数量 | 最终保留的图片数（聚类簇数） | 50 |
| 汉明距离阈值 | 越小去重越严格，1~64 | 8 |

### 内存安全

| 去重后图片数 | 内存占用 |
|-------------|---------|
| 5,000 | ~10 MB |
| 50,000 | ~10 MB |
| 200,000 | ~10 MB |

关键设计：
- `np.memmap`：特征向量落盘，不堆积在 RAM
- `MiniBatchKMeans.partial_fit`：分块训练，每次只读 2048 行
- 处理完成后自动删除临时文件

---

## 功能三：批量重命名

### 原理

对文件夹内所有文件按文件名（不区分大小写）字母序排列后，统一重命名为 `自定义字段_序号.扩展名` 格式，**不改变任何文件的扩展名**。

```
原文件                          新文件
D:/images/IMG_8765.jpg   →    fire_01.jpg
D:/images/IMG_8766.jpg   →    fire_02.jpg
D:/images/IMG_8767.png   →    fire_03.png
```

### 工作流程

1. **预览重命名**：输入目录和参数后点预览，展示 原文件名 → 新文件名 映射表
2. **确认重命名**：检查预览无误后点确认，执行重命名

### 原位重命名保护机制

如果不指定导出目录（在原文件夹重命名），采用**两步重命名法**避免新旧文件名冲突：

```
原始名 → 临时名(.rn_tmp_*) → 最终名
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| 图片目录路径 | 需要批量重命名的文件夹路径 | - |
| 自定义字段 | 文件名前缀，留空则纯数字命名 | 无 |
| 数字格式 | `1` / `01` / `001` / `0001` / `00001` | `1, 2, 3...` |
| 导出目录 | 留空=原地重命名；填写=复制到新目录并重命名 | 无 |

---

## 运行方式

### 环境要求

- Python 3.10+（建议使用 conda 虚拟环境）
- Node.js 18+
- （可选）NVIDIA GPU + CUDA，用于 CLIP 和 ResNet 推理加速

### 1. 安装依赖

```bash
# 后端 (使用 conda 环境)
conda activate data
cd backend
pip install -r requirements.txt

# 前端
cd frontend
npm install
```

### 2. 设置 HuggingFace 镜像（国内用户）

```bash
# Windows CMD / PowerShell（永久生效可在系统环境变量中添加）
set HF_ENDPOINT=https://hf-mirror.com

# Git Bash / Linux
export HF_ENDPOINT=https://hf-mirror.com
```

首次启动时会从 HuggingFace 下载 CLIP 模型（~400MB）和 ResNet50 权重（~100MB），设置镜像可大幅提速。

### 3. 启动服务

#### 方式 A：一键启动（推荐）

双击项目根目录下的 `start.bat`，自动打开两个窗口分别运行前后端。

脚本默认使用 conda 环境 `data`，如果环境名不同，编辑 `start.bat` 顶部的 `CONDA_ENV` 变量。

#### 方式 B：手动启动（两个终端）

```bash
# 终端1：启动后端 (端口 8000)
conda activate data
cd backend
set HF_ENDPOINT=https://hf-mirror.com
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终端2：启动前端 (端口 5173)
cd frontend
npx vite --host
```

### 4. 访问

- 前端界面：http://localhost:5173
- 后端 API 文档 (Swagger)：http://localhost:8000/docs

### 5. 使用流程

- **场景筛选**：填写图片目录路径 → 输入场景描述（英文） → 设置返回数量 → 开始筛选 → 预览结果 → 导出
- **去重采样**：填写图片目录路径 → 设置目标采样数量 → 设置汉明距离阈值 → 开始去重采样 → 查看流水线统计 → 导出结果
- **批量重命名**：填写目录路径 → 设置前缀和数字格式 → 预览重命名 → 确认执行

### 6. 前端构建部署

```bash
cd frontend
npx vite build
# 产物在 frontend/dist/，可用 nginx 等直接托管
```

---

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/filter/scene` | 场景筛选（支持 `image_dir` 或 ZIP `file`） |
| POST | `/api/dedup/sample` | 去重采样（支持 `image_dir` 或 ZIP `file`） |
| POST | `/api/rename/preview` | 重命名预览（返回改名映射表） |
| POST | `/api/rename/execute` | 确认执行重命名 |
| POST | `/api/export` | 导出结果文件（JSON body: `file_paths` + `output_dir`） |
| GET  | `/api/image-file?path=` | 通过绝对路径读取图片文件 |

---

## 依赖项

### 后端 (Python)

| 包 | 用途 |
|----|------|
| fastapi | Web 框架 |
| uvicorn | ASGI 服务器 |
| open-clip-torch | CLIP 模型加载与推理 |
| torch / torchvision | GPU 推理 + ResNet50 特征提取 |
| imagehash | pHash 感知哈希计算 |
| scikit-learn | MiniBatchKMeans 聚类采样 |
| Pillow | 图片加载与预处理 |
| numpy | 数值计算 + memmap |

### 前端 (Node.js)

| 包 | 用途 |
|----|------|
| react / react-dom | UI 框架 |
| tailwindcss | CSS 样式 |
| vite | 构建工具 |
