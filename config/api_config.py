import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== 国内API（优先） ====================

# ==================== 智谱GLM（Coding Plan 端点） ====================
# 所有 key 只能走 coding plan 端点：/api/coding/paas/v4
# 回退链：环境变量 → 硬编码备用 key
_ZHIPU_KEY_FALLBACKS = [
    "bfc33baabb0b49e98b1ff761114c73e1.TMP1ebbMVpquZ7fE",
    "7371dbde757a43d89d2364e302ee1446.nHp3f0Y61LbGKIim",
]
ZHIPU_GLM_API_KEY = (
    os.getenv("GLM_CODING_PLAN_API_KEY", "")
    or os.getenv("ZHIPU_GLM_API_KEY", "")
    or os.getenv("ZHIPU_CODING_API_KEY", "")
    or next((k for k in _ZHIPU_KEY_FALLBACKS if k), "")
)
ZHIPU_GLM_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"

# 智谱 GLM Coding Plan MCP 服务密钥（web-search-prime, web-reader, zread）
GLM_CODING_PLAN_API_KEY = os.getenv("GLM_CODING_PLAN_API_KEY", "")

# ==================== 阿里云百炼 ====================
# 仅使用 Token Plan key，不使用百炼直连 key
ALI_BAILIAN_API_KEY = (
    os.getenv("ALI_TOKEN_PLAN_API_KEY", "")
    or os.getenv("ALI_BAILIAN_API_KEY", "")
)
ALI_BAILIAN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 阿里 Token Plan（代码专用）
ALI_TOKEN_PLAN_API_KEY = os.getenv("ALI_TOKEN_PLAN_API_KEY", "")
ALI_TOKEN_PLAN_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"

# ==================== 国际API（需代理） ====================

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Claude API密钥
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# ==================== 工具API ====================

# AMiner开放平台API密钥
AMINER_API_KEY = os.getenv("AMINER_API_KEY", "")

# WebPilot WattPro API密钥
WATTPRO_API_KEY = os.getenv("WATTPRO_API_KEY", "")

# Serper API密钥
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")

# Tavily API密钥
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# ==================== Provider配置（配置驱动） ====================

PROVIDERS = {
    # ==================== 智谱 GLM（GLM_CODING_PLAN_API_KEY） ====================
    "zhipu_glm": {
        "api_key_env": "ZHIPU_GLM_API_KEY",
        "base_url": ZHIPU_GLM_BASE_URL,
        "models": {
            "glm_5_1": {
                "model_id": "glm-5.1",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
                "stream": True,
                "use_zai": True,
            },
            "glm_5": {
                "model_id": "glm-5",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
                "use_zai": True,
            },
            "glm_4_7": {
                "model_id": "glm-4.7",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
                "stream": True,
                "use_zai": True,
            },
            "glm_4_6v": {
                "model_id": "glm-4.6v",
                "type": "vision",
                "max_tokens": 8192,
                "temperature": 0.7,
                "use_zai": True,
            },
            "glm_4_5v": {
                "model_id": "glm-4.5v",
                "type": "vision",
                "max_tokens": 8192,
                "temperature": 0.7,
                "use_zai": True,
            },
        },
    },
    # ==================== 阿里云百炼（ALI_API_KEY） ====================
    "ali_bailian": {
        "api_key_env": "ALI_BAILIAN_API_KEY",
        "base_url": ALI_BAILIAN_BASE_URL,
        "models": {
            "qwen3_7_max": {
                "model_id": "qwen3.7-max",
                "type": "generation",
                "max_tokens": 16384,
                "temperature": 0.7,
            },
            "qwen3_6_plus": {
                "model_id": "qwen3.6-plus",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
        },
    },
    # ==================== 阿里 Token Plan（ALI_TOKEN_PLAN_API_KEY） ====================
    "ali_token_plan": {
        "api_key_env": "ALI_TOKEN_PLAN_API_KEY",
        "base_url": ALI_TOKEN_PLAN_BASE_URL,
        "models": {
            "tp_qwen3_7_max": {
                "model_id": "qwen3.7-max",
                "type": "generation",
                "max_tokens": 16384,
                "temperature": 0.7,
            },
            "tp_qwen3_6_plus": {
                "model_id": "qwen3.6-plus",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
            "tp_qwen3_6_flash": {
                "model_id": "qwen3.6-flash",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
            "tp_deepseek_v4_pro": {
                "model_id": "deepseek-v4-pro",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
            "tp_deepseek_v4_flash": {
                "model_id": "deepseek-v4-flash",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
        },
    },
    # ==================== 国际API（需代理） ====================
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "models": {
            "gpt_5_5": {
                "model_id": "gpt-5.5",
                "type": "generation",
                "max_tokens": 16384,
                "temperature": 0.7,
            },
            "gpt_5_4": {
                "model_id": "gpt-5.4",
                "type": "generation",
                "max_tokens": 16384,
                "temperature": 0.7,
            },
            "gpt_5_3": {
                "model_id": "gpt-5.3",
                "type": "generation",
                "max_tokens": 16384,
                "temperature": 0.7,
            },
        },
    },
    "anthropic": {
        "api_key_env": "CLAUDE_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "models": {
            "claude_opus_4_7": {
                "model_id": "claude-opus-4-7",
                "type": "generation",
                "max_tokens": 32768,
                "temperature": 1.0,
                "non_openai": True,
            },
            "claude_opus_4_6": {
                "model_id": "claude-opus-4-6",
                "type": "generation",
                "max_tokens": 32768,
                "temperature": 1.0,
                "non_openai": True,
            },
        },
    },
}

# ==================== 模型别名映射 ====================
# 将 project_config 中的模型别名映射到 PROVIDERS 中的具体模型

MODEL_ALIASES = {}
for provider_name, provider_config in PROVIDERS.items():
    for model_alias, model_config in provider_config["models"].items():
        MODEL_ALIASES[model_alias] = {
            "provider": provider_name,
            "model_id": model_config["model_id"],
            "type": model_config.get("type", "generation"),
            "max_tokens": model_config.get("max_tokens", 8192),
            "temperature": model_config.get("temperature", 0.7),
            "stream": model_config.get("stream", False),
            "non_openai": model_config.get("non_openai", False),
            "use_zai": model_config.get("use_zai", False),
        }
