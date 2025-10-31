#!/bin/bash

# 20250922 LIFUBING CHANGE FOR NEW RELEASE
# 报错处理：
# Waiting for cache lock: Could not get lock /var/lib/dpkg/lock-frontend. It is held by process 7261 (apt) 
# 普通用户使用：sudo kill -9 7261 && sudo rm /var/lib/dpkg/lock-frontend && sudo rm /var/lib/dpkg/lock && sudo dpkg --configure -a && sudo apt update
# 
# root用户使用： kill -9 7261 && rm /var/lib/dpkg/lock-frontend && rm /var/lib/dpkg/lock && dpkg --configure -a && apt update


set -euo pipefail
set -e

# ===== 配置参数 =====
REPO_URL="http://1.94.193.239/debrepo/agiros/ubuntu2204lts/2510"
AGIROS_URL="http://1.94.193.239/yumrepo/agiros/agirosdep/agirosdep-0.25.1-py3-none-any.whl"
KEYRING_PATH="/usr/share/keyrings/agiros.gpg"
SOURCE_LIST_PATH="/etc/apt/sources.list.d/agiros.list"
USER_ID="agiros-repo-signing-key <lihongyu@agiros.edu.cn>"
KEY_IDS=(
    "21B5FC18808A5E53B0DB8DC8A2180F6FC2FB0784"
    "3A6094468DDEB0B913B9A2CF2B46C87FAFB44C88"
    "AA976E6026F297DEC1ADB32D4A550D446E70D279"
    "395287465BD74F851ED9A59D5B466A1738412D34"
    "0268274C4CEE6FDF552C48F3C1225994AE797B5C"
)


# 彩色输出定义
COLOR_RED="\033[31m"
COLOR_GREEN="\033[32m"
COLOR_RESET="\033[0m"

SUDO=''
if [ "$(id -u)" -ne 0 ]; then
    SUDO='sudo'
fi
echo -e "${COLOR_GREEN}[AGIROS一键安装向导]${COLOR_RESET}"
$SUDO apt update

# 检查并安装 lsb-release（如果缺失）
if ! command -v lsb_release &> /dev/null; then
    echo "lsb_release 命令未找到，正在安装 lsb-release 包..."
    $SUDO apt install -y lsb-release
fi

# 获取Ubuntu的版本信息
UBUNTU_VERSION=$(lsb_release -sr)
UBUNTU_CODENAME=$(lsb_release -cs)
ARCH=$(dpkg --print-architecture)

# 统一使用 dpkg 架构检测
arch_dpkg=$(dpkg --print-architecture 2>/dev/null)
if [ $? -ne 0 ]; then
    # 如果 dpkg 命令失败，尝试使用 uname -m
    arch_dpkg=$(uname -m)
    if [ "$arch_dpkg" = "x86_64" ]; then
        arch_dpkg="amd64"
    elif [ "$arch_dpkg" = "aarch64" ]; then
        arch_dpkg="arm64"
    fi
fi

case "$arch_dpkg" in
    amd64) 
        echo "CPU架构 X86_64, Ubuntu版本: $UBUNTU_VERSION ($UBUNTU_CODENAME)"
        repo_arch="amd64"
        ;;
    arm64) 
        echo "CPU架构 ARM64, Ubuntu版本: $UBUNTU_VERSION ($UBUNTU_CODENAME)"
        repo_arch="arm64"
        ;;
    *)
        echo -e "${COLOR_RED}❌ 当前仅支持amd64/arm64,检测到不支持的架构: $arch_dpkg${COLOR_RESET}" >&2
        exit 1
        ;;
esac

if [[ "$UBUNTU_CODENAME" != "jammy" ]]; then
    echo -e "${COLOR_RED}💡 AGIROS 的 Ubuntu 正式发布版本为 22.04，与当前系统不对应 " >&2
fi

check_setup_bash() {
    local ros_distro_list=("melodic" "noetic" "foxy" "humble")
    local agiros_distro_list=("loong")
    local found_ros=0
    local found_agiros=0

    for distro in "${ros_distro_list[@]}"; do
        local setup_file="/opt/ros/${distro}/setup.bash"
        if [ -f "$setup_file" ]; then
            echo -e "${COLOR_RED}💡检测到 ros2 $distro, 脚本: $setup_file ${COLOR_RESET}"
            found_ros=1
        fi
    done

    for distro in "${agiros_distro_list[@]}"; do
        local setup_file="/opt/agiros/${distro}/setup.bash"
        if [ -f "$setup_file" ]; then
            echo -e "${COLOR_RED}💡检测到 agiros $distro, 脚本: $setup_file ${COLOR_RESET}"
            found_agiros=1
        fi
    done

    # 如果最终都没找到
    if [ $found_agiros -eq 0 ]; then
        echo -e "${COLOR_GREEN}💡当前系统未安装AGIROS ${COLOR_RESET}" >&2
    fi
}

check_setup_bash

# 确保直接从终端读取输入
if [ -t 0 ]; then
    # 标准输入是终端，直接读取
    echo "AGIROS菜单(v25.06)--------------------"
    echo "0. 先配置AGIROS环境,而后一步一步安装AGIROS"
    echo -e "${COLOR_GREEN}1. ${COLOR_RESET}安装基础包/base"
    echo "2. 安装桌面最小集/desktop,和桌面开发工具"
    echo "3. 安装桌面全集/desktop-full,和桌面开发工具"
    echo "4. 安装全集/full,和桌面开发工具（慎用）"
    echo "5. AGIROS环境配置到启动文件"
    echo "6. 清理AGIROS环境"
    echo "7. 退出 或 Ctrl-C"
    read -p "请输入数字 (0/1/2/3/4/5/6/7): " choice
else
    # 标准输入不是终端，尝试从 /dev/tty 读取
    echo "AGIROS菜单(v25.06)--------------------"
    echo "0. 先配置AGIROS环境,而后一步一步安装AGIROS"
    echo -e "${COLOR_GREEN}1. ${COLOR_RESET}安装基础包/base"
    echo "2. 安装桌面最小集/desktop,和桌面开发工具"
    echo "3. 安装桌面全集/desktop-full,和桌面开发工具"
    echo "4. 安装全集/full,和桌面开发工具（慎用）"
    echo "5. AGIROS环境配置到启动文件"
    echo "6. 清理AGIROS环境"
    echo "7. 退出 或 Ctrl-C"
    read -p "请输入数字 (0/1/2/3/4/5/6/7): " choice </dev/tty
fi

if [[ -z "$choice" ]]; then
    echo -e "${COLOR_RED}错误：未输入任何内容${COLOR_RESET}" >&2
    exit 1
fi
echo "用户输入了：$choice"

# 验证输入是否为0-4的数字
if ! [[ "$choice" =~ ^[0-7]$ ]]; then
    echo -e "${COLOR_RED}错误：无效的选择，请输入0-4之间的数字${COLOR_RESET}" >&2
    exit 1
fi


init() {

    # 检查当前时区是否已经正确设置
    CURRENT_TIMEZONE=$(readlink /etc/localtime 2>/dev/null || echo "")
    EXPECTED_TIMEZONE="/usr/share/zoneinfo/Asia/Shanghai"

    if [[ "$CURRENT_TIMEZONE" == "$EXPECTED_TIMEZONE" ]]; then
        echo "时区已正确设置为 Asia/Shanghai，跳过设置"
    else
        # 检查并安装 tzdata（如果缺失）
        if ! dpkg -l | grep -q tzdata; then
            echo "tzdata 包未找到，正在安装..."
            # 预先配置时区为 Asia/Shanghai，避免交互
            # 预先配置时区为 Asia/Shanghai，避免交互
            echo "tzdata tzdata/Areas select Asia" | $SUDO debconf-set-selections
            echo "tzdata tzdata/Zones/Asia select Shanghai" | $SUDO debconf-set-selections
            $SUDO env DEBIAN_FRONTEND=noninteractive apt install -y tzdata
        fi
    fi

    echo "安装系统依赖包..."
    # 修复：移除末尾的逗号
    $SUDO apt install -y \
        gnupg \
        curl \
        devscripts \
        python3-all \
        dh-python  # 这里移除了多余的逗号

    # 添加 GPG 密钥
    echo "添加仓库签名密钥..."
    if ! curl -sSL "${REPO_URL}/agiros.gpg" | $SUDO tee /usr/share/keyrings/agiros.gpg >/dev/null; then
        echo -e "${COLOR_RED}错误：密钥下载失败${COLOR_RESET}" >&2
        exit 1
    fi

    # 添加 APT 源
    echo "配置软件仓库源..."
    $SUDO tee /etc/apt/sources.list.d/agiros.list >/dev/null <<EOL
# AGiROS官方软件仓库
deb [arch=$repo_arch signed-by=/usr/share/keyrings/agiros.gpg] ${REPO_URL} jammy main
EOL

    # 更新缓存
    echo "更新软件包列表..."
    if ! $SUDO apt-get update; then
        echo -e "${COLOR_RED}更新软件包列表失败${COLOR_RESET}" >&2
        exit 1
    fi
}




# 配置环境变量
configure_environment_variable() {
    env_var_dir="/opt/agiros/loong"
    bashrc_path="$HOME/.bashrc"
    setup_bash="/opt/agiros/loong/setup.bash"

    if [ -f "$setup_bash" ]; then
        echo "找到 AGIROS 环境配置文件: $setup_bash"
    else
        echo -e "${COLOR_RED}❌ 错误：未找到 AGIROS setup.bash 文件，请确认是否已安装 AGiROS${COLOR_RESET}" >&2
        exit 1
    fi
    

    # 添加环境变量
    env_var_key="export PATH=$env_var_dir:\$PATH"
    if ! grep -qF "$env_var_key" "$bashrc_path"; then
        if ! echo -e "\n$env_var_key\n" >> "$bashrc_path"; then
            echo "写入环境变量失败"
            exit 1
        fi
        echo "✅ 环境变量已成功添加到 $bashrc_path"
    else
        echo "💡 环境变量已存在于 $bashrc_path 中"
    fi
    
    # 添加AGIROS Loong环境配置
    
    if ! grep -qF "source $setup_bash" "$bashrc_path"; then
        if ! echo "source $setup_bash" >> "$bashrc_path"; then
            echo "添加AGIROS Loong环境配置到 $bashrc_path 失败"
            exit 1
        fi
        echo "已将 source $setup_bash 添加到 $bashrc_path"
        # 在当前会话中加载配置

    else
        echo "source $setup_bash 已存在于 $bashrc_path 中"
    fi
    
    set +u  # 禁用nounset
    source /opt/agiros/loong/setup.bash
    set -u  # 重新启用nounset（如果需要）

    echo "已在当前会话中加载AGIROS Loong环境配置"
    #source $bashrc_path
    # 提示用户刷新环境
    #echo "💡 已执行 'source $bashrc_path' 使环境变量生效"
    
}

# ===== 清理缓存函数（新增）=====
clean_cache() {
    echo -e "\n\033[1;33m===== 清理系统缓存 =====\033[0m"
    
    # 清理APT缓存（三级清理机制）
    echo "1. 清理APT缓存...clean/atuoclean/autoremove"
    $SUDO apt-get clean
    $SUDO apt-get autoclean
    $SUDO apt-get autoremove -y

    echo "2. 修正APT可能的错误"
    $SUDO apt-get update -qq
    $SUDO apt --fix-broken install

    # 清理临时文件
    #echo "2. 清理临时文件.../tmp/* /var/tmp/*"
    #$SUDO rm -rf /tmp/*
    #$SUDO rm -rf /var/tmp/*
}

# ===== 删除现有密钥和配置 =====
cleanup_system() {
    echo -e "\n\033[1;33m===== 清理现有配置 =====\033[0m"
    
    # 删除指定密钥ID（原脚本2逻辑）
    if [[ -f "$KEYRING_PATH" ]]; then
        for key_id in "${KEY_IDS[@]}"; do
            echo "移除密钥: $key_id"
            gpg --batch --no-default-keyring --keyring "$KEYRING_PATH" \
                --delete-keys "$key_id" 2>/dev/null || true
        done
    fi

    # 删除用户ID关联的密钥（原脚本1逻辑）
    if [[ -f "$KEYRING_PATH" ]]; then
        echo "移除用户ID关联密钥: $USER_ID"
        gpg --batch --no-default-keyring --keyring "$KEYRING_PATH" \
            --delete-keys "$USER_ID" 2>/dev/null || true
    fi

    # 删除密钥环文件
    echo "移除密钥环文件 $KEYRING_PATH"
    $SUDO rm -f "$KEYRING_PATH"

    # 删除仓库配置
    echo "移除仓库配置文件 $SOURCE_LIST_PATH"
    $SUDO rm -f "$SOURCE_LIST_PATH"

    # 更新包列表
    echo "清理APT缓存"
    $SUDO apt-get update -qq
    $SUDO apt --fix-broken install

    # 调用缓存清理函数（新增）
    clean_cache

    echo -e "\n\033[1;32m✔ 所有密钥、仓库配置和系统缓存已成功移除\033[0m"
}
# 安装开发工具
install_tools() {
    echo "💡 安装开发工具和依赖..."
    $SUDO apt install -y \
        python3-colcon-common-extensions \
        python3-colcon-ros \
        python3-colcon-cmake \
        build-essential \
        python3-flake8  \
        python3-pytest-cov \
        python3-pip \
        python3-setuptools \
        libzbar-dev \
        ntpdate

        #agiros-loong-rosidl-default-generators \
        #agiros-loong-rosidl-default-runtime \
    # 时间同步
    $SUDO ntpdate ntp.ubuntu.com

    # 安装额外的Python工具
    echo "安装额外的Python工具..."
    # 检查pip版本并相应调整安装命令
    PIP_VERSION=$(pip3 --version | awk '{print $2}' | cut -d. -f1)

    if [ "$PIP_VERSION" -ge 23 ]; then
        # 新版本pip使用 --break-system-packages
        pip3 install -U -i https://pypi.tuna.tsinghua.edu.cn/simple \
            argcomplete \
            pytest-repeat \
            pytest-rerunfailures \
            --break-system-packages
    else
        # 旧版本pip不需要 --break-system-packages
        pip3 install -U -i https://pypi.tuna.tsinghua.edu.cn/simple \
            argcomplete \
            pytest-repeat \
            pytest-rerunfailures
    fi


    echo "配置并初始化agirosdep..."
    if [ ! -f "/etc/agiros/agirosdep/sources.list.d/20-default.list" ]; then
        pip install $AGIROS_URL

        # 初始化rosdep
        $SUDO agirosdep init || true

        # 更新rosdep
        echo "更新agirosdep..."
        agirosdep update
    fi

    # 使用方法（先进入工作空间）
    # agirosdep install -i --from-path src --rosdistro $ROS_DISTRO -y

    # 卸载rosdep
    # pip xxx
    # $SUDO rm -rf /etc/agiros/agirosdep
    # $SUDO rm -rf ~/.agiros/agirosdep

}

# 安装指定包的函数
install_tools_echo() {

    read -p "是否要安装开发工具:Colcon build,agirosdep等？(y/Y/yes/YES同意安装，其它放弃安装)" user_input </dev/tty

    # 将输入转换为小写进行比较
    user_input_lower=$(echo "$user_input" | tr '[:upper:]' '[:lower:]')

    if [[ "$user_input_lower" == "y" || "$user_input_lower" == "yes" ]]; then
        echo "开始安装开发工具..."
        install_tools
    else
        echo "跳过安装开发工具"
    fi
}

# 安装指定包的函数
install_apt() {
    local package_name=$1
    
    # 等待用户输入，确认是否安装指定包
    read -p "是否要安装 $package_name？(y/Y/yes/YES同意安装，其它跳过安装)" user_input </dev/tty

    # 将输入转换为小写进行比较
    user_input_lower=$(echo "$user_input" | tr '[:upper:]' '[:lower:]')

    if [[ "$user_input_lower" == "y" || "$user_input_lower" == "yes" ]]; then
        echo "开始安装 $package_name..."
        $SUDO apt install -y "$package_name"
        if [ $? -eq 0 ]; then
            echo "$package_name 安装成功"
        else
            echo "$package_name 安装失败"
            exit 1
        fi
    else
        echo "跳过安装 $package_name"
    fi
}

# 安装pip包的函数
install_pip() {
    local package_url=$1
    local package_name=$(basename "$package_url" | cut -d'-' -f1)
    
    # 等待用户输入，确认是否安装指定pip包
    read -p "是否要安装 $package_name？(y/Y/yes/YES同意安装，其它跳过安装)" user_input </dev/tty

    # 将输入转换为小写进行比较
    user_input_lower=$(echo "$user_input" | tr '[:upper:]' '[:lower:]')

    if [[ "$user_input_lower" == "y" || "$user_input_lower" == "yes" ]]; then
        # 检查是否已安装 python3-pip，如果没有则安装
        if ! command -v pip3 &> /dev/null; then
            echo "未检测到 pip3，开始安装 python3-pip..."
            yum install -y python3-pip
            if [ $? -ne 0 ]; then
                echo "python3-pip 安装失败"
                exit 1
            fi
            echo "python3-pip 安装完成"
        else
            echo "开始安装 pip 包: $package_name..."
        fi
        
        
        pip3 install "$package_url"
        if [ $? -eq 0 ]; then
            echo "pip 包 $package_name 安装成功"
        else
            echo "pip 包 $package_name 安装失败"
            exit 1
        fi
    else
        echo "跳过安装 pip 包 $package_name"
    fi
}

install_package() {
    local install_mode="$1"
    local package_name=""
    local local_install_tools=0
    
    case $install_mode in
        0) 
            init
            echo -e "${COLOR_GREEN}✅ 环境配置完成！可通过[sudo] apt install agiros-loong-<pkg>进行安装${COLOR_RESET}"
            install_apt "agiros-loong-ros-base"
            install_apt "agiros-loong-turtlesim"
            install_apt "agiros-loong-desktop"
            install_apt "agiros-loong-desktop-full"
            install_tools_echo
            exit 0
            ;;
        1) 
            init
            $SUDO dpkg --configure -a
            package_name="agiros-loong-ros-base"
            ;;
        2) 
            init
            $SUDO dpkg --configure -a
            package_name="agiros-loong-desktop"
            local_install_tools=1
            ;;
        3) 
            init
            $SUDO dpkg --configure -a
            package_name="agiros-loong-desktop-full"
            local_install_tools=1
            ;;
        4) 
            init
            $SUDO dpkg --configure -a
            package_name="agiros-loong-ros-base agiros-loong-desktop agiros-loong-desktop-full"
            local_install_tools=1
            ;;
        5) 
            configure_environment_variable
            exit 0
            ;;
        6) 
            cleanup_system
            exit 0
            ;;
        7) 
            echo "正常退出脚本"
            exit 0
            ;;
        *)
            echo "输入错误，请输入0-6"
            exit 1
            ;;
    esac
    
    echo "开始安装 $package_name ..."
    if ! $SUDO apt install -y $package_name; then
        echo "💡 安装失败，尝试修复依赖..."
        
        # 确保 aptitude 已安装
        if ! command -v aptitude >/dev/null; then
            $SUDO apt install -y aptitude
        fi
        
        if ! $SUDO aptitude install -y $package_name; then
            echo -e "${COLOR_RED}❌ 依赖修复失败，请手动处理${COLOR_RESET}" >&2
            exit 1
        fi
    fi
    if [ "$local_install_tools" -eq 1 ]; then
        install_tools
    fi
    #如果install_mode不是5，则配置环境变量

    configure_environment_variable

    $SUDO apt clean
    echo -e "${COLOR_GREEN}✅ $package_name 安装成功！${COLOR_RESET}"

    # 验证安装
    echo "验证AGIROS安装..."
    if command -v agiros &> /dev/null; then
        echo "✅ AGIROS已安装成功"
    else
        echo "agiros 命令未找到，可能需要重新启动终端或手动source环境变量"
        echo "请运行: source $bashrc_path"
    fi
}


install_package "$choice"