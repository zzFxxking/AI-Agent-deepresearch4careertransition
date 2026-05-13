import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = open(os.path.join(os.path.dirname(__file__), 'test_run.log'), 'w', encoding='utf-8')
sys.stderr = sys.stdout

try:
    from deep_research import DeepResearchAgent
    print("[INFO] 模块导入成功")

    agent = DeepResearchAgent(verbose=True, save_output=True)
    print("[INFO] Agent 初始化成功")

    report = agent.research("Python编程语言的历史", max_workers=2)
    print("[INFO] 研究完成")
    print("=" * 60)
    print(report[:2000])
    print("=" * 60)
except Exception as e:
    print(f"[ERROR] {e}")
    traceback.print_exc()
