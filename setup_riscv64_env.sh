#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] 拉取 qemu-user-static (用于注册 binfmt)..."
docker pull multiarch/qemu-user-static:latest

echo "[2/3] 注册 binfmt（需要 --privileged，便于运行 riscv64 可执行文件）..."
docker run --rm --privileged multiarch/qemu-user-static:latest --reset -p yes

echo "[3/3] 拉取 riscv64/ubuntu:24.04 基础镜像..."
docker pull riscv64/ubuntu:24.04

echo "[DONE] 环境已准备好，可直接用 riscv64/ubuntu:24.04 创建容器。"
