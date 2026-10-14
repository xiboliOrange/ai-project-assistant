# 本地 AI 项目助手

中文 | [English](README_EN.md)

面向开发者的本地项目文档问答工具，帮助用户从 README、设计文档、接口文档、Issue 和代码注释中快速找到答案，并通过明确引用回到原文验证。

## 项目简介

开发者熟悉一个陌生项目时，通常需要在多个文档和代码文件之间反复搜索。普通聊天式 AI 虽然能够快速回答，但很难判断答案来自项目资料、模型常识，还是模型推测。

本项目将“可验证”作为核心体验：系统基于项目资料进行问答，回答尽量绑定到具体文件、章节、段落或代码行；当资料不足以支持结论时，明确提示缺少依据，而不是编造确定答案。

## 核心特点

- 导入项目文档并建立本地索引；
- 基于项目资料进行自然语言问答；
- 回答附带文件、章节、段落或行号等引用；
- 点击引用后可以回到相关原文进行验证；
- 资料不足、引用失效或模型请求失败时，提供清晰的状态和恢复提示；
- 区分本地资料存储与模型服务配置，明确外部模型可能接收的资料范围。

## Demo 场景

用户导入一个项目的 README、架构文档、API 文档和 Issue 后，提问：

> 用户登录失败时，客户端会经过哪些模块？

系统根据已导入资料生成登录流程说明，并在回答下方展示相关引用。用户点击引用后，可以直接定位到认证流程章节、登录接口说明或异常处理 Issue，快速确认回答是否有依据。

如果资料中没有覆盖某个问题，系统会提示“当前资料中缺少足够依据”，而不是将推测写成项目事实。

## 技术方向

- Qt 5.14 客户端
- Python / FastAPI 服务
- 自研 MCP Server
- 本地文件解析、内容分段和索引
- 支持本地模型及用户自行配置的模型 API

## 当前状态

开发中。Python 服务已实现文件上传、元数据查询和编辑，以及手动触发的摘要与关键词生成；项目问答、引用和 Qt 客户端仍在设计或开发中。

### 运行文件服务

需要 Python 3.11 或更高版本。先确认 `python --version`；若默认版本较低，请将下方首行的 `python` 换成 Python 3.11 的可执行文件路径。在项目根目录执行：

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --reload
```

接口文档位于 `http://127.0.0.1:8000/docs`。上传的文件和 SQLite 索引分别保存在 `data/uploads/` 与 `data/files.sqlite3`，均为本地运行数据。

`POST /files/{id}/index` 需要设置 `AI_PROJECT_LLM_URL`（完整的 Chat Completions URL）、`AI_PROJECT_LLM_MODEL`，以及服务需要时的 `AI_PROJECT_LLM_API_KEY`。只有调用该接口时，服务才会将对应文件的 UTF-8 正文发送给所配置的模型服务。其他文件接口不调用模型。

文件接口测试用例、自动化代码和可重复使用的上传样例文件位于 [`test/files/`](test/files/test-cases.md)。样例文件保存在 `test/files/fixtures/`，测试运行不会删除它们。安装测试依赖并运行：

```powershell
.\venv\Scripts\python.exe -m pip install -r test\requirements.txt
.\venv\Scripts\python.exe -m unittest discover -s test\files -p "test_*.py" -v
```

## 后续补充

- 运行方式与环境配置
- 项目截图和交互演示
- 系统架构图
- 功能开发进度
- 目录结构与开发说明
