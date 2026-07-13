# 决策记录

## D1 - 使用极小 Python CLI/HTTP-free canary 应用

原因：降低业务风险、无需 secrets、无需生产部署，可稳定覆盖 lint/typecheck/test/build/smoke/evidence/final-check。

## D2 - GitHub/CI/evidence 为真源

GUI 或本地缓存不作为商业级验收真源。
