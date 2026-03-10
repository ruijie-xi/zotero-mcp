# Zotero MCP 开发指南：从入门到深入

本文档帮助你从零开始理解 Zotero MCP 项目，掌握如何从源码构建、运行，并在此基础上进行二次开发。

---

## 一、MCP 基础概念（入门）

### 1.1 什么是 MCP？

**Model Context Protocol (MCP)** 是一个开放协议，用于标准化 AI 应用如何连接外部系统。可以把它理解为「AI 的 USB-C 接口」——统一、可插拔。

MCP 服务器通过三种能力与 AI 交互：

| 能力 | 说明 | Zotero MCP 是否提供 |
|------|------|---------------------|
| **Tools（工具）** | AI 可主动调用的函数 | ✅ 主要能力 |
| **Resources（资源）** | 只读数据源 | ❌ |
| **Prompts（提示）** | 预定义指令模板 | ❌ |

### 1.2 工作流程简述

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  Cursor /   │         │ zotero-mcp  │         │   Zotero    │
│  Claude 等  │         │  (MCP 服务器) │         │ (本地/Web)  │
└──────┬──────┘         └──────┬──────┘         └──────┬──────┘
       │                       │                       │
       │ 1. 启动 zotero-mcp serve                      │
       │ ─────────────────────>│                      │
       │                       │                       │
       │ 2. tools/list（发现工具）                      │
       │ ─────────────────────>│                      │
       │ <─────────────────────│ 返回工具列表         │
       │                       │                       │
       │ 3. 用户：「搜索机器学习论文」                  │
       │                       │                       │
       │ 4. tools/call(zotero_search_items, {...})     │
       │ ─────────────────────>│ 5. 调用 Zotero API   │
       │                       │ ─────────────────────>│
       │                       │ <─────────────────────│
       │ <─────────────────────│ 6. 返回 Markdown 结果 │
       │                       │                       │
```

### 1.3 环境要求

- **Python** 3.10+
- **Zotero** 7+（本地 API 全文访问）
- 支持 MCP 的客户端：Cursor、Claude Desktop、ChatGPT、Cherry Studio 等

---

## 二、从源码构建并运行（核心）

### 2.1 克隆项目

```bash
git clone https://github.com/54yyyu/zotero-mcp.git
cd zotero-mcp
```

### 2.2 创建虚拟环境（推荐）

使用 **uv**（推荐，速度快）：

```bash
# 安装 uv（如未安装）
# Windows: irm https://astral.sh/uv/install.ps1 | iex
# macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh

uv venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

或使用 **venv**：

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2.3 以可编辑模式安装（开发模式）

**方式 A：使用 pip（推荐用于开发）**

```bash
pip install -e ".[dev]"
```

`-e` 表示可编辑模式（editable），修改源码后无需重新安装即可生效。`.[dev]` 会额外安装 pytest、black、isort 等开发依赖。

**方式 B：使用 uv**

```bash
uv pip install -e ".[dev]"
```

### 2.4 验证安装

```bash
zotero-mcp version
```

应输出类似：`Zotero MCP v1.x.x`。

### 2.5 直接运行（不安装到系统）

若不想安装，可直接用 Python 模块方式运行：

```bash
# 先安装依赖（不含 -e）
pip install .

# 以模块方式启动
python -m zotero_mcp.cli serve
```

或使用 `uv run`（需在项目根目录）：

```bash
uv run zotero-mcp serve
```

### 2.6 配置 Zotero 连接

**本地 Zotero（推荐）**：

1. 在 Zotero 中：编辑 → 首选项 → 高级 → API → 勾选「允许其他应用程序与 Zotero 通信」
2. 运行配置向导：

```bash
zotero-mcp setup
```

或手动设置环境变量：

```powershell
# Windows PowerShell
$env:ZOTERO_LOCAL = "true"
```

```bash
# macOS/Linux
export ZOTERO_LOCAL=true
```

**Web API**（远程库）：

```bash
zotero-mcp setup --no-local --api-key YOUR_API_KEY --library-id YOUR_LIBRARY_ID
```

### 2.7 在 Cursor 中配置 MCP

#### 如何打开 Cursor 的 MCP 设置

1. **打开设置**：按 `Ctrl + Shift + J`（Windows/Linux）或 `Cmd + Shift + J`（Mac）
2. 在左侧边栏点击 **Tools & MCP**
3. 在此处可添加、启用/禁用 MCP 服务器，或查看已安装的服务器

#### 配置方式

**方式 A：通过 UI 添加**

在 Tools & MCP 页面点击「Add new MCP server」，按提示填写：

- **Name**：`zotero`（或任意名称）
- **Type**：`command`（本地命令）
- **Command**：`zotero-mcp` 的完整路径（见下方）
- **Arguments**：留空，或填 `["serve"]`
- **Environment**：添加 `ZOTERO_LOCAL: true`（本地模式）

**方式 B：通过配置文件**

创建或编辑 `mcp.json`，位置二选一：

| 作用域 | 路径 |
|--------|------|
| 全局（所有项目） | `~/.cursor/mcp.json`（如 `C:\Users\你的用户名\.cursor\mcp.json`） |
| 仅当前项目 | `.cursor/mcp.json`（项目根目录，可提交到 git 与团队共享） |

两种文件会合并；若同名服务器同时存在，项目级配置优先。

**zotero-mcp 配置示例**（pip/uv 安装后，使用系统 `zotero-mcp` 命令）：

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "args": [],
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

保存后**重启 Cursor** 使配置生效。

#### 验证与排错

- **查看 MCP 日志**：`Ctrl + Shift + U`（Windows/Linux）或 `Cmd + Shift + U`（Mac）打开 Output 面板，选择「MCP Logs」
- **启用/禁用服务器**：在 Tools & MCP 中点击服务器旁的开关
- **环境变量**：若依赖 shell 中的环境变量，需在修改后重启 Cursor

### 2.8 在 Cursor 中使用开发版（源码）

1. 获取 `zotero-mcp` 可执行文件路径：

```bash
zotero-mcp setup-info
```

2. 在 Cursor 的 MCP 配置中，将 `command` 指向开发环境的路径，例如：

```json
{
  "mcpServers": {
    "zotero": {
      "command": "D:\\Myfiles\\Codes\\cursor-projects\\zotero-mcp\\.venv\\Scripts\\zotero-mcp.exe",
      "args": [],
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

或使用 `python -m` 方式（需确保 Cursor 能找到正确的 Python）：

```json
{
  "mcpServers": {
    "zotero": {
      "command": "D:\\Myfiles\\Codes\\cursor-projects\\zotero-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "zotero_mcp.cli", "serve"],
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

3. 重启 Cursor 或重新加载 MCP 连接。

### 2.9 快速测试：手动启动服务器

```bash
# 默认 stdio 传输（供 MCP 客户端子进程调用）
zotero-mcp serve

# HTTP 传输（可用于调试、ChatGPT 隧道等）
zotero-mcp serve --transport streamable-http --host 0.0.0.0 --port 8000
```

---

## 三、项目结构概览（进阶）

### 3.1 目录结构

```
zotero-mcp/
├── src/zotero_mcp/
│   ├── __init__.py          # 包入口，导出 mcp 和 __version__
│   ├── _version.py          # 版本号（由 Hatch 管理）
│   ├── server.py            # MCP 服务器与所有工具定义（核心）
│   ├── cli.py               # 命令行入口（serve、setup、update-db 等）
│   ├── client.py            # Zotero 客户端封装（pyzotero / 本地 API）
│   ├── semantic_search.py   # 语义搜索（ChromaDB + 嵌入）
│   ├── chroma_client.py     # ChromaDB 客户端
│   ├── local_db.py          # 本地 zotero.sqlite 访问
│   ├── pdf_utils.py         # PDF 处理（PyMuPDF）
│   ├── pdfannots_downloader.py  # PDF 批注下载
│   ├── pdfannots_helper.py  # PDF 批注辅助
│   ├── epub_utils.py        # EPUB 处理
│   ├── better_bibtex_client.py  # Better BibTeX 集成
│   ├── setup_helper.py      # 配置向导
│   ├── updater.py           # 更新逻辑
│   └── utils.py             # 通用工具
├── tests/                   # 测试
├── docs/                    # 文档
├── pyproject.toml           # 项目配置与依赖
├── smithery.yaml            # Smithery 托管配置
├── Dockerfile               # 容器镜像
└── MANIFEST.in              # 打包清单
```

### 3.2 构建与打包

项目使用 **Hatchling** 作为构建后端（见 `pyproject.toml`）：

```bash
# 安装构建工具
pip install build

# 构建 wheel 和 sdist
python -m build
```

产物在 `dist/` 目录：`zotero_mcp_server-*.whl` 和 `*.tar.gz`。

### 3.3 入口点

`pyproject.toml` 中定义：

```toml
[project.scripts]
zotero-mcp = "zotero_mcp.cli:main"
```

即 `zotero-mcp` 命令会调用 `zotero_mcp.cli.main()`。

---

## 四、核心模块与开发模式（深入）

### 4.1 技术栈

| 组件 | 技术 |
|------|------|
| MCP 框架 | **FastMCP** |
| MCP SDK | `mcp>=1.2.0` |
| Zotero 客户端 | `pyzotero>=1.5.0` |
| 向量数据库 | `chromadb>=0.4.0` |
| 嵌入模型 | sentence-transformers / OpenAI / Gemini |
| PDF 处理 | `pymupdf`、`markitdown[pdf]` |
| 构建系统 | Hatchling |

### 4.2 服务器创建流程（server.py）

```python
from fastmcp import Context, FastMCP

# 1. 创建 FastMCP 实例
mcp = FastMCP("Zotero", lifespan=server_lifespan)

# 2. 用装饰器注册工具
@mcp.tool(
    name="zotero_search_items",
    description="Search for items in your Zotero library, given a query string."
)
def search_items(query: str, qmode: str = "titleCreatorYear", ..., *, ctx: Context) -> str:
    zot = get_zotero_client()
    results = zot.items(...)
    return format_as_markdown(results)
```

### 4.3 添加新工具的步骤

1. 在 `server.py` 中定义函数，并用 `@mcp.tool()` 装饰：

```python
@mcp.tool(
    name="zotero_my_new_tool",
    description="清晰描述工具功能，AI 会据此选择是否调用"
)
def my_new_tool(param1: str, limit: int = 10, *, ctx: Context) -> str:
    try:
        ctx.info("执行操作...")
        zot = get_zotero_client()
        # 调用 Zotero API 或 client.py 中的辅助函数
        result = ...
        return format_as_markdown(result)
    except Exception as e:
        ctx.error(str(e))
        return f"Error: {str(e)}"
```

2. 参数类型注解会自动生成 `inputSchema`，影响 AI 的参数构造。
3. 返回 Markdown 字符串，便于 AI 理解与展示。

### 4.4 配置加载顺序（cli.py）

1. `~/.config/zotero-mcp/config.json`（独立配置）
2. Claude Desktop 的 `claude_desktop_config.json`（除非 `ZOTERO_NO_CLAUDE=true`）
3. 默认值：`ZOTERO_LOCAL=true`、`ZOTERO_LIBRARY_ID=0`

### 4.5 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_server_advanced_search.py -v

# 带覆盖率
pytest --cov=zotero_mcp
```

### 4.6 代码风格

项目使用 black 和 isort：

```bash
black src/ tests/
isort src/ tests/
```

或使用 pre-commit（若已配置）：

```bash
pre-commit run --all-files
```

---

## 五、常用开发场景

### 5.1 调试 MCP 服务器

1. 使用 stdio 时，可在 `cli.py` 的 `main()` 或 `server.py` 的工具函数内加 `print()` 或 `sys.stderr.write()`，输出会出现在 Cursor 的 MCP 日志中。
2. 使用 HTTP 传输时，可直接在终端运行并观察输出：

```bash
zotero-mcp serve --transport streamable-http --host 127.0.0.1 --port 8000
```

### 5.2 修改后快速验证

因使用 `pip install -e .`，修改 Python 源码后**无需重新安装**，只需：

1. 若 Cursor 已连接：在 Cursor 中重新加载 MCP 或重启 Cursor。
2. 若手动运行：重新执行 `zotero-mcp serve`。

### 5.3 添加新依赖

在 `pyproject.toml` 的 `dependencies` 中添加，然后：

```bash
pip install -e ".[dev]"
```

### 5.4 构建发布包

```bash
pip install build
python -m build
```

---

## 六、参考资源

| 资源 | 链接 |
|------|------|
| MCP 官方文档 | https://modelcontextprotocol.io |
| Zotero MCP 仓库 | https://github.com/54yyyu/zotero-mcp |
| 详细中文文档 | [docs/ZOTERO_MCP_中文文档.md](./ZOTERO_MCP_中文文档.md) |
| 快速入门 | [docs/getting-started.md](./getting-started.md) |

---

## 七、常见问题

**Q: 修改代码后 Cursor 没有反应？**  
A: 确认使用 `pip install -e .` 安装；在 Cursor 中重新加载 MCP 连接或重启 Cursor。

**Q: 如何指定开发用的 Python 解释器？**  
A: 在 MCP 配置的 `command` 中使用虚拟环境中的 `python.exe` 完整路径，例如：`D:\...\zotero-mcp\.venv\Scripts\python.exe`，`args` 为 `["-m", "zotero_mcp.cli", "serve"]`。

**Q: 构建时报错缺少 hatchling？**  
A: 运行 `pip install hatchling` 或 `pip install -e ".[dev]"` 会一并安装构建依赖。

**Q: 如何关闭从 Claude Desktop 配置加载环境变量？**  
A: 设置环境变量 `ZOTERO_NO_CLAUDE=true`，并确保 `~/.config/zotero-mcp/config.json` 中有正确的 `client_env` 配置。
