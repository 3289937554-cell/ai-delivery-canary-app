# AI Delivery Canary App

低风险 Python canary 应用，用于验证 AI Delivery Control Plane 的 S0-S10 全链路治理。

```bash
python3 src/aid_canary_app.py --smoke
python3 -m unittest discover -s tests -v
```
