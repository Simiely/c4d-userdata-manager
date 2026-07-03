"""
系统性检查插件中所有 GeDialog 方法调用，找出 C4D 2026 中可能的
positional-only 参数冲突。
"""

import re, sys
from collections import defaultdict

with open('UserDataManager.pyp', 'r') as f:
    lines = f.readlines()

# 收集所有 self.Method(key=val, ...) 调用
issues = defaultdict(list)
safe = defaultdict(list)

# 已知在 C4D 2026 中变为 positional-only 的参数
# (method, param_name) 元组
known_positional_only = {
    ('AddStaticText', 'border'),
    ('AddComboBox', 'cols'),
}

# 已知安全的常用参数（不会被改成 positional-only）
safe_keywords = {
    'flags', 'name', 'initw', 'inith', 'title', 'cols', 'rows',
    'groupflags', 'scrollflags', 'def_file', 'def_path', 'force_suffix',
    'type',
}

for lineno, line in enumerate(lines, 1):
    # 找到 self.Method(...) 且包含 = 的调用
    for m in re.finditer(r'self\.(\w+)\(([^)]*)\)', line):
        method = m.group(1)
        args_str = m.group(2)
        if '=' not in args_str:
            continue
        
        # 解析关键字参数
        kwargs = re.findall(r'(\w+)=(?:\w+\.\w+|\w+|"[^"]*"|\'[^\']*\'|c4d\.\w+)', args_str)
        for kw in kwargs:
            key = (method, kw)
            if key in known_positional_only:
                issues[method].append((lineno, kw, args_str.strip()))
            elif kw not in safe_keywords:
                issues[method].append((lineno, kw, args_str.strip()))
            else:
                safe[method].append((lineno, kw))

print("=" * 60)
print("C4D 2026 兼容性检查结果")
print("=" * 60)

if issues:
    for method in sorted(issues.keys()):
        print(f"\n⚠️  {method}:")
        for lineno, kw, args_str in issues[method]:
            print(f"   L{lineno}: {kw}  ← {args_str[:80]}")
else:
    print("\n✅ 未发现新的潜在问题")

print(f"\n---")
print(f"已安全的常见关键字参数：")
for method in sorted(safe.keys()):
    params = sorted(set(kw for _, kw in safe[method]))
    print(f"  {method}: {', '.join(params)}")
