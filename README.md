# openclaw-mimo-patch

修复 OpenClaw 使用小米 MiMo 推理模型时，tool calling 第二轮请求报 **400 Param Incorrect** 的问题。

## 问题描述

当 OpenClaw 使用 MiMo 推理模型（mimo-v2.5-pro、mimo-v2-pro 等）作为默认模型时，**tool calling 第二轮请求失败**：

```
provider rejected the request schema or tool payload
400 Param Incorrect
```

**根因**：MiMo 是推理模型（类似 DeepSeek-R1）。首次请求返回的响应中包含 `reasoning_content` 字段。OpenClaw 执行完工具后发起第二轮请求时，没有把 `reasoning_content` 传回去，而 MiMo API 要求 thinking mode 下 assistant message 必须携带此字段（哪怕为空字符串 `""`），因此 API 返回 400。

```
请求1（正常）: OpenClaw → MiMo → tool_calls + reasoning_content
               OpenClaw 执行工具
请求2（失败）: OpenClaw → MiMo（缺少 reasoning_content）→ ❌ 400
```

## 一键修复

**Windows（PowerShell）**：
```powershell
irm https://raw.githubusercontent.com/mikeyoubeach/openclaw-mimo-patch/master/patch.py | python
openclaw gateway restart
```

**macOS / Linux（Bash）**：
```bash
curl -sL https://raw.githubusercontent.com/mikeyoubeach/openclaw-mimo-patch/master/patch.py | python3
openclaw gateway restart
```

## 手动使用

```bash
git clone https://github.com/mikeyoubeach/openclaw-mimo-patch.git
cd openclaw-mimo-patch

python patch.py            # 打补丁
python patch.py --check    # 检查状态（不修改文件）
python patch.py --revert   # 恢复原状
```

打完补丁后重启 OpenClaw：
```bash
openclaw gateway restart
```

## 何时需要重新打补丁

以下操作会覆盖补丁，需要重新执行：
- `npm update openclaw`
- `npm install openclaw@latest`
- OpenClaw 版本号变更

## 环境要求

- Python 3.6+
- OpenClaw 通过 npm 安装

## 技术细节

**修改的文件**：
```
<npm全局路径>/node_modules/openclaw/node_modules/@earendil-works/pi-ai/dist/providers/openai-completions.js
```

**修改内容**：在 `convertMessages` 函数（约第 700 行）中，原来的条件：
```js
if (compat.requiresReasoningContentOnAssistantMessages && model.reasoning && ...)
```

扩展为同时覆盖 `model.provider === "xiaomi"`：
```js
const needsReasoningContent =
    compat.requiresReasoningContentOnAssistantMessages ||
    (model.reasoning && model.provider === "xiaomi");
if (needsReasoningContent && model.reasoning && ...)
```

这与代码库中 DeepSeek 模型的处理方式一致。

## 已测试模型

| 模型 | 状态 |
|------|------|
| mimo-v2.5-pro | ✅ 已修复 |
| mimo-v2.5 | ✅ 已修复 |
| mimo-v2-pro | ✅ 已修复 |
| mimo-v2-omni | ✅ 已修复 |
| mimo-v2-flash | 无需（reasoning=false） |

## 许可证

MIT
