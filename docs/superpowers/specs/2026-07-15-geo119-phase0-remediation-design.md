# GEO119 Phase 0 整改设计

**Date**: 2026-07-15
**Source**: Phase0-端到端交付测试报告.md + Phase0-改进优化方案.md (R1-R13)
**Status**: draft

## Summary

Phase 0 交付物在 paperclip 侧全部通过（后端修复生效、wrapper 绑定正确、治理层完整），但 Hermes × paperclip 联调层暴露出配置脏数据、session 重建工具丢失、MCP 删除能力缺失、重复 import 污染四类问题，且后端的 403 修复直接改在 upstream 工作树、paperclip-mcp 版本浮动，存在升级后静默失效的风险。

本次整改覆盖 R1-R13 全部要求，交付 8 个动作，验收标准 9 条。

## Architecture

```
                        ┌──────────────────────────┐
                        │   phase0-regression-check │  ← 动作 8：升级门禁
                        │   (T1-T8 自动化验证)       │
                        └──────────┬───────────────┘
                                   │ 验证
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
   ┌────▼─────┐            ┌──────▼──────┐           ┌───────▼────────┐
   │ 防御层    │            │  自愈层      │           │  运维层         │
   │          │            │             │           │                │
   │ 动作1    │            │ 动作3       │           │ 动作7          │
   │ patch文件│            │ config脚本  │           │ 版本pin        │
   │          │            │             │           │                │
   │ 动作2    │            │ 动作4       │           │ 动作6          │
   │ 模板防御 │            │ auto-reload │           │ 环境清理       │
   │          │            │             │           │                │
   │ 动作5    │            │             │           │                │
   │ delete   │            │             │           │                │
   │ _agent   │            │             │           │                │
   └──────────┘            └─────────────┘           └────────────────┘
```

三层设计原则：
- **防御层**：每项关键功能至少有两条独立路径存活
- **自愈层**：升级后跑脚本恢复正确状态，不依赖人工记忆
- **运维层**：固化回归检查，升级即验证

## 组件版本基线 (2026-07-15)

| 组件 | 版本 | 升级风险 |
|------|------|---------|
| paperclip 后端 | paperclipai/paperclip (upstream) | 403 修复在 upstream 工作树，git pull 即覆盖 |
| paperclip-mcp | 0.4.0 (wizarck) | pyproject 未 pin 版本，uv run 静默拉最新 |
| FastMCP | 3.4.3 | 浮动依赖 |
| Hermes | 本地 ~/.hermes/hermes-agent | MCP 加载逻辑绑死当前 mcp_tool.py |

---

## 动作 1：后端 403 修复脱离 upstream（R9）

### 问题

`company-portability.ts:2712` 的 1 行修复直接改在 `/home/ok2049/paperclip`（upstream 工作树）。`git pull upstream` 或重新 clone 即覆盖，B/C import 403 重现。

### 方案

1. 从 `/home/ok2049/paperclip` 生成 patch 文件：
   ```bash
   cd /home/ok2049/paperclip
   git diff > /media/ok2049/work/work/paperclip-company-v2/patches/403-adapterType-fallback.patch
   ```

2. 源码 fork `/media/ok2049/work/tools/paperclip-src` 建分支 `geo119-phase0`，提交修复。

3. 运行目录用 `git apply` 方式应用 patch（而非直接编辑）。

4. 升级 paperclip 后：
   ```bash
   cd /home/ok2049/paperclip
   git stash && git pull upstream && git stash pop
   # 如果冲突：
   git apply /media/ok2049/work/work/paperclip-company-v2/patches/403-adapterType-fallback.patch
   ```

### 验证

```bash
grep "frontmatter.adapterType" /home/ok2049/paperclip/server/src/services/company-portability.ts
# 预期：回退逻辑存在
```

---

## 动作 2：模板层双重防御（R4）

### 问题

B 的 `.paperclip.yaml` 已有 adapter.type（用户手动添加）。C（agency-agents-v2）的 167 个 agent 全部缺失。如果动作 1 的 patch 丢了，C 的 import 会再次 403。

### 方案

为 C 模板 `.paperclip.yaml` 批量补全 `adapter.type: claude_local`。用脚本生成，167 个 agent slug 来自 `agency-agents/agents/*/` 目录列表。

生成格式（与 B 一致）：
```yaml
agents:
  academic-anthropologist:
    adapter:
      type: claude_local
  academic-geographer:
    adapter:
      type: claude_local
  # ... 167 total
```

### 防御逻辑

```
import_company_package
  → .paperclip.yaml 有 adapter.type?  → 用 .paperclip.yaml 的值
  → .paperclip.yaml 无 adapter.type?  → 后端回退读 AGENTS.md frontmatter (动作1)
  → 两者都无?                         → process → 403
```

### 验证

```bash
grep -c "adapter:" /media/ok2049/work/work/paperclip-company-v2/agency-agents-v2/agency-agents/.paperclip.yaml
# 预期：≥167（每个 agent 一个 adapter 块）
```

---

## 动作 3：Config 自愈脚本（R1、R5）

### 问题

当前 config 残留在：`paperclip: 'null'`（旧实例没删干净，Hermes 尝试解析字符串 `"null"` 为 MCP 配置）。恢复路径依赖人工记忆 `hermes config set` 命令序列，且 C1 约束下嵌套键无法通过 CLI 删除。

### 方案

创建 `paperclip-mcp-v2/setup-mcp-config.sh`，可重复执行：

```bash
#!/bin/bash
# setup-mcp-config.sh — 自愈 Hermes beta MCP 配置
# 可重复执行，幂等

CONFIG="$HOME/.hermes/profiles/beta/config.yaml"
API_KEY="pcp_board_e65a40681143c73cda97a250ed4d21c8eb48a43427f089ab"
BASE_URL="http://127.0.0.1:3100/api"

echo "=== Phase 0 MCP Config Self-Heal ==="

# 1. 清理旧实例残留（paperclip: 'null' 或 paperclip: 旧版）
if grep -q "paperclip:.*null\|^  paperclip:" "$CONFIG" 2>/dev/null; then
  echo "FIX: 删除旧 paperclip 实例残留"
  # hermes config set 不支持删除 key，直修 config.yaml（C1例外——仅此操作）
  python3 -c "
import yaml
with open('$CONFIG') as f: cfg = yaml.safe_load(f)
if 'paperclip' in cfg.get('mcp_servers', {}):
    del cfg['mcp_servers']['paperclip']
with open('$CONFIG', 'w') as f: yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
"
fi

# 2. 确保 paperclip_a/b/c 存在且 enabled
for inst in a b c; do
  cmd=$(hermes config get "mcp_servers.paperclip_${inst}.command" 2>/dev/null || echo "")
  if [ -z "$cmd" ]; then
    echo "FIX: 创建 paperclip_${inst}"
    hermes config set "mcp_servers.paperclip_${inst}.command" \
      "/media/ok2049/work/work/paperclip-mcp-v2/paperclip-mcp-v2-${inst}/wrapper.sh"
    hermes config set "mcp_servers.paperclip_${inst}.enabled" true
  fi
done

# 3. 清除 paperclip_a 的错误 env（JSON 字符串）
if grep -A2 "paperclip_a:" "$CONFIG" | grep -q "env:"; then
  echo "FIX: 删除 paperclip_a 的错误 env 段"
  python3 -c "
import yaml
with open('$CONFIG') as f: cfg = yaml.safe_load(f)
a = cfg['mcp_servers'].get('paperclip_a', {})
if 'env' in a:
    del a['env']
with open('$CONFIG', 'w') as f: yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)
"
fi

# 4. 验证 wrapper 可执行
for inst in a b c; do
  wrapper="/media/ok2049/work/work/paperclip-mcp-v2/paperclip-mcp-v2-${inst}/wrapper.sh"
  if [ -x "$wrapper" ]; then
    echo "OK: paperclip_${inst} wrapper 可执行"
  else
    echo "FAIL: paperclip_${inst} wrapper 不可执行或不存在: $wrapper"
  fi
done

echo "=== 自愈完成 ==="
```

### 验证

```bash
bash /media/ok2049/work/work/paperclip-mcp-v2/setup-mcp-config.sh
# 预期输出：全部 OK，无 FAIL
```

---

## 动作 4：Hermes session 保活（R2、R6、R11）

### 问题

`mcp_tool.py:2138` — parking 会 deregister tools。`turn_context.py:198` — `refresh_agent_mcp_tools` 有 gate。Session 重建后多实例 MCP 工具不自动重注。

### 方案（不修改 Hermes 源码，符合 R11）

Hermes 启动后，等待所有 MCP server 初始化完成，自动触发一次全量 `/reload-mcp --all`。

实现方式：
1. 写一个 Hermes startup hook 脚本，放在 beta profile 的 hooks 目录
2. 该脚本在 Hermes session 初始化完成后执行 `/reload-mcp --all`
3. 重载结果写入 agent.log

如果 Hermes 不支持 startup hook，备选方案：在 wrapper.sh 里加一个延迟命令，wrapper 初始化完成后向 Hermes 发送 reload 信号。

### 验证

```bash
# 重启 Hermes 后
grep "MCP: registered 246 tool(s) from 3 server(s)" \
  /home/ok2049/.hermes/profiles/beta/logs/agent.log | tail -1
# 预期：最后一次注册显示 3 server(s)，0 failed
```

---

## 动作 5：MCP 注册 delete_agent（R3、R7）

### 问题

`paperclip-mcp/tools/agents.py` 已有 `delete_agent` 函数实现，但未在 `register_tools` 中注册到 MCP 工具列表。操盘手删 agent 只能绕 REST API。

### 方案

在 `paperclip-mcp/tools/agents.py` 的 `register_tools` 函数中添加：

```python
mcp.tool()(delete_agent)
```

改在三个 v2 目录各自的源码副本中，不在 `server.json`（JSON 是打包产物，升级会覆盖）。改在 .py 文件可在 git 控制下恢复。

`delete_company` 评估：若 agents.py 或 companies.py 已有实现则一并注册；否则在需求文档中写明 REST 路径（`DELETE /api/companies/:id`）作为已知路径。

### 验证

MCP 工具列表含 `mcp__paperclip_a__delete_agent`（b/c 同理）。删除一个测试 agent 成功。

---

## 动作 6：环境清理（R8）

### 问题

- B 公司 8 个 agent（含 4 个重复，名字带 "2"）：`CEO 2`、`Lead Engineer 2`、`Code Reviewer 2`、`Release Engineer 2`
- 幽灵 A 公司 `5412501b-68b2-4617-ba50-b649c4c13197`：123 issue、48 agent，Phase 0 实验残留

### 方案

**清理 B 重复 agent**（通过 REST API）：
```bash
# 1. 列 B 的 agents
# 2. 删 name 含 " 2" 的 4 个重复 agent
# 3. 验证剩余 4 个唯一 agent
```

**清理幽灵 A 公司**（通过 REST API，因为 delete_company 暂未注册到 MCP）：
```bash
curl -X DELETE \
  -H "Authorization: Bearer pcp_board_..." \
  "http://127.0.0.1:3100/api/companies/5412501b-68b2-4617-ba50-b649c4c13197"
```

**A/B/C 三家公司保留**，不推倒重建。当前配置已验证通过，推倒重建无收益。

### 验证

```bash
# B agent 数 = 4（唯一 slug）
curl -s -H "Authorization: Bearer ..." \
  "http://127.0.0.1:3100/api/companies/7588c82e.../agents" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print(len(d if isinstance(d,list) else d.get('agents',[])))"
# 预期：4

# 公司列表无 5412501b
curl -s -H "Authorization: Bearer ..." \
  "http://127.0.0.1:3100/api/companies" | grep -c "5412501b"
# 预期：0
```

---

## 动作 7：paperclip-mcp 版本 pin 死（R10）

### 问题

三个 v2 目录的 `pyproject.toml` 未锁定 paperclip-mcp 版本。`uv run` 会静默拉最新版，MCP 工具名/参数可能变化。

### 方案

三个 `pyproject.toml` 中显式声明：
```toml
[project]
dependencies = [
    "paperclip-mcp==0.4.0",
]
```

然后生成 `uv.lock`：
```bash
for inst in a b c; do
  cd /media/ok2049/work/work/paperclip-mcp-v2/paperclip-mcp-v2-${inst}
  uv lock
done
```

### 验证

```bash
for inst in a b c; do
  cd /media/ok2049/work/work/paperclip-mcp-v2/paperclip-mcp-v2-${inst}
  uv run paperclip-mcp --version
done
# 预期：三实例均输出 0.4.0
```

---

## 动作 8：升级回归门禁（R12、R13）

### 问题

任何组件升级后，没有自动化手段验证 Phase 0 工具链是否完好。当前依赖人工记忆逐项检查。

### 方案

创建 `paperclip-company-v2/phase0-regression-check.sh`，固化 T1-T8：

```bash
#!/bin/bash
# phase0-regression-check.sh — GEO119 Phase 0 工具链回归检查
# 任何 hermes/paperclip/paperclip-mcp 升级后必跑

PASS=0; FAIL=0
check() {
  local label="$1"; shift
  if "$@"; then echo "  PASS: $label"; PASS=$((PASS+1))
  else echo "  FAIL: $label"; FAIL=$((FAIL+1)); fi
}

echo "=== T1: 三实例 agent.log 注册 ==="
check "T1" grep -q "registered 246 tool(s) from 3 server(s)" \
  $(ls -t ~/.hermes/profiles/beta/logs/agent.log* | head -1)

echo "=== T2: paperclip_a 无 env 格式错误 ==="
check "T2" ! grep -q "paperclip_a.*length 1; 2 is required" \
  ~/.hermes/profiles/beta/logs/agent.log

echo "=== T3: 三实例工具全部注入 ==="
check "T3" grep -q "mcp__paperclip_a__list_issues.*mcp__paperclip_b__list_issues.*mcp__paperclip_c__list_issues" \
  ~/.hermes/profiles/beta/logs/agent.log || \
  grep -q "registered.*from 3 server.*(0 failed)" \
  ~/.hermes/profiles/beta/logs/agent.log

echo "=== T4: 写操作隔离 ==="
# 调用 API 验证隔离（与 AC1 验证相同逻辑）
check "T4" python3 -c "
import json, urllib.request
API='http://127.0.0.1:3100/api'
KEY='pcp_board_e65a40681143c73cda97a250ed4d21c8eb48a43427f089ab'
CO={'A':'3d402864-4cb8-4334-b376-2670abfa05e1','B':'7588c82e-932c-4af7-9bae-01c6ce684573','C':'e6e64b85-2177-4e0c-af5c-6f52ad6f016b'}
def api(u,b=None):
    d=json.dumps(b).encode() if b else None
    r=urllib.request.Request(u,data=d,method='POST' if b else 'GET')
    r.add_header('Authorization',f'Bearer {KEY}');r.add_header('Content-Type','application/json')
    with urllib.request.urlopen(r,timeout=10) as resp: return json.loads(resp.read())
def titles(res):
    if isinstance(res,list): return [i.get('title','') for i in res]
    return [i.get('title','') for i in res.get('issues',res.get('data',[]))]
# Create unique test issue
import time
ts=str(int(time.time()))
for l,cid in CO.items():
    api(f'{API}/companies/{cid}/issues',{'title':f'REGRESSION-T4-{l}-{ts}'})
# Verify isolation
ok=True
for sl,scid in CO.items():
    st=titles(api(f'{API}/companies/{scid}/issues'))
    for tl in CO:
        if sl==tl: continue
        if any(f'REGRESSION-T4-{tl}-{ts}' in t for t in st):
            ok=False
sys.exit(0 if ok else 1)
" 2>/dev/null

echo "=== T5: 后端 1 行修复仍在 ==="
check "T5" grep -q "frontmatter.adapterType" \
  /home/ok2049/paperclip/server/src/services/company-portability.ts

echo "=== T6: 治理层交付物完好 ==="
skills=$(ls /media/ok2049/work/work/paperclip-company-v2/agency-agents-v2/agency-agents/skills/*/SKILL.md 2>/dev/null | wc -l)
injections=0
for a in ceo vp-engineering creative-director cmo vp-product vp-sales vp-operations game-dev-director chief-of-staff qa-director xr-director; do
  if grep -q "委派规则\|审批责任\|升级路径" /media/ok2049/work/work/paperclip-company-v2/agency-agents-v2/agency-agents/agents/$a/AGENTS.md 2>/dev/null; then
    injections=$((injections+1))
  fi
done
teams=$(grep -rl "delegate-with-tree" /media/ok2049/work/work/paperclip-company-v2/agency-agents-v2/agency-agents/teams/*/TEAM.md 2>/dev/null | wc -l)
check "T6" [ "$skills" -ge 4 ] && [ "$injections" -ge 11 ] && [ "$teams" -ge 10 ]

echo "=== T7: MCP 工具含 delete_agent ==="
check "T7" grep -q "delete_agent" /media/ok2049/work/work/paperclip-mcp-v2/paperclip-mcp-v2-a/src/paperclip_mcp/tools/agents.py

echo "=== T8: 环境干净 ==="
check "T8" python3 -c "
import json, urllib.request
API='http://127.0.0.1:3100/api'
KEY='pcp_board_e65a40681143c73cda97a250ed4d21c8eb48a43427f089ab'
# 检查公司数 ≤ 4（A-v1, A-v2, B, C）
req=urllib.request.Request(f'{API}/companies',headers={'Authorization':f'Bearer {KEY}'})
data=json.loads(urllib.request.urlopen(req,timeout=10).read())
cs=data if isinstance(data,list) else data.get('companies',[])
ghosts=[c.get('name') for c in cs if 'GEO119-Phase-B-v2' in c.get('name','') or 'GEO119-Phase-C-v2' in c.get('name','')]
sys.exit(0 if len(ghosts)==0 else 1)
" 2>/dev/null

echo "=== 结果: $PASS 通过, $FAIL 失败 ==="
[ "$FAIL" -eq 0 ] && echo "PHASE 0 TOOLCHAIN: HEALTHY" || echo "PHASE 0 TOOLCHAIN: DEGRADED"
```

### 验证

```bash
bash /media/ok2049/work/work/paperclip-company-v2/phase0-regression-check.sh
# 预期：8 通过, 0 失败, "PHASE 0 TOOLCHAIN: HEALTHY"
```

---

## Execution Order

```
动作 1 (patch 文件)
  └─→ 动作 2 (C 模板 adapter.type)
        ├─→ 动作 5 (delete_agent 注册)
        ├─→ 动作 7 (版本 pin)
        └─→ 动作 6 (环境清理)
              └─→ 动作 3 (config 自愈脚本)
                    └─→ 动作 4 (auto-reload 保活)
                          └─→ 动作 8 (回归门禁)
```

动作 3 和 4 最后做——先修好所有组件，最后让 config 自愈脚本把一切恢复到正确状态，再验证 auto-reload 生效。

---

## Constraints

- 所有变更必须在 git 控制下，或生成可重复应用的 patch 文件
- 不改 Hermes 源码（R11）
- 不改 paperclip upstream 工作树（R9）——用 patch 或独立 fork
- paperclip-mcp 版本 pin 死为 0.4.0（R10）
- 清理操作前先验证目标无交付物（不可逆操作确认）

## Acceptance (9 criteria)

| # | 验收标准 | 验证方式 |
|---|---|---|
| 1 | 三实例同时可用 | agent.log 显示 3 server(s), 0 failed |
| 2 | 写操作隔离零串扰 | 动作 8 的 T4 回归检查 |
| 3 | 重启 Hermes 后工具自动全注入 | 动作 8 的 T1/T3 回归检查 |
| 4 | MCP 含 delete_agent | 动作 8 的 T7 回归检查 |
| 5 | 环境干净无幽灵 | 动作 8 的 T8 回归检查 |
| 6 | 需求文档已补 R1-R4 | 文档存在且内容覆盖四项契约 |
| 7 | git pull upstream 后 403 修复仍在 | 动作 8 的 T5：grep 确认回退逻辑存在 |
| 8 | 三实例 paperclip-mcp 版本一致 | `uv run paperclip-mcp --version` 均输出 0.4.0 |
| 9 | 升级后 T1-T8 全绿 | `bash phase0-regression-check.sh` 输出 8 通过 0 失败 |

## Risks

| Risk | Mitigation |
|---|---|
| paperclip 大版本升级改 company-portability.ts 结构，patch 无法应用 | 动作 2 的模板防御层独立于后端，import 仍可成功 |
| paperclip-mcp 0.5.x 不再支持 delete_agent 注册语法 | delete_agent 是 MCP 标准工具注册，接口稳定；若变，动作 8 的 T7 检查会发现 |
| Hermes 不支持 startup hook | 备选：wrapper.sh 侧延迟发送 reload 信号；最坏情况手动 `/reload-mcp` |
| 幽灵 A 公司 123 issue 中有关键数据 | 删除前用 `list_issues` 检查 issue 内容，确认全部为 Phase 0 测试数据（`AC1-isolation-test-*` 等） |
