"""AI 分析服务 - 使用 OpenAI 兼容 API 分析构建错误日志"""
import re
import json
import logging
import requests
from typing import Optional, Generator
from app.models import GlobalConfig

logger = logging.getLogger(__name__)

# 错误关键词模式，用于从海量日志中提取关键行
ERROR_PATTERNS = [
    r'\berror\b',
    r'\bfailed\b',
    r'\bfatal\b',
    r'\bundefined reference\b',
    r'\bno such file\b',
    r'\bcannot find\b',
    r'\bcommand not found\b',
    r'\bpermission denied\b',
    r'\bsegmentation fault\b',
    r'\bbus error\b',
    r'\bout of memory\b',
    r'\bkilled\b',
    r'\btimeout\b',
    r'\baborted\b',
    r'\bassertion\b',
    r'\bconflict\b',
    r'\bmissing\b',
    r'\binvalid\b',
    r'\bunresolved\b',
    r'\bexception\b',
    r'\btraceback\b',
    r'\bsyntax error\b',
    r'\bno module\b',
    r'\bimport error\b',
    r'\blink error\b',
    r'\bld returned\b',
    r'\bcollect2: error\b',
    r'\bmake\[\d+\]: \*\*\*',
    r'\bno rule to make target\b',
]

MAX_LOG_CHARS = 15000
CONTEXT_LINES = 2

SYSTEM_PROMPT = """你是一个资深 Debian/Deepin 软件包构建工程师。用户会提供一段构建错误日志，你需要帮助分析代码层面的问题。

重要区分：
- 如果错误是代码本身的问题（编译错误、语法错误、类型不匹配、缺少头文件、链接错误等），请详细分析：
  1. **错误原因**：简要指出最可能的根本原因（1-2句话）
  2. **关键错误**：列出日志中最重要的错误信息
  3. **解决方案**：给出具体的修复建议和操作步骤
  4. **涉及文件**：列出出现问题的文件或依赖包名

- 如果错误是构建环境/平台问题（pbuilder 内部错误、chroot 创建失败、apt 下载超时、网络波动、镜像源不可用、磁盘空间不足等），只需简单说明是平台/环境问题，建议重新触发构建即可，不需要深入分析。

判断标准：看错误是否出在源代码编译阶段。如果出在 configure/make/gcc/cmake 阶段 → 代码问题；如果出在 pbuilder/create-snapshot/apt-get update 阶段 → 平台问题。

请直接输出分析，不要寒暄。"""


class AIService:
    """AI 构建日志分析服务"""

    @classmethod
    def _filter_log(cls, log_text: str) -> str:
        """从完整日志中提取错误相关的关键行，大幅减少 token 消耗"""
        if not log_text:
            return ""

        lines = log_text.split('\n')
        if len(lines) <= 50:
            return log_text

        # 用 regex 匹配每一行
        combined = re.compile('|'.join(ERROR_PATTERNS), re.IGNORECASE)

        matched_indices = set()
        for i, line in enumerate(lines):
            if combined.search(line):
                matched_indices.add(i)

        if not matched_indices:
            # 没有匹配到任何错误关键词，返回最后 200 行（错误通常在末尾）
            return '\n'.join(lines[-200:])

        # 保留匹配行及其上下文
        keep_indices = set()
        for idx in matched_indices:
            start = max(0, idx - CONTEXT_LINES)
            end = min(len(lines), idx + CONTEXT_LINES + 1)
            keep_indices.update(range(start, end))

        # 如果两个保留块之间有空洞（≤5行），也保留以保持连贯
        sorted_indices = sorted(keep_indices)
        merged = set(sorted_indices)
        for i in range(1, len(sorted_indices)):
            gap = sorted_indices[i] - sorted_indices[i - 1]
            if 1 < gap <= 5:
                merged.update(range(sorted_indices[i - 1] + 1, sorted_indices[i]))

        result_lines = [lines[i] for i in sorted(merged)]
        result = '\n'.join(result_lines)

        # 硬截断
        if len(result) > MAX_LOG_CHARS:
            result = '...(truncated)...\n' + result[-(MAX_LOG_CHARS - 100):]

        logger.info(f"日志过滤: {len(log_text)} -> {len(result)} 字符 ({len(log_text.split(chr(10)))} -> {len(result.split(chr(10)))} 行)")
        return result

    @classmethod
    def analyze(cls, log_text: str, arch: str = "", project_name: str = "") -> Optional[str]:
        """分析构建日志，返回 AI 分析结果"""
        config = GlobalConfig.get_config()

        if not config.ai_api_url:
            logger.error("AI API 地址未配置")
            return None
        if not config.ai_api_key:
            logger.error("AI API Key 未配置")
            return None

        # 过滤日志节省 token
        filtered_log = cls._filter_log(log_text)

        # 构建用户消息
        context_parts = [f"架构: {arch}"] if arch else []
        if project_name:
            context_parts.append(f"项目: {project_name}")
        context = "，".join(context_parts)

        user_message = f"{context}\n\n构建错误日志如下：\n\n```\n{filtered_log}\n```"

        model = config.ai_model or "gpt-4o-mini"

        try:
            resp = requests.post(
                f"{config.ai_api_url.rstrip('/')}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
                timeout=120,
            )
            resp.raise_for_status()
            result = resp.json()

            if "choices" in result and len(result["choices"]) > 0:
                analysis = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                logger.info(f"AI 分析完成, tokens: prompt={usage.get('prompt_tokens')}, completion={usage.get('completion_tokens')}")
                return analysis
            else:
                logger.error(f"AI API 返回异常: {result}")
                return None

        except requests.Timeout:
            logger.error("AI API 请求超时")
            return None
        except Exception as e:
            logger.exception(f"AI 分析异常: {e}")
            return None

    @classmethod
    def analyze_stream(cls, log_text: str, arch: str = "", project_name: str = "",
                       system_prompt: str = None) -> Generator[str, None, None]:
        """流式分析，yield 每个 token"""
        config = GlobalConfig.get_config()

        if not config.ai_api_url:
            yield "错误: AI API 地址未配置"
            return
        if not config.ai_api_key:
            yield "错误: AI API Key 未配置"
            return

        prompt = system_prompt or SYSTEM_PROMPT

        if system_prompt is not None:
            # 自定义 prompt，跳过日志过滤，直接使用原始文本
            user_message = log_text
        else:
            # 默认构建日志分析模式
            log_text = cls._filter_log(log_text)
            context_parts = [f"架构: {arch}"] if arch else []
            if project_name:
                context_parts.append(f"项目: {project_name}")
            context = "，".join(context_parts)
            user_message = f"{context}\n\n构建错误日志如下：\n\n```\n{log_text}\n```"

        model = config.ai_model or "gpt-4o-mini"

        try:
            resp = requests.post(
                f"{config.ai_api_url.rstrip('/')}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                    "stream": True,
                },
                timeout=120,
                stream=True,
            )
            resp.raise_for_status()

            for line in resp.iter_lines(decode_unicode=True):
                if not line or line.startswith(":"):
                    continue
                if line == "data: [DONE]":
                    break
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, IndexError):
                        continue

        except requests.Timeout:
            yield "\n\n[AI 请求超时，请重试]"
        except Exception as e:
            logger.exception(f"AI 流式分析异常: {e}")
            yield f"\n\n[分析失败: {e}]"
