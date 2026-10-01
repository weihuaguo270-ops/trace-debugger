# 贡献指南（Contributing）

Agent 轨迹分析**小工具**。欢迎补规则、修解析或加测试。

## 本地验证（与 CI 同款）

```bash
pip install -e ".[test]"

pytest tests/ -q                               # 全量
pytest tests/test_failure_golden.py -q         # 规则回归（golden 32）
pytest tests/test_failure_fp_and_gate.py -q    # 假阳性回归 + 门禁导出

# CI 的规则门禁步骤（与 .github/workflows/test.yml 同款）：同数据 compare 不应触发 hold，
# 且每条 finding 必须能指到回归锁（缺锁即 exit 1）
tdebug scan fixtures/failure_golden 5 --json-out /tmp/gate.json
tdebug scan fixtures/failure_golden 5 \
  --compare /tmp/gate.json \
  --fail-on hold \
  --findings-out /tmp/gate_findings.json \
  --require-verification \
  --project-root .

# CI 也守卫夹具可复现：改 spec 后必须能原样重生成
python scripts/generate_failure_golden.py
git diff --exit-code -- fixtures/failure_golden
```

## 受限 runner / 容器 / 沙箱

失败日志默认写入平台用户数据目录，测试同样依赖系统临时目录；在只允许写工作区的受限环境里，
把这两处都指到仓库内可写路径（参见 [docs/PORTABILITY.md](docs/PORTABILITY.md)）：

```bash
export TDEBUG_DATA_DIR="$PWD/.pytest-tmp/data"
export TMPDIR="$PWD/.pytest-tmp/tmp"      # Windows: set TMP=... 与 TEMP=...
pytest tests/ -q
```

若沙箱**还**禁止访问以 `0o700` 创建的目录（`tempfile.mkdtemp` 与 pytest `tmp_path` 的默认模式），
相关用例会在 setup/teardown 阶段报 `PermissionError: [WinError 5]`。这是环境限制、不是项目缺陷，
请在 CI 或普通 shell 复跑确认，不要为此改动测试或降低断言。

