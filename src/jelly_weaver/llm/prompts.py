"""Prompt templates for LLM-based media name parsing."""

SYSTEM_PROMPT = (
    "你是影视命名专家。用户给你一个 PT 下载的文件夹名，"
    "你需要识别出：媒体类型(movie/tv)、英文标准名、中文名、首播年份。\n"
    "严格返回 JSON，不要多余文字。\n\n"
    "输出格式：\n"
    '{"media_type":"movie或tv","title_en":"英文名","title_zh":"中文名","year":年份}\n\n'
    "示例：\n"
    '输入: "老友记.Friends.S01-S10.1080p.BluRay.x265-GROUP"\n'
    '输出: {"media_type":"tv","title_en":"Friends","title_zh":"老友记","year":1994}\n\n'
    '输入: "肖申克的救赎.The.Shawshank.Redemption.1994.BluRay.1080p"\n'
    '输出: {"media_type":"movie","title_en":"The Shawshank Redemption","title_zh":"肖申克的救赎","year":1994}'
)


def build_user_prompt(folder_name: str, hint: str | None = None) -> str:
    """Build the user message for LLM parsing.

    Args:
        folder_name: The raw PT download folder name.
        hint: Optional hint like "movie" or "tv" from the drop target.
    """
    msg = f'"{folder_name}"'
    if hint:
        msg += f"\n（提示：用户将其归类为 {hint}）"
    return msg
