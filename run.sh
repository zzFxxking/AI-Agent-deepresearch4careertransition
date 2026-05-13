#!/usr/bin/env bash
# AI 求职助手 - 一键运行脚本
# 用法: bash run.sh
#       bash run.sh "你的求职需求" --target-role "大模型应用开发工程师" --time-budget "3个月"
#
# 支持平台: Linux / macOS / Windows (Git Bash / WSL)

set -euo pipefail

# ==================== 颜色定义 ====================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ==================== 打印 Banner ====================
echo -e "${BLUE}============================================${NC}"
echo -e "${CYAN}   AI 求职助手 - Deep Research Agent${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ==================== 项目根目录 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ==================== 环境检查 ====================
echo -e "${YELLOW}[1/4] 检查运行环境...${NC}"

# Python 版本检查
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}[ERROR] 未找到 Python，请安装 Python 3.10+${NC}"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)
PYTHON_VERSION=$($PYTHON --version 2>&1 | grep -oP '\d+\.\d+')
echo -e "  Python: ${GREEN}$PYTHON_VERSION${NC} ($PYTHON)"

# .env 文件检查
if [ ! -f "deep_research/.env" ]; then
    echo -e "${YELLOW}[WARN] 未找到 deep_research/.env，尝试从 .env.example 创建...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example deep_research/.env
        echo -e "  ${YELLOW}已创建 deep_research/.env，请编辑填入真实 API Key 后重新运行。${NC}"
        echo -e "  ${YELLOW}编辑器打开 deep_research/.env 中...${NC}"
        exit 0
    else
        echo -e "${RED}[ERROR] 未找到 .env.example，请手动创建 deep_research/.env${NC}"
        exit 1
    fi
fi

# ==================== 依赖安装 ====================
echo -e "${YELLOW}[2/4] 检查依赖...${NC}"

if ! $PYTHON -c "import openai" 2>/dev/null; then
    echo -e "  正在安装依赖..."
    $PYTHON -m pip install -r requirements.txt -q
    echo -e "  依赖安装: ${GREEN}完成${NC}"
else
    echo -e "  依赖状态: ${GREEN}已就绪${NC}"
fi

# ==================== 数据目录 ====================
echo -e "${YELLOW}[3/4] 准备数据目录...${NC}"
mkdir -p research_output data
echo -e "  目录状态: ${GREEN}已就绪${NC}"

# ==================== 运行 ====================
echo -e "${YELLOW}[4/4] 启动 AI 求职助手...${NC}"
echo ""

if [ $# -eq 0 ]; then
    # 无参数：交互式示例
    echo -e "${CYAN}使用示例任务启动（可通过命令行参数自定义）：${NC}"
    echo ""
    $PYTHON -m deep_research \
        "我是数学专业研一学生，跨考计算机，会Python和PyTorch基础，想找大模型应用开发方向的暑期实习" \
        --target-role "大模型应用开发工程师" \
        --time-budget "3个月" \
        --company-tier "大厂" \
        --current-level "有Python和PyTorch基础，没做过完整项目" \
        --focus-areas "RAG,Agent框架,MCP协议" \
        --avoid-areas "前端开发"
else
    # 有参数：透传给 deep_research
    $PYTHON -m deep_research "$@"
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}   运行完成！报告已保存至 research_output/ ${NC}"
echo -e "${GREEN}============================================${NC}"
