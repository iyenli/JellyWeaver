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


# --- Structure analysis prompts ---

STRUCTURE_SYSTEM_PROMPT = (
    "你是媒体库目录组织专家。用户给你一个 PT 下载文件夹的名称和内部目录结构，\n"
    "你需要判断它的结构类型，并生成一个链接计划：将源子目录映射到 Jellyfin 标准的目标子目录。\n\n"
    "结构类型 (structure_type)：\n"
    "- tv_single_season: 单季剧集，所有文件属于同一季\n"
    "- tv_multi_season: 多季剧集，每个子目录对应一季\n"
    "- movie_single: 单部电影\n"
    "- movie_collection: 电影合集，每个子目录是一部独立电影\n"
    "- unknown: 无法判断\n\n"
    "映射规则：\n"
    "- TV 剧集：目标子目录必须是 Season XX 格式（两位数字，如 Season 01）\n"
    "- 电影合集：每部电影需要提供 title_en 和 year，目标子目录留空\n"
    "- 单部电影：source_subdir 和 target_subdir 都留空字符串\n"
    "- source_subdir 为空字符串表示根目录的文件\n\n"
    "严格返回 JSON，不要多余文字。\n"
    "输出格式：\n"
    '{"structure_type":"类型","items":[{"source_subdir":"源子目录","target_subdir":"目标子目录","title_en":"英文名(仅合集)","year":年份(仅合集)}]}\n\n'
    "示例1 — 多季剧集，子目录名非标准：\n"
    "文件夹: \"老友记.Friends.S01-S10.1080p.BluRay\"\n"
    "目录树:\n"
    "  老友记S01.Friends.1994.1080p/ (24 files) sample: Friends.S01E01.mkv\n"
    "  老友记S02.Friends.1995.1080p/ (24 files) sample: Friends.S02E01.mkv\n"
    '输出: {"structure_type":"tv_multi_season","items":['
    '{"source_subdir":"老友记S01.Friends.1994.1080p","target_subdir":"Season 01","title_en":"","year":0},'
    '{"source_subdir":"老友记S02.Friends.1995.1080p","target_subdir":"Season 02","title_en":"","year":0}]}\n\n'
    "示例2 — 电影合集：\n"
    "文件夹: \"碟中谍.Mission.Impossible.1-6.1080p.BluRay\"\n"
    "目录树:\n"
    "  碟中谍.Mission.Impossible.1996.1080p/ (3 files) sample: Mission.Impossible.1996.mkv\n"
    "  碟中谍2.Mission.Impossible.II.2000.1080p/ (3 files) sample: Mission.Impossible.II.2000.mkv\n"
    '输出: {"structure_type":"movie_collection","items":['
    '{"source_subdir":"碟中谍.Mission.Impossible.1996.1080p","target_subdir":"","title_en":"Mission Impossible","year":1996},'
    '{"source_subdir":"碟中谍2.Mission.Impossible.II.2000.1080p","target_subdir":"","title_en":"Mission Impossible II","year":2000}]}\n\n'
    "示例3 — 单季剧集，平铺文件：\n"
    "文件夹: \"绝命毒师.Breaking.Bad.S01.1080p\"\n"
    "目录树:\n"
    "  (root files) sample: Breaking.Bad.S01E01.mkv, Breaking.Bad.S01E02.mkv\n"
    '输出: {"structure_type":"tv_single_season","items":['
    '{"source_subdir":"","target_subdir":"Season 01","title_en":"","year":0}]}\n\n'
    "示例4 — 单部电影：\n"
    "文件夹: \"肖申克的救赎.The.Shawshank.Redemption.1994.BluRay\"\n"
    "目录树:\n"
    "  (root files) sample: The.Shawshank.Redemption.1994.mkv\n"
    '输出: {"structure_type":"movie_single","items":['
    '{"source_subdir":"","target_subdir":"","title_en":"","year":0}]}'
)


def build_structure_prompt(folder_name: str, tree: dict) -> str:
    """Build user message for structure analysis.

    Args:
        folder_name: The raw PT download folder name.
        tree: Output from list_entry_tree().
    """
    lines = [f'文件夹: "{folder_name}"', "目录树:"]

    root_files = tree.get("root_files", [])
    if root_files:
        lines.append(f"  (root files) sample: {', '.join(root_files)}")

    for d in tree.get("subdirs", []):
        name = d["name"]
        count = d.get("file_count", 0)
        samples = d.get("sample_files", [])
        line = f"  {name}/ ({count} files)"
        if samples:
            line += f" sample: {', '.join(samples)}"
        lines.append(line)

    if not root_files and not tree.get("subdirs"):
        lines.append("  (empty)")

    return "\n".join(lines)
