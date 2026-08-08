#!/usr/bin/env python3
"""
CATL QuantiSkills 全景分析 — 一键更新
用法: python3 run.py
"""
import subprocess, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))

print("╔══════════════════════════════════════╗")
print("║  🔋 CATL QuantiSkills 全景分析     ║")
print("╚══════════════════════════════════════╝")
print()

# Step 1: Data collection
print("📡 采集数据...")
result = subprocess.run([sys.executable, f"{BASE}/fetch_data.py"], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"❌ 数据采集失败:\n{result.stderr}")
    sys.exit(1)

# Step 2: Report generation
print("🎨 生成报告...")
result = subprocess.run([sys.executable, f"{BASE}/gen_report.py"], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"❌ 报告生成失败:\n{result.stderr}")
    sys.exit(1)

print(f"\n📊 报告位置: {BASE}/index.html")
print("✅ 全部完成！")
