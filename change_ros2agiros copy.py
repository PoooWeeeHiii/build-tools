#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from collections import defaultdict
from datetime import datetime

"""
批量内容替换脚本

目录/文件过滤：
- 跳过目录：debian/、.github/、所有以 .git 开头的目录（如 .git、.gitlab 等）
- 跳过文件名：rules、Dockerfile、Dockfile
- 跳过扩展名（不区分大小写）：.md、.txt、.rst、.urdf、.svg

替换规则：
  1) ros-jazzy-  →  agiros-loong-
  2) ros-jazzy   →  agiros-loong
  3) /opt/ros/   →  /opt/agiros/
  4) jazzy/Jazzy/JAZZY  →  loong/Loong/LOONG
  5) 独立的 ros：不进行任何替换（包括 ros-xxx、.ros/.ros.、ros:: 等全部保持原样）
  6) ros:jazzy → agiros:loong
     ROS_REPO: [ros] → ROS_REPO: [agiros]
  7) ros-[ROS_DISTRO] → agiros-[ROS_DISTRO]
  8) ros-%s → agiros-%s
  10) ros-${ROS2_VERSION} → agiros-${ROS2_VERSION}
  11) ros-$ROS_DISTRO → agiros-$ROS_DISTRO

额外保护image：
- image: ros:jazzy  —— 只保护其中的 "ros:jazzy" 片段，不改行内其他内容
- turtles.append("jazzy.png") —— 只保护其中的 "jazzy.png" 片段，不改行内其他内容

其它逻辑保持不变：保留对 ros2cli 套件目录的专门替换。
"""

import os
import re

# 关键字临时保护列表：防止这些特定关键字中的"ros"被误替换
PROTECT_WORDS = ["CMakeLists.txt", "Findros.cmake"]

# 预编译正则表达式模式，用于高效匹配

URL_PAT         = re.compile(r"https?://\S+")      # 匹配URL模式



# 目录和文件过滤规则
SKIP_DIRS_EXACT = {"debian", ".github"}                    # 精确匹配跳过的目录名
SKIP_FILE_NAMES = {"rules", "Dockerfile", "Dockfile"}      # 精确匹配跳过的文件名
SKIP_FILE_EXTS  = {".md", ".txt", ".rst", ".urdf", ".svg"} # 跳过指定扩展名的文件（统一转小写比较）


def protect_urls(line: str):
    """用占位符保护行内的URL，返回替换后的行和原始URL列表"""
    urls = []
    def _store(m: re.Match) -> str:
        urls.append(m.group(0))  # 保存原始URL
        return f"[[[URL_{len(urls)-1}]]]"  # 返回占位符
    return URL_PAT.sub(_store, line), urls  # 替换所有URL为占位符


def unprotect_urls(line: str, urls: list) -> str:
    """恢复被保护的URL：将占位符替换回原始URL"""
    for i, url in enumerate(urls):
        line = line.replace(f"[[[URL_{i}]]]", url)
    return line


def protect_keywords(line: str) -> str:
    """用占位符保护特定关键字中的ros，防止被误替换"""
    for word in PROTECT_WORDS:
        line = re.sub(r"\b" + re.escape(word) + r"\b",
                      lambda m: m.group(0).replace("ros", "[[[ROS]]]]"),  # 将ros替换为占位符
                      line)
    return line


def unprotect_keywords(line: str) -> str:
    """恢复关键字中被保护的ros：将占位符替换回原始ros"""
    for word in PROTECT_WORDS:
        safe_word = word.replace("ros", "[[[ROS]]]]")  # 生成保护后的关键字
        line = line.replace(safe_word, word)  # 恢复原始关键字
    return line


def safe_replace(line: str, from_str:str, to_str:str) -> str:
    """执行安全替换的主逻辑，按照预定义的替换规则处理文本行"""

    #准备数据---------------------
    ROSJAZZY_DASH   = re.compile(r"ros-jazzy-")  # 匹配带连字符的ros-jazzy-
    ROSJAZZY        = re.compile(r"ros-jazzy")   # 匹配ros-jazzy（不带连字符）
    J_LOWER         = re.compile(r"jazzy")             # 匹配小写jazzy
    J_TITLE         = re.compile(r"Jazzy")             # 匹配首字母大写Jazzy
    J_UPPER         = re.compile(r"JAZZY")             # 匹配全大写JAZZY
    # 仅保护片段的模式（不跳过整行）
    IMAGE_ROS_JAZZY_PAT  = re.compile(r"(^|\s)image\s*:\s*ros:jazzy\b", re.IGNORECASE)  # 匹配image: ros:jazzy
    TURTLE_JAZZY_PNG_PAT = re.compile(r"turtles\s*\.\s*append\(\s*['\"]jazzy\.png['\"]\s*\)")  # 匹配turtles.append("jazzy.png")
    IMG_ROS_JAZZY_TOKEN    = "[[[HOLD_TOKEN_1]]]"     # 临时占位符，用于保护ros:jazzy片段
    TURTLE_JAZZY_PNG_TOKEN = "[[[HOLD_TOKEN_2]]]"     # 临时占位符，用于保护jazzy.png片段


    # URL保护：先将所有URL替换为占位符
    line, urls = protect_urls(line)
    # 关键字保护：保护特定关键字中的ros
    line = protect_keywords(line)

    # 片段保护（只锁定特定片段，不跳过整行）
    # 保护image: ros:jazzy里的"ros:jazzy"
    def _hold_image_ros_jazzy(m: re.Match) -> str:
        # 仅替换匹配中的ros:jazzy，不动前面的image:与空白
        return m.group(0).replace("ros:jazzy", IMG_ROS_JAZZY_TOKEN)
    line = IMAGE_ROS_JAZZY_PAT.sub(_hold_image_ros_jazzy, line)

    # 保护turtles.append("jazzy.png")里的"jazzy.png"
    line = TURTLE_JAZZY_PNG_PAT.sub(
        lambda m: m.group(0).replace("jazzy.png", TURTLE_JAZZY_PNG_TOKEN),
        line
    )



    # 执行核心替换规则
    # 1) ros-jazzy（先带连字符，再不带）
    line = ROSJAZZY_DASH.sub("agiros-loong-", line)
    line = ROSJAZZY.sub("agiros-loong", line)

    # 3+4) 路径与发行名替换
    line = line.replace("/opt/ros/", "/opt/agiros/")
    line = J_UPPER.sub("LOONG", line)   # 替换全大写JAZZY
    line = J_TITLE.sub("Loong", line)   # 替换首字母大写Jazzy
    line = J_LOWER.sub("loong", line)   # 替换小写jazzy

    # 6–11) 结构化键/模板替换（先于独立ros的处理，以免被误伤）
    line = re.sub(r"ros:jazzy\b", "agiros:loong", line)  # 替换ros:jazzy
    line = re.sub(r"(ROS_REPO:\s*\[)ros(\])", r"\1agiros\2", line)  # 替换ROS_REPO字段
    line = line.replace("ros-[ROS_DISTRO]", "agiros-[ROS_DISTRO]")  # 替换模板变量
    line = line.replace("ros-%s", "agiros-%s")  # 替换格式化字符串
    line = line.replace("ros-${ROS2_VERSION}", "agiros-${ROS2_VERSION}")  # 替换环境变量格式
    line = line.replace("ros-$ROS_DISTRO", "agiros-$ROS_DISTRO")  # 替换shell变量格式

    # 5) 独立的ros：不进行任何替换（ros-、.ros/.ros.、ros::以及其它独立ros全部保持原样）

    # 恢复被保护的片段
    line = line.replace(IMG_ROS_JAZZY_TOKEN, "ros:jazzy")
    line = line.replace(TURTLE_JAZZY_PNG_TOKEN, "jazzy.png")

    # 恢复关键字和URL
    line = unprotect_keywords(line)
    line = unprotect_urls(line, urls)
    return line


def process_text_file(file_path: str, from_str:str, to_str:str) -> bool:
    """按行应用替换，只有文件内容有变化时才写回文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()  # 读取文件所有行
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {e}")
        return False

    changed = False  # 标记文件是否有变化
    out_lines = []   # 存储处理后的行
    for ln in lines:
        new_ln = safe_replace(ln, from_str, to_str)  # 对每行执行安全替换
        if new_ln != ln:
            changed = True  # 如果行内容有变化，标记为已更改
        out_lines.append(new_ln)

    if changed:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(out_lines)  # 将处理后的内容写回文件
            print(f"已在文件 {file_path} 中完成替换")
        except Exception as e:
            print(f"写回文件 {file_path} 时出错: {e}")
            return False
    else:
        print(f"文件 {file_path} 无变化")

    return changed


def change_ros2agiros_tag(root_dir: str, from_str:str, to_str:str, logger=None) -> None:
    """遍历目录，按过滤规则跳过指定目录/文件，然后进行内容替换"""
    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
        print(f"目录 {root_dir} 不存在。")
        return

    # 用于匹配ros2cli套件目录的模式
    package_pattern = re.compile(r"ros-jazzy-ros2cli-\d+\.\d+\.\d+")

    if logger is None:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        logger = logging

    processed_files = 0  # 已处理文件计数
    modified_files = 0   # 已修改文件计数

    # 遍历目录树
    for root, dirs, files in os.walk(root_dir):
        # 目录过滤：阻止os.walk进入需要跳过的目录
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS_EXACT  # 跳过指定目录
                   and not d.startswith(".git")]  # 跳过所有.git开头的目录

        # 文件过滤 + 替换
        for file in files:
            # 1) 跳过以.git开头的文件
            if file.startswith(".git"):
                continue
            # 2) 精确文件名跳过
            if file in SKIP_FILE_NAMES:
                continue
            # 3) 扩展名跳过（不区分大小写）
            _, ext = os.path.splitext(file)
            if ext.lower() in SKIP_FILE_EXTS:
                continue

            file_path = os.path.join(root, file)
            processed_files += 1
            if process_text_file(file_path, from_str, to_str):
                modified_files += 1

        # ros2cli套件目录的专门处理
        if package_pattern.fullmatch(os.path.basename(root)):
            # 处理completion目录下的bash补全文件
            completion_dir = os.path.join(root, "completion")
            if os.path.isdir(completion_dir):
                bash_file = os.path.join(completion_dir, "ros2-argcomplete.bash")
                if os.path.exists(bash_file):
                    process_text_file(bash_file, from_str, to_str)

            # 处理ros2cli目录下的cli.py文件
            ros2cli_dir = os.path.join(root, "ros2cli")
            if os.path.isdir(ros2cli_dir):
                cli_file = os.path.join(ros2cli_dir, "cli.py")
                if os.path.exists(cli_file):
                    process_text_file(cli_file, from_str, to_str)

            # 处理setup.py文件
            setup_file = os.path.join(root, "setup.py")
            if os.path.exists(setup_file):
                process_text_file(setup_file, from_str, to_str)

    print(f"\n总共处理了 {processed_files} 个文件，修改了 {modified_files} 个文件")


if __name__ == "__main__":
    orig_dir = "3replaced"  # 指定要处理的根目录
    change_ros2agiros_tag(orig_dir)   # 开始处理目录