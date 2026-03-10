# Zotero MCP 中文文档

本文档介绍 Zotero MCP 的使用方法、MCP 协议原理、Cursor 连接时 AI 如何识别工具、MCP 架构、代码实现、PDF 读取、语义搜索索引构造与嵌入模型。

---

## 一、如何使用

### 1.1 安装

**推荐方式（uv）：**
```bash
uv tool install zotero-mcp-server
zotero-mcp setup  # 自动配置
```

**pip 安装：**
```bash
pip install zotero-mcp-server
zotero-mcp setup
```

**pipx 安装：**
```bash
pipx install zotero-mcp-server
zotero-mcp setup
```

### 1.2 环境要求

- Python 3.10+
- Zotero 7+（本地 API 全文访问）
- 支持 MCP 的客户端（Claude Desktop、ChatGPT、Cursor、Cherry Studio、Chorus 等）

### 1.3 配置方式

#### 方式一：本地 Zotero（推荐）

1. 在 Zotero 中启用本地 API：
   - 编辑 → 首选项 → 高级 → API → 勾选「允许其他应用程序与 Zotero 通信」
2. 运行 `zotero-mcp setup` 自动配置，或手动在 MCP 客户端配置中加入：
   ```json
   {
     "mcpServers": {
       "zotero": {
         "command": "zotero-mcp",
         "env": {
           "ZOTERO_LOCAL": "true"
         }
       }
     }
   }
   ```

#### 方式二：Zotero Web API

适用于远程访问或云端库：
```bash
zotero-mcp setup --no-local --api-key YOUR_API_KEY --library-id YOUR_LIBRARY_ID
```

### 1.4 与各客户端集成

| 客户端 | 配置说明 |
|--------|----------|
| **Claude Desktop** | 在 `claude_desktop_config.json` 中添加上述配置，重启 Claude |
| **Cursor** | `Ctrl+Shift+J` → Tools & MCP → 添加服务器；或编辑 `~/.cursor/mcp.json` / `.cursor/mcp.json`，详见 [开发指南](./DEVELOPMENT_GUIDE.md#27-在-cursor-中配置-mcp) |
| **ChatGPT** | 需通过 ngrok 等隧道将本地 MCP 暴露到公网，详见 [getting-started.md](./getting-started.md) |
| **Cherry Studio** | 设置 → MCP 服务器 → 添加 zotero-mcp |
| **Chorus** | 使用 `zotero-mcp setup-info` 获取路径，在 Chorus 偏好中配置 |

### 1.5 语义搜索配置

```bash
# 初始化语义搜索数据库（快速，仅元数据）
zotero-mcp update-db

# 带全文提取（更全面，较慢）
zotero-mcp update-db --fulltext

# 查看数据库状态
zotero-mcp db-status
```

### 1.6 常用命令

| 命令 | 说明 |
|------|------|
| `zotero-mcp serve` | 启动 MCP 服务器（默认 stdio） |
| `zotero-mcp setup` | 配置 Zotero 与语义搜索 |
| `zotero-mcp setup-info` | 显示安装路径和配置信息 |
| `zotero-mcp update-db` | 更新语义搜索数据库 |
| `zotero-mcp db-status` | 语义数据库状态 |
| `zotero-mcp update` | 更新 zotero-mcp 到最新版 |
| `zotero-mcp version` | 显示版本 |

### 1.7 示例提示词

- 「在我的库中搜索关于机器学习的论文」
- 「找出我最近添加的气候变化相关文章」
- 「总结我关于量子计算的论文的主要发现」
- 「提取我神经网络论文 PDF 中的所有批注」
- 「用语义搜索找与深度学习在计算机视觉中应用相似的研究」

---

## 二、MCP 是怎么工作的

### 2.1 协议概述

**Model Context Protocol (MCP)** 是一个开放协议，用于标准化应用程序如何向大语言模型（LLM）提供**工具**和**上下文**。它充当桥梁，让 AI 能够访问实时数据、调用外部系统并执行操作。

MCP 服务器通过三种能力与 AI 交互：

| 能力 | 说明 | 谁控制 |
|------|------|--------|
| **Tools（工具）** | 模型可主动调用的函数，根据用户请求决定何时使用 | 模型 |
| **Resources（资源）** | 只读数据源，如文件、数据库、API 文档 | 应用 |
| **Prompts（提示）** | 预定义的指令模板，引导模型使用特定工具 | 用户 |

Zotero MCP 主要暴露 **Tools**，不提供 Resources 或 Prompts。

### 2.2 工具发现与调用流程

当 Cursor（或其他 MCP 客户端）连接 Zotero MCP 时，大致流程如下：

```
┌─────────────┐                    ┌─────────────┐                    ┌─────────────┐
│   Cursor    │                    │  zotero-mcp │                    │   Zotero    │
│  (MCP 客户端) │                    │  (MCP 服务器) │                    │  (本地/API)  │
└──────┬──────┘                    └──────┬──────┘                    └──────┬──────┘
       │                                  │                                  │
       │  1. 启动子进程 zotero-mcp serve    │                                  │
       │ ───────────────────────────────> │                                  │
       │     (stdio 或 HTTP 传输)          │                                  │
       │                                  │                                  │
       │  2. tools/list（发现可用工具）     │                                  │
       │ ───────────────────────────────> │                                  │
       │                                  │                                  │
       │  3. 返回工具列表（名称、描述、参数 schema）                           │
       │ <─────────────────────────────── │                                  │
       │                                  │                                  │
       │  ... 用户输入：「搜索机器学习论文」 ...                               │
       │                                  │                                  │
       │  4. AI 选择工具并构造参数          │                                  │
       │     tools/call(zotero_search_items, {query: "机器学习"})               │
       │ ───────────────────────────────> │                                  │
       │                                  │  5. 调用 Zotero API              │
       │                                  │ ───────────────────────────────> │
       │                                  │ <─────────────────────────────── │
       │                                  │  6. 格式化结果                    │
       │  7. 返回 Markdown 结果            │                                  │
       │ <─────────────────────────────── │                                  │
       │                                  │                                  │
       │  8. AI 将结果整合进回复            │                                  │
       │                                  │                                  │
```

### 2.3 工具发现（tools/list）

MCP 客户端通过 **`tools/list`** 请求发现可用工具。服务器返回每个工具的：

- **name**：唯一标识符（如 `zotero_search_items`）
- **description**：人类可读的功能描述
- **inputSchema**：JSON Schema，定义参数类型、必填项、说明

例如 Zotero MCP 的 `zotero_search_items` 会返回类似：

```json
{
  "name": "zotero_search_items",
  "description": "Search for items in your Zotero library, given a query string.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": { "type": "string", "description": "Search query string" },
      "qmode": { "type": "string", "default": "titleCreatorYear" },
      "limit": { "type": "integer", "default": 10 }
    },
    "required": ["query"]
  }
}
```

FastMCP 会根据 `@mcp.tool()` 装饰的函数签名和 docstring 自动生成上述 schema。

### 2.4 工具调用（tools/call）

当 AI 决定使用某个工具时，客户端发送 **`tools/call`** 请求，包含工具名和参数。服务器执行对应 Python 函数，将返回值作为结果返回给客户端，再由客户端交给 AI 处理。

### 2.5 Cursor 连接时，AI 如何识别相关工具？

当你通过 Cursor 连接 Zotero MCP 时，识别过程如下：

1. **连接阶段**：Cursor 根据配置启动 `zotero-mcp serve`，建立与 MCP 服务器的通信（通常为 stdio）。

2. **发现阶段**：Cursor 向 zotero-mcp 发送 `tools/list`，获取全部工具的名称、描述和参数 schema。这些信息被缓存在 Cursor 侧。

3. **注入上下文**：在每次对话中，Cursor 会把**当前已启用 MCP 服务器的工具列表**（含 name、description、inputSchema）作为**系统提示的一部分**注入给 AI 模型。因此模型「知道」有哪些工具可用、每个工具做什么、需要什么参数。

4. **语义匹配**：当你输入「搜索我库里的机器学习论文」时，AI 根据：
   - 工具描述（如 "Search for items in your Zotero library"）
   - 参数含义（如 `query` 对应搜索关键词）
   - 与当前对话的语义相关性  

   推断应调用 `zotero_search_items`，并构造 `{"query": "机器学习"}` 等参数。

5. **执行与反馈**：Cursor 将 AI 选定的工具调用发给 zotero-mcp，收到结果后再交回 AI，由 AI 组织成最终回复。

**要点**：AI 并不「猜测」工具，而是依赖 MCP 协议提供的**结构化 schema**。清晰的 `description` 和 `inputSchema` 能显著提高 AI 选对工具、填对参数的概率。Zotero MCP 中每个 `@mcp.tool()` 的 `description` 和函数参数类型注解，都会影响 AI 的识别效果。

---

## 三、MCP 是如何构建的

### 3.1 技术栈

| 组件 | 技术 |
|------|------|
| MCP 框架 | **FastMCP**（基于 MCP SDK） |
| MCP SDK | `mcp>=1.2.0` |
| 构建系统 | Hatchling |
| 入口脚本 | `zotero-mcp = "zotero_mcp.cli:main"` |

### 3.2 服务器创建流程

1. **创建 FastMCP 实例**（`server.py`）：
   ```python
   mcp = FastMCP("Zotero", lifespan=server_lifespan)
   ```

2. **生命周期管理**（`server_lifespan`）：
   - 启动时：检查语义搜索配置，若需自动更新则在后台更新数据库
   - 关闭时：取消后台任务，优雅退出

3. **传输方式**：
   - **stdio**（默认）：`zotero-mcp serve` 或 `zotero-mcp serve --transport stdio`
   - **streamable-http**：`--transport streamable-http --host localhost --port 8000`
   - **sse**（已弃用）：`--transport sse --host localhost --port 8000`

### 3.3 配置加载顺序

1. `~/.config/zotero-mcp/config.json`（独立配置）
2. Claude Desktop 的 `claude_desktop_config.json`（除非设置 `ZOTERO_NO_CLAUDE=true`）
3. 本地模式默认值（`ZOTERO_LOCAL=true`, `ZOTERO_LIBRARY_ID=0`）

### 3.4 工具注册方式

所有工具通过 `@mcp.tool()` 装饰器注册，例如：

```python
@mcp.tool(
    name="zotero_search_items",
    description="Search for items in your Zotero library, given a query string."
)
def search_items(query: str, qmode: str = "titleCreatorYear", ..., *, ctx: Context) -> str:
    ...
```

### 3.5 可用工具一览

| 类别 | 工具名 | 功能 |
|------|--------|------|
| **搜索** | `zotero_search_items` | 关键词搜索 |
| | `zotero_advanced_search` | 高级多条件搜索 |
| | `zotero_search_by_tag` | 按标签搜索 |
| | `zotero_search_notes` | 搜索笔记和批注 |
| **库/集合** | `zotero_get_collections` | 列出集合 |
| | `zotero_get_collection_items` | 获取集合内条目 |
| | `zotero_get_tags` | 列出标签 |
| | `zotero_get_recent` | 最近添加的条目 |
| **内容** | `zotero_get_item_metadata` | 获取元数据（支持 BibTeX） |
| | `zotero_get_item_fulltext` | 获取全文 |
| | `zotero_get_item_children` | 获取附件和子项 |
| **多库** | `zotero_list_libraries` | 列出库 |
| | `zotero_switch_library` | 切换当前库 |
| **订阅** | `zotero_list_feeds` | 列出订阅 |
| | `zotero_get_feed_items` | 获取订阅条目 |
| **批注/笔记** | `zotero_get_annotations` | 获取批注 |
| | `zotero_get_notes` | 获取笔记 |
| | `zotero_create_note` | 创建笔记 |
| | `zotero_create_annotation` | 创建批注 |
| **语义搜索** | `zotero_semantic_search` | 向量相似度搜索 |
| | `zotero_update_search_database` | 手动更新语义库 |
| | `zotero_get_search_database_status` | 查看数据库状态 |
| **ChatGPT 兼容** | `search` | ChatGPT 期望的搜索接口 |
| | `fetch` | ChatGPT 期望的获取接口 |

### 3.6 Smithery 部署

项目包含 `smithery.yaml`，可在 [Smithery.ai](https://smithery.ai) 上部署为托管 MCP。配置支持 `zoteroLocal`、`zoteroApiKey`、`zoteroLibraryId` 等选项。

---

## 四、代码是怎么写的

### 4.1 项目结构

```
zotero-mcp/
├── src/zotero_mcp/
│   ├── __init__.py          # 包入口，导出 mcp 和 __version__
│   ├── server.py            # MCP 服务器与所有工具定义（~3000 行）
│   ├── cli.py               # CLI 入口与子命令
│   ├── client.py            # Zotero 客户端封装（pyzotero / 本地 API）
│   ├── semantic_search.py   # 语义搜索（ChromaDB + 嵌入）
│   ├── chroma_client.py     # ChromaDB 客户端
│   ├── local_db.py          # 本地 Zotero 数据库访问
│   ├── pdf_utils.py         # PDF 处理（PyMuPDF）
│   ├── pdfannots_downloader.py  # PDF 批注下载
│   ├── pdfannots_helper.py  # PDF 批注辅助
│   ├── epub_utils.py        # EPUB 处理
│   ├── better_bibtex_client.py  # Better BibTeX 集成
│   ├── setup_helper.py      # 配置与安装辅助
│   ├── updater.py           # 更新逻辑
│   └── utils.py             # 通用工具
├── tests/                   # 测试
├── docs/                    # 文档
├── pyproject.toml           # 项目与依赖
├── smithery.yaml            # Smithery 配置
└── Dockerfile               # 容器镜像
```

### 4.2 核心模块说明

#### server.py

- 使用 `FastMCP` 创建 MCP 服务器
- 通过 `@mcp.tool()` 注册工具，每个工具接收 `ctx: Context` 用于日志
- 工具内部调用 `client.py` 的 `get_zotero_client()` 获取 Zotero 客户端
- 为 ChatGPT 提供 `search` 和 `fetch` 两个兼容工具，内部转发到主工具

#### client.py

- `get_zotero_client()`：根据环境变量返回本地或 Web API 的 Zotero 客户端
- 支持运行时库切换（`set_active_library` / `clear_active_library`）
- `get_attachment_details()`、`format_item_metadata()`、`generate_bibtex()` 等辅助函数

#### semantic_search.py

- `ZoteroSemanticSearch`：封装 ChromaDB 向量搜索
- 支持多种嵌入模型：默认（sentence-transformers）、OpenAI、Gemini
- `create_semantic_search()`：从配置文件创建搜索实例
- `update_database()`：索引 Zotero 条目到 ChromaDB

#### cli.py

- `main()`：解析命令行，分发到 `serve`、`setup`、`update-db` 等子命令
- `setup_zotero_environment()`：按优先级加载环境变量（独立配置 → Claude 配置 → 默认值）
- `serve` 命令调用 `mcp.run(transport=...)` 启动服务器

### 4.3 依赖关系

```
pyproject.toml 核心依赖：
├── pyzotero>=1.5.0      # Zotero API 客户端
├── mcp>=1.2.0           # MCP SDK
├── fastmcp>=2.14.0      # FastMCP 框架
├── chromadb>=0.4.0      # 向量数据库
├── sentence-transformers>=2.2.0  # 默认嵌入模型
├── openai>=1.0.0        # OpenAI 嵌入
├── google-genai>=0.7.0  # Gemini 嵌入
├── pymupdf>=1.24.0      # PDF 处理
├── markitdown[pdf]      # Markdown 转换
├── pydantic>=2.0.0      # 数据验证
└── ...
```

### 4.4 工具实现模式

典型工具实现模式：

```python
@mcp.tool(name="zotero_xxx", description="...")
def tool_name(param: str, *, ctx: Context) -> str:
    try:
        ctx.info("操作描述")  # 可选：记录日志
        zot = get_zotero_client()
        # 调用 pyzotero API
        results = zot.items(...)
        # 格式化为 Markdown 返回
        return format_as_markdown(results)
    except Exception as e:
        ctx.error(str(e))
        return f"Error: {str(e)}"
```

### 4.5 环境变量

| 变量 | 说明 |
|------|------|
| `ZOTERO_LOCAL` | 使用本地 Zotero API |
| `ZOTERO_API_KEY` | Web API 密钥 |
| `ZOTERO_LIBRARY_ID` | 库 ID |
| `ZOTERO_LIBRARY_TYPE` | 库类型（user/group） |
| `ZOTERO_EMBEDDING_MODEL` | 嵌入模型（default/openai/gemini） |
| `OPENAI_API_KEY` | OpenAI 嵌入用 |
| `GEMINI_API_KEY` | Gemini 嵌入用 |
| `ZOTERO_DB_PATH` | 自定义 zotero.sqlite 路径 |
| `ZOTERO_NO_CLAUDE` | 禁用从 Claude 配置加载 |

---

## 五、PDF 读取、语义搜索索引与嵌入模型

### 5.1 PDF 是怎么读取的

项目中 PDF 的读取分为**三种用途**，使用不同库：

| 用途 | 模块 | 库 | 说明 |
|------|------|-----|------|
| **批注创建时的文本定位** | `pdf_utils.py` | **PyMuPDF** (fitz) | 提取页面文本块（`page.get_text("dict")`）、搜索文本位置（`page.search_for()`）、锚点匹配、模糊匹配，用于创建 Zotero 高亮批注的坐标 |
| **语义搜索全文提取** | `local_db.py` | **pdfminer** | 通过 `pdfminer.high_level.extract_text()` 从本地附件 PDF 提取文本，用于 `update-db --fulltext` 时的向量索引；默认最多 10 页（可配置 `ZOTERO_PDF_MAXPAGES` 或 `semantic_search.extraction.pdf_max_pages`） |
| **全文展示（get_item_fulltext）** | `client.py` | **MarkItDown** | `markitdown[pdf]` 将 PDF 转为 Markdown，供 AI 阅读；MarkItDown 内部使用 pdfminer 等处理 PDF |

**流程简述**：

- **批注**：`pdf_utils.find_text_position()` → PyMuPDF 打开 PDF → 按页提取 span/bbox → 精确/模糊匹配 → 返回 Zotero 所需 `rects`、`pageIndex`
- **全文索引**：`local_db._extract_text_from_pdf()` → 解析附件路径（`storage:xxx.pdf`）→ pdfminer 提取文本 → 截断至 10000 字符 → 写入 ChromaDB
- **全文展示**：`client.convert_to_markdown()` → MarkItDown 转换 → 返回 Markdown 文本

### 5.2 语义搜索索引是如何构造的

**数据来源**：

- **API 模式**（`update-db` 无 `--fulltext` 或非本地）：从 Zotero Web/本地 API 拉取条目，仅用元数据
- **本地全文模式**（`update-db --fulltext` 且本地 Zotero）：直接读 `zotero.sqlite`，从附件 PDF/HTML 提取全文

**文档文本构造**（`semantic_search._create_document_text`）：

1. 若有全文（`fulltext`）：优先使用全文
2. 否则拼接：标题、作者、摘要、期刊、标签、笔记等

**元数据**（`_create_metadata`）：`item_key`、`item_type`、`title`、`date`、`creators`、`publication`、`url`、`doi`、`tags`、`citation_key`、`has_fulltext`、`fulltext_source` 等

**索引流程**：

1. 获取条目列表（API 或本地 DB）
2. 按批（50 条）处理
3. 对每条：构造 `doc_text` + `metadata`，用 `_truncate_to_tokens()` 截断到嵌入模型 token 上限
4. 调用 ChromaDB `upsert_documents(documents, metadatas, ids)` 写入
5. ChromaDB 内部对 `documents` 做嵌入并存入向量库

**去重**：本地模式下，preprint 与 journalArticle 若 DOI/标题相同，只保留 journalArticle。

### 5.3 使用的嵌入模型

| 配置值 | 实际模型 | 来源 | Token 上限 | 说明 |
|--------|----------|------|------------|------|
| `default` | **all-MiniLM-L6-v2** | ChromaDB 内置 | 256 | 免费、本地、轻量 |
| `openai` | **text-embedding-3-small**（默认）或 text-embedding-3-large | OpenAI API | 8000 | 需 API Key，质量较好 |
| `gemini` | **gemini-embedding-001** | Google Gemini API | 2000 | 需 API Key |
| `qwen` | **Qwen/Qwen3-Embedding-0.6B** | sentence-transformers | 模型元数据 | 本地，中文友好 |
| `embeddinggemma` | **google/embeddinggemma-300m** | sentence-transformers | 模型元数据 | 本地 |
| 任意 HuggingFace 模型名 | 指定模型 | sentence-transformers | 模型元数据 | 可自定义 |

**环境变量**：`ZOTERO_EMBEDDING_MODEL`、`OPENAI_API_KEY`、`OPENAI_EMBEDDING_MODEL`、`GEMINI_API_KEY`、`GEMINI_EMBEDDING_MODEL` 等。

**Token 截断**：长文本用 `tiktoken`（cl100k_base）或字符估算截断到模型上限，避免嵌入失败。

---

## 六、故障排除

- **无结果**：确认 Zotero 已启动且本地 API 已启用
- **无法连接**：检查 API Key 和 Library ID（Web API）
- **全文不可用**：需 Zotero 7+ 且本地模式
- **语义搜索报错**：运行 `zotero-mcp setup` 配置环境，或 `zotero-mcp update-db --force-rebuild` 重建数据库

更多问题可参考 [README.md](../README.md) 的 Troubleshooting 部分。
