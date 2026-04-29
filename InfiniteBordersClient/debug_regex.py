import re

line = '        (12, 15, "武威",   8, "州府"),   # 凉州治所，河西走廊要冲\n'
m = re.match(r'^(\s*)\((\d+),\s*(\d+),\s*("[^"]+"),\s*(\d+),\s*("[^"]+?)\)\s*,\s*(#.*)$', line)
print(f'Match: {m}')

# 测试: 也许中文括号或其他字符
line2 = repr(line)
print(f'Repr: {line2}')

# 直接用更宽松的正则
m2 = re.match(r'\(\s*(\d+)\s*,\s*(\d+)\s*,', line)
print(f'Simple match: {m2}')

# 也许问题是 Windows BOM?
with open('scenarios.py', 'rb') as f:
    first_bytes = f.read(20)
    print(f'First 20 bytes: {first_bytes}')
