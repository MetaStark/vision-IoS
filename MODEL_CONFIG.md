# Vision-IoS LLM Model Configuration

## Current Model: Claude 3 Haiku

**Model:** `claude-3-haiku-20240307`

### Why Haiku?

- **Cost-optimized:** ~$0.25 per million input tokens (60x cheaper than Opus)
- **Fast:** Lowest latency of all Claude 3 models
- **Sufficient:** More than adequate for Vision-IoS agent tasks

### Available Models on Account

| Model | Status | Cost (per 1M input tokens) | Use Case |
|-------|--------|---------------------------|----------|
| claude-3-haiku-20240307 | ✅ Active | ~$0.25 | **RECOMMENDED** - Cost-effective for agents |
| claude-3-opus-20240229 | ⚠️ Deprecated (EOL: Jan 2026) | ~$15.00 | Complex reasoning (expensive) |
| claude-3-5-sonnet-* | ❌ Not available | N/A | Not accessible on current API key |

### Cost Savings Example

For 1 million tokens (typical daily usage for 5 agents):
- **Haiku:** $0.25
- **Opus:** $15.00
- **Savings:** $14.75 per million tokens (98% reduction)

### Where Model is Used

All Vision-IoS scripts use Haiku by default:
- `vision-IoS/test_api_key.py`
- `vision-IoS/validate_environment.py`
- `vision-IoS/agent_keys.py` (via get_llm_client_for_agent)
- Future agent implementations (LARS, FINN, STIG, LINE, VEGA)

### Upgrading Models

If you gain access to Claude 3.5 Sonnet in the future:
1. Test availability: `python vision-IoS/list_available_models.py`
2. Update model name in scripts to: `claude-3-5-sonnet-20241022`
3. Cost increase: ~10x more expensive than Haiku

### Reference

- Anthropic Pricing: https://www.anthropic.com/pricing
- Model Deprecations: https://docs.anthropic.com/en/docs/resources/model-deprecations
