import sys
from pathlib import Path

# --- 1. 路径修复 (必须放在最前面) ---
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# --- 2. 导入核心组件 ---
from core import vector_store

# --- 3. 查库 ---
print("\n🔎 正在扫描向量数据库...")

# 获取所有数据 ID
all_data = vector_store.get()
count = len(all_data['ids'])

print(f"📊 当前数据库状态：共存储了 【{count}】 个向量分块。")

if count > 0:
    print("-" * 30)
    print("📝 第一条数据的元数据 (Metadata) 预览：")
    # 打印第一条数据的 metadata，验证 user_id 和 file_id 是否存在
    print(all_data['metadatas'])
    print("-" * 30)
    print("✅ 验证通过：数据库已包含数据，可以进行对话了！")
else:
    print("❌ 验证失败：数据库是空的。")
    print("👉 请回到 Thunder Client 执行 /api/upload 上传一个文件。")
    