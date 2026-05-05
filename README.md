# axiom-battle-api

WuDao Axiom Battle REST API

## Deploy

```bash
railway login
railway init
railway up
```

Or connect GitHub repo for auto-deploy.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/battle` | POST | Run axiom battle |
| `/arena` | GET | Arena status |
| `/health` | GET | Health check |

## Example

```bash
curl -X POST https://axiom-battle-api.railway.app/battle \
  -H "Content-Type: application/json" \
  -d '{"axiom_a": "\u5叙事", "axiom_b": "\u81自由", "attack_type": "reverse"}'
```

(c) WuDao System
