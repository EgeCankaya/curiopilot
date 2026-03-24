"""Domain taxonomy for knowledge graph concept categorization."""

from __future__ import annotations

CATEGORIES: dict[str, list[str]] = {
    "AI Models": [
        "llm", "gpt", "claude", "gemini", "qwen", "mistral", "deepseek",
        "phi", "llama", "falcon", "transformer", "foundationmodel",
        "languagemodel", "chatmodel", "instructmodel",
    ],
    "Agentic Systems": [
        "agent", "multiagent", "autonomousagent", "agenticai", "aiagent",
        "tooluse", "planning", "workflow", "orchestration", "taskdelegation",
        "llmagent",
    ],
    "Training & Learning": [
        "rl", "rlhf", "icrl", "finetuning", "pretraining", "distillation",
        "training", "posttrain", "reward", "ppo", "dpo", "sft",
        "incontextlearning", "fewshot", "zeroshot",
    ],
    "Architecture & Methods": [
        "attention", "embedding", "rag", "vectorstore", "moe",
        "mixtureofexpert", "densemodel", "sparsemodel", "quantization",
        "context", "tokenefficiency", "kvcache",
    ],
    "Applications & Tools": [
        "codingassistant", "codegeneration", "aicodingagent", "chatbot",
        "search", "knowledgesharing", "stackoverflow", "ide", "plugin",
        "copilot",
    ],
    "Hardware & Infrastructure": [
        "gpu", "tpu", "cuda", "inference", "serving", "deployment",
        "llama.cpp", "ollama", "vllm", "triton",
    ],
    "Safety & Alignment": [
        "alignment", "safety", "ethics", "bias", "hallucination",
        "redteam", "jailbreak", "longtailattack", "robustness",
        "constitutionalaiai",
    ],
    "Research & Benchmarks": [
        "benchmark", "eval", "scalinglaw", "emergent", "intelligenceexplosion",
        "agi", "cognitivesociet", "paperreview", "arxiv",
    ],
}

CATEGORY_COLORS: dict[str, str] = {
    "AI Models":                "#0A84FF",
    "Agentic Systems":          "#30D158",
    "Training & Learning":      "#FF9F0A",
    "Architecture & Methods":   "#BF5AF2",
    "Applications & Tools":     "#FF375F",
    "Hardware & Infrastructure": "#64D2FF",
    "Safety & Alignment":       "#FF6961",
    "Research & Benchmarks":    "#FFD60A",
    "Uncategorized":            "#8E8E93",
}


def assign_category(concept_key: str) -> str:
    """Return the best-matching category for a normalized concept key."""
    for cat, keywords in CATEGORIES.items():
        if any(kw in concept_key for kw in keywords):
            return cat
    return "Uncategorized"
