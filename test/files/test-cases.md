# 文件上传接口测试用例

依据：[`specs/file-upload.md`](../../specs/file-upload.md)。自动化代码见 [`test_file_upload_api.py`](test_file_upload_api.py)。

上传用的样例文件固定存放在 [`fixtures/`](fixtures/)；测试运行时直接读取，不重新生成，也不删除。为保证重复运行结果一致，接口保存的副本和 SQLite 数据库仍放在每个用例独立的临时目录。模型调用由测试替身模拟，不向真实模型服务发送文件内容。

| 样例文件 | 用途 |
|---|---|
| `first.txt`、`second.MD`、`note.md` | 合法文本、大小写扩展名、重名与建索引 |
| `unsupported.csv` | 不支持的扩展名 |
| `empty.txt` | 零字节文件 |
| `limit.txt` | 恰好 10 MB |
| `too-large.txt` | 10 MB + 1 byte |

| 编号 | 接口与场景 | 输入或前置条件 | 预期结果 |
|---|---|---|---|
| FU-01 | `POST /files` 批量成功 | 同时上传 `first.txt` 和 `second.MD` | HTTP 200；两项成功；文件字节与数据库元数据正确；上传阶段不调用 LLM |
| FU-02 | `POST /files` 无文件 | 不传 `files` 字段 | HTTP 400，`NO_FILES` |
| FU-03 | 单项失败互不影响 | 一批包含 `.csv`、路径穿越名、Windows 保留名和合法 `.md` | HTTP 200；前三项分别返回对应错误码；合法文件保存且入库 |
| FU-04 | 文件大小边界 | 一个文件恰好 10 MB，另一个为 10 MB + 1 byte | 前者成功；后者返回 `FILE_TOO_LARGE`；超限文件不留在磁盘或索引中 |
| FU-05 | 重名编号与防覆盖 | 磁盘已有 `note.md`，再上传两个同名文件 | 保存为 `note_1.md`、`note_2.md`；原文件内容不变 |
| FU-06 | SQLite 写入失败清理 | 模拟数据库插入异常 | 单项返回 `INDEX_SAVE_FAILED`；本次保存的文件被删除 |
| FU-07 | 文件保存失败 | 上传目录位置被普通文件占用 | 单项返回 `SAVE_FAILED`；数据库无记录 |
| FU-08 | 查询列表、详情和不存在的 ID | 已上传两个文件 | `GET /files` 按时间倒序；详情只含元数据；不存在的 ID 返回 HTTP 404、`FILE_NOT_FOUND` |
| FU-09 | 用户编辑摘要和关键词 | 分别 PATCH 摘要与关键词，并提交非法关键词类型 | 只更新请求中的字段；来源设为 `user`；非法类型为 HTTP 422；不存在的 ID 为 404 |
| FU-10 | 手动建立索引 | 文件已有用户摘要，模型返回新摘要和关键词 | 仅调用索引接口时读取正文；保留用户摘要；生成关键词及 `llm` 来源 |
| FU-11 | 模型失败与不存在的 ID | 模拟模型异常 | HTTP 502、`LLM_FAILED`；已有元数据不变；不存在的 ID 为 404 |
| FU-12 | 空文件上传 | 上传 `empty.txt` | HTTP 200；记录的文件大小为 0；保存的文件为空 |

## 运行

在项目根目录、已建立 Python 3.11+ 虚拟环境后执行：

```powershell
.\venv\Scripts\python.exe -m pip install -r test\requirements.txt
.\venv\Scripts\python.exe -m unittest discover -s test\files -p "test_*.py" -v
```

HTTP 用例使用 FastAPI 的测试客户端直接向应用发送请求，不需要启动独立服务。同一命令也会运行迁入此目录的服务层与路由层测试。
