#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from collections import defaultdict
from datetime import datetime

ROOT_DIR = "agiros_master_all_src3"

# 跳过的目录
SKIP_DIRS = {"debian", ".github", "doc"}
SKIP_DIR_PREFIX = (".git",)

# 跳过的文件名
SKIP_FILES = {"rules", "Dockfile", "Dockerfile"}
# 跳过的扩展名（不含 .txt，CMakeLists.txt 例外处理）
SKIP_EXTS = {".md", ".rst", ".urdf", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".bin", ".exe", ".class", ".jar", ".zip", ".tar", ".gz", ".7z"}


# 全局修改记录
modified_files = defaultdict(list)

# 日志文件
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
SUMMARY_LOG = f"replace_summary_{timestamp}.txt"

def log_summary(text: str):
    """写入汇总日志文件"""
    with open(SUMMARY_LOG, "a", encoding="utf-8") as f:
        f.write(text + "\n")

def process_file(file_path: str, REPLACE_MAP) -> bool:
    """处理单个文件，进行批量替换并打印详细信息"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"⚠️ 无法读取文件 {file_path}: {e}")
        return False

    changed = False
    out_lines = []
    for idx, line in enumerate(lines, start=1):
        new_line = line
        i=0
        for old, new, count in REPLACE_MAP:
            if old in new_line:
                before = new_line
                new_line = new_line.replace(old, new)
                if new_line != before:
                    REPLACE_MAP[i][2] += 1  # 计数
                    msg = f"[rule][{file_path}:{idx}] '{old}' → '{new}'"
                    print(msg)
                    log_summary(msg)
            i+=1
        if new_line != line:
            changed = True
            msg = f"[replace][{file_path}:{idx}] {line.strip()}  -->  {new_line.strip()}"
            print(msg)
            log_summary(msg)
        out_lines.append(new_line)

    if changed:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(out_lines)
            # 记录修改的文件
            rel_path = os.path.relpath(file_path, ROOT_DIR)
            pkg = rel_path.split(os.sep)[0]  # 包名 = 顶层目录
            modified_files[pkg].append(rel_path)
        except Exception as e:
            print(f"⚠️ 写入文件 {file_path} 出错: {e}")
            return False
    return changed

def change_ros2agiros_tag(root_dir: str, from_str:str, to_str:str, logger=None) -> None:

    # 替换规则
    REPLACE_MAP = [
        ["/opt/ros/", "/opt/agiros/", 0],
        ["humble", "loong", 0],
        ["Humble", "Loong", 0],
        ["HUMBLE", "LOONG", 0],
        ["ros-humble", "agiros-loong", 0],
        ["ros2 action", "agiros action", 0],
        ["ros2 bag", "agiros bag", 0],
        ["ros2 component", "agiros component", 0],
        ["ros2 control", "agiros control", 0],
        ["ros2 daemon", "agiros daemon", 0],
        ["ros2 doctor", "agiros doctor", 0],
        ["ros2 interface", "agiros interface", 0],
        ["ros2 launch", "agiros launch", 0],
        ["ros2 lifecycle", "agiros ifecycle", 0],
        ["ros2 multicast", "agiros multicast", 0],
        ["ros2 node", "agiros node", 0],
        ["ros2 param", "agiros param", 0],
        ["ros2 pkg", "agiros pkg", 0],
        ["ros2 security", "agiros security", 0],
        ["ros2 service", "agiros service", 0],
        ["ros2 topic", "agiros topic", 0],
        ["ros2 wtf", "agiros wtf", 0],
        ["ros2 run", "agiros run", 0],
        ["ros-{", "agiros-{", 0],
        ["ros-$", "agiros-$", 0],
        ["\"ros-\"", "\"agiros-\"", 0],
        ["'ros-'", "'agiros-'", 0],
        ["ros-$ENV{ROS_DISTRO}", "agiros-$ENV{ROS_DISTRO}", 0],
        ["ros2)", "agiros)", 0],
        ["ros2 = ros2cli.cli:main", "agiros = ros2cli.cli:main", 0],
    ]


    package_pattern = re.compile(r'ros2cli-\d+\.\d+\.\d+')
    """递归遍历目录并处理文件"""
    if not os.path.exists(root_dir) or not os.path.isdir(root_dir):
        print(f"❌ 目录不存在: {root_dir}")
        return
    
    if logger is None:
        import logging
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        logger = logging

    processed, modified = 0, 0

    for root, dirs, files in os.walk(root_dir):
        if '.github' in dirs:
            dirs.remove('.github')
        # 过滤目录
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(SKIP_DIR_PREFIX)]

        for file in files:
            if file in SKIP_FILES:
                continue
            _, ext = os.path.splitext(file)

            # 特殊处理：只允许 CMakeLists.txt，其他 .txt 文件过滤
            if ext.lower() == ".txt" and file != "CMakeLists.txt":
                continue
            if ext.lower() in SKIP_EXTS:
                continue

            file_path = os.path.join(root, file)
            processed += 1
            if process_file(file_path, REPLACE_MAP):
                modified += 1

        # 处理特定包文件夹下的文件
        if package_pattern.fullmatch(os.path.basename(root)):
            # 处理 completion 子目录下的 ros2-argcomplete.bash 文件
            completion_dir = os.path.join(root, 'completion')
            if os.path.exists(completion_dir) and os.path.isdir(completion_dir):
                bash_file = os.path.join(completion_dir, 'ros2-argcomplete.bash')
                if os.path.exists(bash_file):
                    replace_in_file(bash_file, 'ros2)', 'agiros)')

            # 处理 ros2cli 子目录下的 cli.py 文件
            ros2cli_dir = os.path.join(root, 'ros2cli')
            if os.path.exists(ros2cli_dir) and os.path.isdir(ros2cli_dir):
                cli_file = os.path.join(ros2cli_dir, 'cli.py')
                if os.path.exists(cli_file):
                    replace_in_file(cli_file, 'ros2', 'agiros')

            # 处理 setup.py 文件
            setup_file = os.path.join(root, 'setup.py')
            if os.path.exists(setup_file):
                replace_in_file(setup_file, 'ros2 = ros2cli.cli:main', 'agiros = ros2cli.cli:main')

    summary_header = f"处理ros标记，总共处理了 {processed} 个文件，修改了 {modified} 个文件"
    logger.info(summary_header)
    # 构造对齐的规则统计
    if REPLACE_MAP:
        max_old = max(len(old) for old, _, _ in REPLACE_MAP)
        max_new = max(len(new) for _, new, _ in REPLACE_MAP)
        header = f"{'原始'.ljust(max_old)}  ->  {'替换后'.ljust(max_new)}  : 次数"
        sep = "-" * len(header)
        lines = [header, sep]
        for old, new, count in REPLACE_MAP:
            lines.append(f"{old.ljust(max_old)}  ->  {new.ljust(max_new)}  : {count}")
        summary_body = "\n".join(lines)
    else:
        summary_body = "无替换规则。"
    logger.info(summary_body)


def replace_in_file(file_path, old_str, new_str):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        if isinstance(old_str, str):
            new_content = content.replace(old_str, new_str)
        else:
            new_content = old_str.sub(new_str, content)
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(new_content)
            print(f"已在文件 {file_path} 中完成替换")
    except Exception:
        pass
