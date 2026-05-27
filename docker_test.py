#!/usr/bin/env python3
"""
Docker 环境测试脚本
用于验证 API 配置和基本功能
"""

import os
import sys


def check_environment():
    """检查环境变量配置"""
    print("🔍 检查环境配置...")
    print("-" * 50)

    required_vars = {
        "GLM_API_KEY": os.getenv("GLM_API_KEY", ""),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY", ""),
    }

    optional_vars = {
        "GLM_OCR_URL": os.getenv("GLM_OCR_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
        "DEEPSEEK_URL": os.getenv("DEEPSEEK_URL", "https://api.deepseek.com/chat/completions"),
        "HTTP_TIMEOUT_SEC": os.getenv("HTTP_TIMEOUT_SEC", "30"),
        "QT_QPA_PLATFORM": os.getenv("QT_QPA_PLATFORM", "not set"),
        "DISPLAY": os.getenv("DISPLAY", "not set"),
    }

    all_ok = True

    print("\n📋 必需环境变量：")
    for name, value in required_vars.items():
        if value:
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  ✅ {name}: {masked}")
        else:
            print(f"  ❌ {name}: 未设置")
            all_ok = False

    print("\n⚙️  可选环境变量：")
    for name, value in optional_vars.items():
        print(f"  📌 {name}: {value}")

    print("\n" + "-" * 50)
    if all_ok:
        print("✅ 环境配置完整")
    else:
        print("⚠️  请设置必要的环境变量")
    print()

    return all_ok


def check_python_packages():
    """检查 Python 依赖包"""
    print("📦 检查 Python 依赖...")
    print("-" * 50)

    required_packages = [
        "dotenv",
        "httpx",
        "mss",
        "numpy",
        "cv2",
        "PyQt6",
        "keyboard",
    ]

    all_ok = True
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} - 未安装")
            all_ok = False

    print("\n" + "-" * 50)
    if all_ok:
        print("✅ 所有依赖包已安装")
    else:
        print("❌ 缺少依赖包，运行: pip install -r requirements.txt")
    print()

    return all_ok


async def test_api_client():
    """测试 API 客户端功能"""
    print("🧪 测试 API 客户端...")
    print("-" * 50)

    try:
        from api_client import OWColorFluentApiClient

        print("  ✅ api_client 模块导入成功")

        # 测试模拟数据
        mock_ocr_results = [
            {
                "text": "HEAL ME",
                "color_tag": {
                    "label": "Enemy",
                    "hex_color": "#FF4C4C"
                }
            },
            {
                "text": "C9",
                "color_tag": {
                    "label": "Friendly",
                    "hex_color": "#4CBFFF"
                }
            },
            {
                "text": "谢谢",
                "color_tag": None
            }
        ]

        async with OWColorFluentApiClient() as client:
            print("  ✅ OWColorFluentApiClient 初始化成功")

            # 测试翻译（实际调用 API）
            print("\n  🔄 正在测试翻译 API...")
            trans_results = await client.translate_ocr_results(mock_ocr_results)

            print(f"\n  ✅ 收到 {len(trans_results)} 条翻译结果：")
            for i, result in enumerate(trans_results[:3], 1):
                print(f"\n  {i}. 原文: {result.source_text}")
                print(f"     译文: {result.translated}")
                print(f"     标签: {result.color_tag.label if result.color_tag else 'None'}")

            print("\n" + "-" * 50)
            print("✅ API 测试完成")
            return True

    except Exception as e:
        print(f"\n  ❌ API 测试失败: {e}")
        print("\n" + "-" * 50)
        return False


async def main():
    """主测试流程"""
    print("\n" + "=" * 50)
    print("🐳 OW-Light-Translator Docker 测试")
    print("=" * 50 + "\n")

    # 1. 检查环境
    env_ok = check_environment()

    # 2. 检查 Python 包
    pkg_ok = check_python_packages()

    # 3. 测试 API
    if env_ok and pkg_ok:
        api_ok = await test_api_client()
    else:
        print("⏭️  跳过 API 测试（环境或依赖不完整）")
        api_ok = False

    # 总结
    print("\n" + "=" * 50)
    print("📊 测试结果汇总")
    print("=" * 50)
    print(f"  环境配置: {'✅' if env_ok else '❌'}")
    print(f"  Python 依赖: {'✅' if pkg_ok else '❌'}")
    print(f"  API 功能: {'✅' if api_ok else '❌'}")
    print("=" * 50 + "\n")

    if env_ok and pkg_ok and api_ok:
        print("🎉 所有测试通过！Docker 环境配置正确。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查配置。")
        return 1


if __name__ == "__main__":
    exit_code = 1
    try:
        import asyncio
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 测试已取消")
    sys.exit(exit_code)
