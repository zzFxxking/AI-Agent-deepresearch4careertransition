"""
最小可行闭环测试脚本
使用 spec.md 中的示例输入验证完整链路
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout = open(os.path.join(os.path.dirname(__file__), 'test_mvp.log'), 'w', encoding='utf-8')
sys.stderr = sys.stdout

try:
    from deep_research import DeepResearchAgent
    print("[INFO] 模块导入成功")

    agent = DeepResearchAgent(verbose=True, save_output=True)
    print("[INFO] Agent 初始化成功")

    # spec.md 中的示例输入
    result = agent.research(
        "我是数学专业研一学生，跨考计算机，会Python和PyTorch基础，想找大模型应用开发方向的暑期实习，有3个月准备时间",
        target_role="大模型应用开发工程师",
        time_budget="3个月",
        company_tier="大厂",
        current_level="有Python和PyTorch基础，没做过完整项目",
        focus_areas=["RAG", "Agent框架", "MCP协议"],
        avoid_areas=["前端开发", "嵌入式"],
        max_workers=4,
    )

    print("[INFO] 研究完成")
    print("=" * 60)
    print("[主报告摘要]")
    print(result.markdown[:2000])
    print("=" * 60)
    print("[八股面试报告摘要]")
    print(result.markdown_interview[:2000] if result.markdown_interview else "(空)")
    print("=" * 60)
    print("[项目推荐报告摘要]")
    print(result.markdown_projects[:2000] if result.markdown_projects else "(空)")
    print("=" * 60)
    print("[JSON 结构化输出]")
    import json
    print(json.dumps(result.json_data, ensure_ascii=False, indent=2)[:2000])
    print("=" * 60)
    print("[元数据]")
    print(result.metadata)

except Exception as e:
    print(f"[ERROR] {e}")
    traceback.print_exc()
