# 网易云音乐云盘复制工具

将一个网易云音乐账号的云盘歌曲快速复制到另一个账号。

## 功能特性

✅ **智能复制** - 仅复制网易云服务器上已有的文件（通过 MD5 匹配），无需下载上传
✅ **自动去重** - 自动跳过目标账号已有的歌曲
✅ **断点续传** - 支持中断后继续，不会重复处理
✅ **进度跟踪** - 实时保存进度，随时查看统计信息
✅ **错误处理** - 网络错误自动重试，永久错误跳过并记录
✅ **美观界面** - Rich 终端界面，进度一目了然

## 工作原理

当歌曲文件已存在于网易云服务器时（`needUpload=false`），本工具通过以下 API 流程将歌曲关联到目标账号：

1. **获取云盘列表** - 从源账号和目标账号获取歌曲列表
2. **检查上传状态** - 验证文件是否已在服务器上
3. **分配 Token** - 获取资源 ID（不实际上传文件）
4. **上传元数据** - 关联歌曲信息到目标账号
5. **发布到云盘** - 完成复制

## 限制说明

⚠️ **重要**：本工具仅处理网易云服务器上已有的文件。如果某首歌曲是你独有的（服务器上不存在），将会被跳过。这意味着：

- ✅ 可以复制：网易云曲库中的歌曲
- ❌ 无法复制：你自己上传的独有音频文件

## 安装

### 前置要求

- Python 3.10 或更高版本
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

### 使用 uv 安装（推荐）

```bash
# 克隆仓库
cd netease-cloud-copy

# 安装 uv（如果还没安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv sync
```

### 使用 pip 安装

```bash
cd netease-cloud-copy

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -e .
```

## 配置

### 1. 获取 Cookie

打开浏览器，登录网易云音乐网页版：

1. 按 `F12` 打开开发者工具
2. 切换到 **Network**（网络）选项卡
3. 刷新页面或执行任意操作
4. 找到任意请求，查看 **Request Headers**
5. 复制完整的 `Cookie` 值

**Cookie 示例：**
```
MUSIC_U=007400D1432118DFFB...; __csrf=c93a17930b1c1b5e...; JSESSIONID-WYYY=ej1kJZJc...
```

### 2. 创建配置文件

复制示例配置文件：

```bash
cp config/cookies.json.example config/cookies.json
```

编辑 `config/cookies.json`，填入两个账号的 Cookie：

```json
{
  "source": {
    "cookie": "源账号的完整 Cookie",
    "account_name": "源账号"
  },
  "target": {
    "cookie": "目标账号的完整 Cookie",
    "account_name": "目标账号"
  }
}
```

⚠️ **安全提示**：
- 不要将包含真实 Cookie 的配置文件提交到 Git
- Cookie 具有完整账号权限，请妥善保管
- 定期更换 Cookie（登录状态过期后需重新获取）

## 使用方法

### 基本用法

```bash
# 使用 uv 运行
uv run python main.py copy

# 或激活虚拟环境后运行
source venv/bin/activate
python main.py copy
```

### 命令行选项

```bash
python main.py copy --help

选项:
  -c, --config PATH       Cookie 配置文件路径 [默认: config/cookies.json]
  -p, --progress PATH     进度文件路径 [默认: data/progress.json]
  -b, --batch-size INT    批处理大小（每 N 首歌保存一次进度） [默认: 10]
  -l, --log-level TEXT    日志级别（DEBUG/INFO/WARNING/ERROR） [默认: INFO]
```

### 查看进度

```bash
python main.py status
```

### 自定义配置

```bash
# 使用不同的配置文件
python main.py copy -c my_cookies.json

# 调整批处理大小（每 5 首歌保存一次）
python main.py copy -b 5

# 启用调试日志
python main.py copy -l DEBUG
```

## 工作流程示例

```bash
$ python main.py copy

╭──────────────────────────────────────╮
│ 网易云音乐云盘复制工具                │
│ 将源账号的云盘歌曲复制到目标账号      │
╰──────────────────────────────────────╯

正在验证 Cookie...
✓ Cookie 验证成功

开始复制歌曲...

开始获取源账号歌曲列表...
源账号共有 245 首歌曲
开始获取目标账号歌曲列表...
目标账号共有 98 首歌曲
目标账号已有 98 首歌曲
需要复制 120 首歌曲

[1/120] 处理: 告白气球 - 周杰伦
✓ 复制成功: 告白气球 - 周杰伦

[2/120] 处理: 稻香 - 周杰伦
✓ 复制成功: 稻香 - 周杰伦

...

所有歌曲处理完成！
============================================================
统计摘要
============================================================
源账号总歌曲数: 245
已在目标账号: 98
成功复制: 115
跳过（需上传）: 5
失败: 0
剩余: 0
============================================================
```

## 断点续传

如果复制过程中被中断（`Ctrl+C` 或程序崩溃），进度会自动保存。下次运行时会从中断处继续：

```bash
# 第一次运行（处理了 50 首后中断）
$ python main.py copy
^C
收到中断信号，正在保存进度...
进度已保存

# 第二次运行（自动跳过已处理的 50 首）
$ python main.py copy
需要复制 70 首歌曲  # 自动跳过已处理的
[51/120] 处理: ...
```

## 进度文件

进度保存在 `data/progress.json`，包含：

- 已处理歌曲列表（MD5、状态、时间戳）
- 目标账号已有歌曲 MD5 列表
- 统计信息（成功/失败/跳过数量）

可以随时删除此文件以重新开始。

## 故障排查

### Cookie 无效

```
错误: 源账号 Cookie 无效或已过期
```

**解决方法：** 重新获取 Cookie 并更新配置文件

### 网络错误

```
HTTPError: 连接超时
```

**解决方法：** 程序会自动重试 3 次，如果仍失败请检查网络连接

### 文件需要上传

```
⊘ 跳过（需要上传）: 某歌曲 - 某歌手
```

**说明：** 这首歌曲文件不在网易云服务器上，本工具无法复制。这是正常情况，不是错误。

## 项目结构

```
netease-cloud-copy/
├── api/              # API 客户端
├── models/           # 数据模型
├── services/         # 业务逻辑
├── utils/            # 工具函数
├── config/           # 配置文件（.gitignore）
├── data/             # 进度数据（.gitignore）
├── main.py           # CLI 入口
└── pyproject.toml    # 项目配置
```

## 开发

### 安装开发依赖

```bash
uv sync --all-extras
```

### 代码格式化

```bash
uv run ruff check .
uv run ruff format .
```

## 许可证

MIT License

## 免责声明

本工具仅供学习交流使用，请遵守网易云音乐服务条款。使用本工具产生的任何问题由使用者自行承担。

## 致谢

感谢网易云音乐提供的优质音乐服务。
