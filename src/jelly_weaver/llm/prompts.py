"""Prompt templates for LLM-based media directory renaming.

Single entry point: the full directory tree is passed in one call.
The LLM sees root name, all children, siblings, and sample files —
enough context to correctly name every level (Show, Season, Movie, Collection).
"""

from __future__ import annotations

from jelly_weaver.core.tree import TreeNode


RENAME_SYSTEM_PROMPT = (
    "你是 Jellyfin 媒体库命名专家。用户给你一棵完整的目录树，"
    "你需要为每个目录（包括根目录）提供符合 Jellyfin 刮削规范的建议名称，并判断媒体类型。\n\n"
    "根据目录结构判断类型，分如下情况：\n\n"
    "根目录下有多个子目录\n"
    "  - 若子目录内含剧集文件（文件名含 S01E01 等）→ media_type=tv，根目录 = Show Name (Year)，子目录 = Season 01 / Season 02 …\n"
    "  - 若子目录各自含少量视频文件（每部独立电影）→ media_type=movie，根目录 = Title Collection，子目录各自 = Movie Title (Year)\n"
    "  - 若只有一个子目录且含剧集文件 → media_type=tv，根目录 = Show Name (Year)，子目录 = Season 01\n\n"
    "根目录直接包含视频文件（无子目录，或子目录不含媒体）\n"
    "  - 若文件名含 S01E01 等剧集格式 → media_type=tv，根目录 = Show Name (Year)\n"
    "  - 若文件是单部电影 → media_type=movie，根目录 = Movie Title (Year)\n\n"
    "通用规则：\n"
    "- 年份格式：(Year)，如 (1994)、(2010)\n"
    "- 季编号两位数字：Season 01、Season 02\n"
    "- 根目录（id=0，标有「根目录」）永远不能命名为 Season XX\n"
    "- 若目录已符合规范，保持原名即可\n\n"
    "严格返回 JSON 对象，不要多余文字：\n"
    '{"media_type":"tv|movie","renames":[{"id":0,"name":"建议名"},{"id":1,"name":"建议名"},...]}' "\n\n"
    "示例 — 多季剧集\n"
    "输入:\n"
    '[0] "老友记.Friends.S01-S10.1080p"/（根目录）  (0 文件)\n'
    '  [1] "老友记S01.Friends.1994.1080p"/  (24 文件)  样本: Friends.S01E01.mkv\n'
    '  [2] "老友记S02.Friends.1995.1080p"/  (24 文件)  样本: Friends.S02E01.mkv\n'
    '  [3] "老友记S03.Friends.1996.1080p"/  (24 文件)  样本: Friends.S03E01.mkv\n'
    '输出: {"media_type":"tv","renames":[{"id":0,"name":"Friends (1994)"},{"id":1,"name":"Season 01"},{"id":2,"name":"Season 02"},{"id":3,"name":"Season 03"}]}' "\n\n"
    "示例 — 只有一个季子目录\n"
    "输入:\n"
    '[0] "老友记.Friends.1080p"/（根目录）  (0 文件)\n'
    '  [1] "老友记S01.Friends.1994.1080p"/  (24 文件)  样本: Friends.S01E01.mkv\n'
    '输出: {"media_type":"tv","renames":[{"id":0,"name":"Friends (1994)"},{"id":1,"name":"Season 01"}]}' "\n\n"
    "示例 — 根目录直接含剧集文件（只下了一季，无子目录）\n"
    "输入:\n"
    '[0] "老友记S01.Friends.1994.1080p"/（根目录）  (24 文件)  样本: Friends.S01E01.mkv\n'
    '输出: {"media_type":"tv","renames":[{"id":0,"name":"Friends (1994)"}]}' "\n\n"
    "示例 — 电影合集\n"
    "输入:\n"
    '[0] "碟中谍.Mission.Impossible.1-6.1080p"/（根目录）  (0 文件)\n'
    '  [1] "碟中谍.Mission.Impossible.1996.1080p"/  (3 文件)  样本: Mission.Impossible.1996.mkv\n'
    '  [2] "碟中谍2.Mission.Impossible.II.2000.1080p"/  (3 文件)  样本: Mission.Impossible.II.2000.mkv\n'
    '输出: {"media_type":"movie","renames":[{"id":0,"name":"Mission Impossible Collection"},{"id":1,"name":"Mission Impossible (1996)"},{"id":2,"name":"Mission Impossible II (2000)"}]}' "\n\n"
    "示例 — 单部电影\n"
    "输入:\n"
    '[0] "盗梦空间.Inception.2010.1080p"/（根目录）  (2 文件)  样本: Inception.2010.mkv\n'
    '输出: {"media_type":"movie","renames":[{"id":0,"name":"Inception (2010)"}]}'
    "如果不符合上述情况，请你根据 Jellyfin 的刮削原则为我命名，严谨的提供每一个名字。"
)


def build_rename_prompt(root: TreeNode) -> tuple[str, list[str]]:
    """Render the full directory tree as text for the LLM.

    Returns:
        (prompt_text, keys) where keys[i] is TreeNode.key for the directory
        assigned id=i. The LLM returns {"media_type":..., "renames":[{"id":i,"name":...}]},
        and keys maps those ids back to node keys for cache storage.
    """
    lines: list[str] = []
    keys: list[str] = []

    def visit(node: TreeNode, indent: int) -> None:
        if not node.is_dir:
            return
        node_id = len(keys)
        keys.append(node.key)
        prefix = "  " * indent
        tag = "（根目录）" if indent == 0 else ""
        sample = f"  样本: {', '.join(node.sample_files[:3])}" if node.sample_files else ""
        lines.append(
            f"{prefix}[{node_id}] \"{node.name}\"/{tag}  ({node.file_count} 文件){sample}"
        )
        for child in node.children:
            if child.is_dir:
                visit(child, indent + 1)

    visit(root, 0)
    return "\n".join(lines), keys
