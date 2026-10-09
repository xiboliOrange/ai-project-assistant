# 文件上传接口 Spec

## 1. 目标

提供本地文件批量上传服务。文件保存到磁盘，基础信息保存到 SQLite，供后续检索和内容处理使用。上传时不读取正文；摘要和关键词由用户填写或后续由 LLM 生成。

## 2. 范围

- 支持一次上传多个文件。
- 仅支持 `.txt`、`.md`，扩展名不区分大小写。
- 单个文件大小不超过 10 MB（10 * 1024 * 1024 bytes）。
- 文件保存到 `data/uploads/`。
- 重名文件自动加编号，禁止覆盖已有文件。
- 使用 SQLite 保存文件索引。
- 支持查询文件、用户编辑摘要和关键词、后续调用 LLM 建立索引。
- 本版本不包含认证、权限、断点续传、在线编辑和二进制文件处理。

## 3. 文件命名

保存 `note.md` 时，如果目标已存在，依次尝试：

```text
note.md
note_1.md
note_2.md
```

直到找到未占用的文件名。原始文件名和实际保存文件名都必须写入索引。

## 4. SQLite 数据模型

建立 `files` 表：

| 字段 | 类型 | 约束 | 说明 |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY | 文件 ID |
| original_filename | TEXT | NOT NULL | 原始文件名 |
| stored_filename | TEXT | NOT NULL UNIQUE | 实际保存文件名 |
| file_path | TEXT | NOT NULL UNIQUE | 相对项目根目录的路径 |
| file_type | TEXT | NOT NULL | txt 或 md |
| file_size | INTEGER | NOT NULL | bytes |
| uploaded_at | TEXT | NOT NULL | ISO 8601 时间 |
| summary | TEXT | NULL | 摘要 |
| keywords | TEXT | NULL | JSON 字符串数组 |
| summary_source | TEXT | NULL | user、llm 或 NULL |
| keywords_source | TEXT | NULL | user、llm 或 NULL |

用户填写的摘要或关键词优先级最高，后续 LLM 操作不得覆盖对应字段。

## 5. 接口

### 5.1 批量上传

```http
POST /files
Content-Type: multipart/form-data
```

字段：

```text
files: UploadFile[]
```

处理流程：

1. 校验是否至少有一个文件；
2. 逐个校验扩展名和大小；
3. 分配不冲突的保存文件名；
4. 保存到 `data/uploads/`；
5. 写入 SQLite；
6. 返回每个文件的成功或失败结果。

上传时不得读取正文，也不得调用 LLM。

成功项示例：

```json
{
  "success": true,
  "id": 1,
  "original_filename": "note.md",
  "stored_filename": "note_1.md",
  "file_size": 2048
}
```

失败项示例：

```json
{
  "success": false,
  "original_filename": "image.png",
  "error_code": "UNSUPPORTED_FILE_TYPE",
  "message": "Only .txt and .md files are supported."
}
```

批量上传中单个文件失败，不影响其他合法文件。文件已保存但 SQLite 写入失败时，删除本次保存的文件，避免产生孤儿文件。

### 5.2 查询文件列表

```http
GET /files
```

按 `uploaded_at` 倒序返回元数据，不读取正文。至少返回：

```json
{
  "items": [
    {
      "id": 1,
      "original_filename": "note.md",
      "stored_filename": "note_1.md",
      "file_type": "md",
      "file_size": 2048,
      "uploaded_at": "2026-10-08T12:00:00+08:00",
      "summary": null,
      "keywords": [],
      "summary_source": null,
      "keywords_source": null
    }
  ]
}
```

### 5.3 查询详情

```http
GET /files/{id}
```

只返回元数据，不返回正文。文件不存在返回 HTTP 404，错误码 `FILE_NOT_FOUND`。

### 5.4 修改用户元数据

```http
PATCH /files/{id}/metadata
Content-Type: application/json
```

请求：

```json
{
  "summary": "关于 FastAPI 上传接口的学习笔记",
  "keywords": ["FastAPI", "上传", "Python"]
}
```

只更新请求中出现的字段。更新摘要时将 `summary_source` 设为 `user`；更新关键词时将 `keywords_source` 设为 `user`。用户值可以覆盖旧的 LLM 值。

### 5.5 LLM 建立索引

```http
POST /files/{id}/index
```

处理流程：

1. 根据 ID 查找文件；
2. 读取对应的 txt 或 md 正文；
3. 调用 LLM 生成摘要和关键词；
4. 只更新来源不是 `user` 的字段；
5. 将生成字段的来源设为 `llm`。

文件不存在返回 404。LLM 调用失败时不修改已有元数据，并返回 `LLM_FAILED`。

## 6. 错误码

| 错误码 | HTTP 状态 | 条件 |
|---|---:|---|
| NO_FILES | 400 | 没有上传文件 |
| UNSUPPORTED_FILE_TYPE | 400 | 不是 txt 或 md |
| FILE_TOO_LARGE | 413 | 超过 10 MB |
| FILE_NOT_FOUND | 404 | ID 不存在 |
| SAVE_FAILED | 500 | 文件保存失败 |
| INDEX_SAVE_FAILED | 500 | SQLite 写入失败 |
| LLM_FAILED | 502 | LLM 生成失败 |

## 7. 验收标准

- [ ] 可以一次上传多个 txt/md 文件。
- [ ] 非支持格式和超过 10 MB 的文件会被拒绝。
- [ ] 重名文件会自动编号且不覆盖旧文件。
- [ ] 文件保存到 `data/uploads/`，索引写入 SQLite。
- [ ] 上传时不读取正文、不调用 LLM。
- [ ] 可以查询文件列表和详情。
- [ ] 用户可以分别修改摘要和关键词。
- [ ] LLM 生成结果不会覆盖用户自定义字段。
- [ ] 批量上传中单个失败不影响其他合法文件。
- [ ] SQLite 写入失败时不会留下未索引文件。
