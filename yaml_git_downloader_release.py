import os
import subprocess
import requests
import yaml
from tqdm import tqdm
import datetime

# ---------------- 全局配置 ----------------
TARGET_DIR = os.environ.get("AGIROS_RELEASE_TARGET_DIR", "ros2_release_dir")
LOG_FILE = os.path.join(TARGET_DIR, "download_log.txt")
GIT_CLONE_TIMEOUT = int(os.environ.get("AGIROS_GIT_CLONE_TIMEOUT", "600"))

# ANSI 颜色定义
class Color:
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    RESET = "\033[0m"


def log_message(message: str, color: str = Color.RESET):
    os.makedirs(TARGET_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(f"{color}{formatted}{Color.RESET}")  # 终端彩色输出
    with open(LOG_FILE, "a") as f:
        f.write(formatted + "\n")


def safe_git_clone_or_resume(repo_url, repo_path, branch_or_tag=None) -> bool:
    """
    克隆仓库，如果已存在则尝试 git fetch 断点续传。
    如果提供 branch_tag，则在 clone 时使用该分支（或 tag），
    已存在仓库时会 fetch 并 reset 到 origin/<branch_or_tag>。
    返回 True 表示成功，False 表示失败。
    """
    log_message(f">>>>>>>> 开始克隆{repo_url} ,TAG {branch_or_tag}。", Color.YELLOW)
    if os.path.exists(repo_path):
        return True
        if os.path.isdir(os.path.join(repo_path, ".git")):
            
            try:
                # 如果指定了 branch_tag，针对该分支 fetch 并 reset 到 origin/branch_or_tag
                if branch_or_tag:
                    log_message(f"[Skip] {repo_path} 已存在，尝试更新到branch_tag: {branch_or_tag}。", Color.YELLOW)
                    subprocess.run(
                        ["git", "-C", repo_path, "fetch", "origin", branch_or_tag],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    subprocess.run(
                        ["git", "-C", repo_path, "reset", "--hard", f"origin/{branch_or_tag}"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    log_message(f"[Skip] {repo_path} 已存在，跳过下载。", Color.YELLOW)
                    subprocess.run(
                        ["git", "-C", repo_path, "fetch", "--all"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    # 获取默认分支名
                    result = subprocess.run(
                        ["git", "-C", repo_path, "symbolic-ref", "refs/remotes/origin/HEAD"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                    default_branch = result.stdout.strip().split("/")[-1]
                    subprocess.run(
                        ["git", "-C", repo_path, "reset", "--hard", f"origin/{default_branch}"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                return True
            except subprocess.CalledProcessError:
                log_message(f"[Error] {repo_path} fetch/reset 失败。", Color.RED)
                return False
        else:
            log_message(
                f"[Info] {repo_path} 已存在且缺少 .git 目录，判定为手动准备的包，跳过 git 操作。",
                Color.BLUE,
            )
            return True
    else:
        try:
            if branch_or_tag:
                clone_cmd = ["git", "clone", "--branch", branch_or_tag, "--single-branch", repo_url, repo_path]
            else:
                clone_cmd = ["git", "clone", repo_url, repo_path]

            subprocess.run(
                clone_cmd,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=GIT_CLONE_TIMEOUT,
            )
            log_message(f"[OK] 成功克隆 {repo_url} → {repo_path} {'('+branch_or_tag+')' if branch_or_tag else ''}", Color.GREEN)
            return True
        except subprocess.TimeoutExpired:
            log_message(
                f"[Warning] 克隆超时：{repo_url} → {repo_path}，已运行超过 {GIT_CLONE_TIMEOUT}s。",
                Color.YELLOW,
            )
            return False
        except subprocess.CalledProcessError:
            log_message(f"[Error] 克隆失败：{repo_url} → {repo_path}", Color.RED)
            if os.path.exists(repo_path):
                # 删除克隆失败的残留目录
                subprocess.run(["rm", "-rf", repo_path])
            return False

##yaml_url = https://github.com/ros/rosdistro/blob/jazzy/2025-10-14/jazzy/distribution.yaml
#从yaml_url中提取jazzy/2025-10-14/jazzy/distribution.yaml，并转换为jazzy_2025-10-14_jazzy-distribution.yaml
#如果jazzy_2025-10-14_jazzy-distribution.yaml已存在，则跳过下载
def download_repos_from_distribution_yaml(yaml_url: str, target_dir: str = TARGET_DIR, code_or_tracks: str = "code"):
    os.makedirs(target_dir, exist_ok=True)
    

    # 将GitHub blob URL转换为raw URL以获取原始文件内容
    if "github.com" in yaml_url and "/blob/" in yaml_url:
        yaml_url = yaml_url.replace("/blob/", "/raw/")
    log_message(f"[Start] 从 {yaml_url} 下载 distribution.yaml", Color.BLUE)

    #如果distribution.yaml文件存在，则读取文件内容到yaml_content, 否则 下载 YAML 文件，并读取内容到yaml_content
    yaml_filename = yaml_url.split("/")[-3] + "_" + yaml_url.split("/")[-2] + "_" + yaml_url.split("/")[-1].replace("/", "-")
    yaml_filepath = os.path.join(target_dir, yaml_filename)
    if os.path.exists(yaml_filepath):
        log_message(f"[Info] {yaml_filepath} 已存在，跳过下载。", Color.YELLOW)
        
    else:
        try:
            #从yaml_url下载文件，并保存到本地的yaml_filepath文件中
            response = requests.get(yaml_url)
            response.raise_for_status()
            #yaml_content = response.text
            with open(yaml_filepath, "w") as f:
                f.write(response.text)
            log_message(f"[OK] 成功下载 YAML 文件到 {yaml_filepath}", Color.GREEN)

        except Exception as e:
            log_message(f"[Error] 下载 YAML 失败: {e}", Color.RED)
            raise
    download_by_distribution_yaml(yaml_filepath, target_dir, code_or_tracks)


def download_by_distribution_yaml(distribution_yaml_filepath: str, target_dir: str = TARGET_DIR, code_or_tracks: str = "code"):
    with open(distribution_yaml_filepath, "r") as f:
        yaml_content = f.read()
    data = yaml.safe_load(yaml_content)

    repos = []
    if "repositories" in data:
        for repo_name, repo_info in data["repositories"].items():
            if "release" in repo_info and "url" in repo_info["release"]:
                #repo_info["release"]的内容为{'tags': {'release': 'release/jazzy/{package}/{version}'}, 'url': 'https://github.com/ros2-gbp/zmqpp_vendor-release.git', 'version': '0.0.2-4'}
                #提取release中的tags作为branch_tag
                branch_or_tag = None

                #------------------------处理tags------------------------
                if "tags" in repo_info["release"] and "release" in repo_info["release"]["tags"]:
                    tags = repo_info["release"]["tags"]["release"]   
                    #tags的值是'release/jazzy/{package}/{version}，其中{package}和{version}需要替换为实际的包名和版本号
                else:    
                    log_message(f"[Error] {repo_name}的tags内容为空.", Color.RED)
                    continue

                branch_or_tag = tags

                if code_or_tracks == "code":
                    if "version" in repo_info["release"]:
                        branch_or_tag = branch_or_tag.replace("{version}", repo_info["release"]["version"])
                    else:
                        branch_or_tag = branch_or_tag.replace("/{version}", "")

                    if "packages" in repo_info["release"] :
                        #packages的值是一个列表，包含该release对应的包名，比如：['smacc2', 'smacc2_msgs']
                        packages = repo_info["release"]["packages"]
                        #轮询packages列表，针对每个包名，替换tags中的{package}为实际的包名
                        for package in packages:
                            branch_tag_pkg = branch_or_tag.replace("{package}", package)
                            repos.append((repo_name, package, repo_info["release"]["url"], branch_tag_pkg))
                    else:
                        #比如：https://github.com/ros2-gbp/acado_vendor-release.git的release没有packages字段
                        branch_tag_pkg = branch_or_tag.replace("{package}", repo_name)
                        repos.append((repo_name, repo_name, repo_info["release"]["url"], branch_tag_pkg))
                
                if code_or_tracks == "tracks":
                    #branch_or_tag = branch_or_tag.replace("/{version}", "")
                    branch_tag_pkg = None
                    repos.append((repo_name, repo_name, repo_info["release"]["url"], branch_tag_pkg))


    total = len(repos)
    log_message(f"[Info] Found {total} repositories to download.", Color.BLUE)
    #print(f"[Info] Found {total} release repositories to download.\n")

    failed_repos = []

    with tqdm(total=total, desc="Downloading repos", unit="repo") as pbar:
        for idx, (repo_name, package_name, repo_url, branch_or_tag) in enumerate(repos, start=1):

            repo_path = os.path.join(target_dir, package_name)

            ok = safe_git_clone_or_resume(repo_url, repo_path, branch_or_tag)

            if ok:
                
                #检查repo_path目录下是否有tracks.yaml文件，如果没有，则认为是分支选错了，提示用户检查
                tracks_yaml_path = os.path.join(repo_path, "tracks.yaml")
                if code_or_tracks == "tracks":
                    if not os.path.exists(tracks_yaml_path):
                        log_message(f"[Error] {repo_name}/{package_name}  {'TAG '+branch_or_tag if branch_or_tag else ''}未找到 tracks.yaml 文件。", Color.RED)
                        #删除repo_path目录
                        subprocess.run(["rm", "-rf", repo_path])
                        #branch_or_tag为空时，尝试用master分支克隆;为master时，则用None克隆 
                        if branch_or_tag is None:
                            branch_or_tag = "master"
                        elif branch_or_tag == "master":
                            branch_or_tag = None
                        else:
                            branch_or_tag = "master"
                        ok = safe_git_clone_or_resume(repo_url, repo_path, branch_or_tag)
                        if ok:
                            if not os.path.exists(tracks_yaml_path):
                                subprocess.run(["rm", "-rf", repo_path])
                                log_message(f"[Error] {repo_name}/{package_name}  {'TAG '+branch_or_tag if branch_or_tag else ''}未找到 tracks.yaml 文件。", Color.RED)
                                tqdm.write(f"[{idx}/{total}] {Color.GREEN}[OK]{Color.RESET} {repo_name}/{package_name} TAG None (重新克隆失败)")
                            else:
                                tqdm.write(f"[{idx}/{total}] {Color.GREEN}[OK]{Color.RESET} {repo_name}/{package_name} TAG master")
                        else:
                            tqdm.write(f"[{idx}/{total}] {Color.RED}[Error]{Color.RESET} {repo_name}/{package_name} (重新克隆失败)")
                            failed_repos.append((f"{repo_name}/{package_name}", repo_url))
                    else:
                        tqdm.write(f"[{idx}/{total}] {Color.GREEN}[OK]{Color.RESET} {repo_name}/{package_name} TAG None")
                else:
                    tqdm.write(f"[{idx}/{total}] {Color.GREEN}[OK]{Color.RESET} {repo_name}/{package_name} {'TAG '+branch_or_tag if branch_or_tag else ''}")

            else:
                subprocess.run(["rm", "-rf", repo_path])
                tqdm.write(f"[{idx}/{total}] {Color.RED}[Error]{Color.RESET} {repo_name}/{package_name} from {repo_url}")
                failed_repos.append((f"{repo_name}/{package_name}", repo_url))

            pbar.update(1)

    if failed_repos:
        failed_file = os.path.join(target_dir, "failed_repos.txt")
        with open(failed_file, "w") as f:
            for name, url in failed_repos:
                f.write(f"{name} {url}\n")
        log_message(f"[Warning] {len(failed_repos)} failed repos written to {failed_file}", Color.YELLOW)
        print(f"\n{Color.YELLOW}[Warning]{Color.RESET} {len(failed_repos)} repositories failed. See {failed_file}")

    log_message(f"[Done] Finished downloading {total} repositories.", Color.GREEN)
    print(f"\n{Color.GREEN}[Done]{Color.RESET} Finished downloading {total} repositories. "
          f"Success: {total - len(failed_repos)}, Failed: {len(failed_repos)}")


if __name__ == "__main__":
    yaml_url = "http://1.94.193.239/yumrepo/agiros/agirosdep/loong/distribution.yaml"
    download_repos_from_distribution_yaml(yaml_url, TARGET_DIR)
