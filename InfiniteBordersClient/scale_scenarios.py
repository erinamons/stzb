"""缩放脚本v6：修正关口格式（方括号内是圆括号元组）"""
import re

src = r'E:\pyproject\PythonProject\InfiniteBordersServer\scenarios.py'
dst = r'E:\pyproject\PythonProject\InfiniteBordersClient\scenarios.py'

with open(src, 'r', encoding='utf-8') as f:
    content = f.read()

# 第一步：缩放城池 (数字, 数字, "串", 数字, "串")
content = re.sub(
    r'\((\d+),\s*(\d+),\s*"([^"]+)",\s*(\d+),\s*"([^"]+)"\)',
    lambda m: '({:.0f}, {:.0f}, "{}", {}, "{}")'.format(
        int(m.group(1))*1.5, int(m.group(2))*1.5, m.group(3), m.group(4), m.group(5)
    ),
    content
)

# 第二步：缩放关口 [  (数字, 数字, "串") ]
content = re.sub(
    r'\[\s*\(\s*(\d+),\s*(\d+),\s*"([^"]+)"\s*\)\s*\]',
    lambda m: '[({:.0f}, {:.0f}, "{}")]'.format(
        int(m.group(1))*1.5, int(m.group(2))*1.5, m.group(3)
    ),
    content
)

# 更新注释
content = content.replace('80x60', '120x90').replace('80×60', '120x90')

with open(dst, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)

import py_compile
try:
    py_compile.compile(dst, doraise=True)
    print('OK')
except Exception as e:
    print(f'ERROR: {e}')
