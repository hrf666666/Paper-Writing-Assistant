import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== 国内API（优先） ====================

# ==================== 智谱GLM ====================
ZHIPU_GLM_API_KEY = os.getenv("ZHIPU_GLM_API_KEY", "")
ZHIPU_GLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# 智谱 Coding Plan（代码专用）
ZHIPU_CODING_API_KEY = os.getenv("ZHIPU_CODING_API_KEY", "")
ZHIPU_CODING_BASE_URL = "https://open.bigmodel.cn/api/coding/paas/v4"

# 智谱 GLM Coding Plan MCP 服务密钥（web-search-prime, web-reader, zread）
GLM_CODING_PLAN_API_KEY = os.getenv("GLM_CODING_PLAN_API_KEY", "")

# ==================== 阿里云百炼 ====================
ALI_BAILIAN_API_KEY = os.getenv("ALI_BAILIAN_API_KEY", "")
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
    "zhipu_glm": {
        "api_key_env": "ZHIPU_GLM_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": {
            "glm_5_1": {
                "model_id": "glm-5.1",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
            "glm_4_plus": {
                "model_id": "glm-4-plus",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
            "glm_4_flash": {
                "model_id": "glm-4-flash",
                "type": "light",
                "max_tokens": 4096,
                "temperature": 0.5,
            },
        },
    },
    # 智谱 Coding Plan（代码专用，吞吐量更高）
    "zhipu_coding": {
        "api_key_env": "ZHIPU_CODING_API_KEY",
        "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
        "models": {
            "glm_coding": {
                "model_id": "glm-4",
                "type": "coding",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
        },
    },
    "ali_bailian": {
        "api_key_env": "ALI_BAILIAN_API_KEY",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": {
            "qwen3_6_plus": {
                "model_id": "qwen3.6-plus",
                "type": "generation",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
            "qwq_32b": {
                "model_id": "qwq-32b",
                "type": "reasoning",
                "max_tokens": 8192,
                "stream": True,
            },
            "qwen_plus": {
                "model_id": "qwen-plus",
                "type": "light",
                "max_tokens": 4096,
                "temperature": 0.5,
            },
            "qwen_72b": {
                "model_id": "qwen-72b-instruct",
                "type": "light",
                "max_tokens": 4096,
                "temperature": 0.5,
            },
            "qwen_long": {
                "model_id": "qwen-long",
                "type": "generation",
                "max_tokens": 10000,
                "temperature": 0.7,
            },
        },
    },
    # 阿里 Token Plan（代码专用，吞吐量更高）
    "ali_token_plan": {
        "api_key_env": "ALI_TOKEN_PLAN_API_KEY",
        "base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "models": {
            "qwen_coding": {
                "model_id": "qwen-coder-plus",
                "type": "coding",
                "max_tokens": 8192,
                "temperature": 0.7,
            },
        },
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "models": {
            "o3_mini": {
                "model_id": "o3-mini",
                "type": "reasoning",
                "max_tokens": 8192,
            },
            "o1": {
                "model_id": "o1",
                "type": "reasoning",
                "max_tokens": 8192,
            },
        },
    },
    "anthropic": {
        "api_key_env": "CLAUDE_API_KEY",
        "base_url": "https://api.anthropic.com/v1",
        "models": {
            "claude_37": {
                "model_id": "claude-3-7-sonnet-20250219",
                "type": "generation",
                "max_tokens": 23333,
                "temperature": 1.0,
                "non_openai": True,  # 使用Anthropic原生API
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
        }
