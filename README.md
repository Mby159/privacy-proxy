# Privacy Proxy Server

OpenAI 兼容的隐私代理服务器，自动检测和脱敏用户输入中的敏感信息。

## 功能
- OpenAI 兼容 API（支持 `/v1/chat/completions`、`/v1/embeddings` 等端点）
- 集成 privacy-guard 进行敏感信息检测和脱敏
- 支持自定义隐私规则
- 审计日志
- 多种脱敏策略

## 安装
```bash
pip install -r requirements.txt
```

## 使用
```bash
# 启动服务器
python main.py --config config.json

# 测试隐私处理
curl -X POST http://localhost:8080/process \
  -H "Content-Type: application/json" \
  -d '{"text":"手机号13812345678"}'
```

## 配置
编辑 `config.json` 文件：
```json
{
  "proxy": {
    "host": "127.0.0.1",
    "port": 8080,
    "openai_base_url": "https://api.openai.com/v1",
    "openai_api_key": "your-api-key"
  },
  "privacy": {
    "enabled": true,
    "strategy": "placeholder"
  }
}
```

## 依赖
- privacy-guard (https://github.com/Mby159/privacy-guard)
- aiohttp
- pydantic
- python-dotenv

## 许可证
MIT