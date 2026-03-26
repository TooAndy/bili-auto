# 快速参考 - UP主订阅管理速查表

## 🚀 最快的方式（推荐）

```bash
# 启动交互式管理工具
uv run python manage_subscriptions.py
```

然后选择菜单中的选项即可。

---

## ⚡ 常用一行命令

### 添加单个UP主
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
db.add(Subscription(mid='1988098633', name='李毓佳', notes='科技UP'))
db.commit()
print('✅ 添加成功')
"
```

### 查看所有订阅
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
for s in db.query(Subscription).all():
    print(f'{s.id:>2} | {s.mid:>15} | {s.name:>20} | {\"✅激活\" if s.is_active else \"❌禁用\":>8}')
"
```

### 删除指定UP主
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
sub = db.query(Subscription).filter_by(mid='1988098633').first()
if sub:
    db.delete(sub)
    db.commit()
    print(f'❌ 已删除: {sub.name}')
"
```

### 禁用指定UP主（不删除数据）
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
sub = db.query(Subscription).filter_by(mid='1988098633').first()
if sub:
    sub.is_active = False
    db.commit()
    print(f'⏸️  已禁用: {sub.name}')
"
```

---

## 📋 批量导入的三种方式

### 方式1：直接Python列表
```bash
uv run python << 'EOF'
from app.models.database import get_db, Subscription

data = [
    ('1988098633', '李毓佳', '科技UP'),
    ('399658881', '罗翔说法律', '法律讲解'),
    ('2070143629', '油管搬运工', '搬运'),
]

db = get_db()
for mid, name, notes in data:
    if not db.query(Subscription).filter_by(mid=mid).first():
        db.add(Subscription(mid=mid, name=name, notes=notes))
        print(f'✅ {name}')
db.commit()
EOF
```

### 方式2：从文本文件
```bash
# subscriptions.txt 格式：mid|名字|备注
uv run python << 'EOF'
from app.models.database import get_db, Subscription

db = get_db()
with open('subscriptions.txt') as f:
    for line in f:
        if line.startswith('#') or not line.strip(): continue
        mid, name, notes = [x.strip() for x in line.split('|')]
        if not db.query(Subscription).filter_by(mid=mid).first():
            db.add(Subscription(mid=mid, name=name, notes=notes))
            print(f'✅ {name}')
db.commit()
EOF
```

### 方式3：交互式批量输入
```bash
uv run python manage_subscriptions.py
# 选择菜单选项 3（批量添加UP主）
```

---

## 🔍 快速查询命令

### 查询特定UP主
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
sub = db.query(Subscription).filter_by(mid='1988098633').first()
if sub:
    print(f'名字: {sub.name}')
    print(f'MID: {sub.mid}')
    print(f'状态: {\"激活\" if sub.is_active else \"禁用\"}')
    print(f'备注: {sub.notes or \"无\"}')
"
```

### 统计订阅数
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
total = db.query(Subscription).count()
active = db.query(Subscription).filter_by(is_active=True).count()
print(f'📊 总计: {total} | 🟢 激活: {active} | 🔴 禁用: {total-active}')
"
```

---

## 📊 更新/修改操作

### 修改UP主名字
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
sub = db.query(Subscription).filter_by(mid='1988098633').first()
if sub:
    sub.name = '新名字'
    db.commit()
    print(f'✅ 已更新')
"
```

### 修改UP主备注
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
sub = db.query(Subscription).filter_by(mid='1988098633').first()
if sub:
    sub.notes = '新备注'
    db.commit()
    print(f'✅ 已更新')
"
```

### 启用已禁用的UP主
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
sub = db.query(Subscription).filter_by(mid='1988098633').first()
if sub:
    sub.is_active = True
    db.commit()
    print(f'✅ 已启用')
"
```

---

## 🎯 工作流示例

### 场景1：第一次使用，添加3个UP主

```bash
# 1. 启动管理工具
uv run python manage_subscriptions.py

# 2. 选择 "2️⃣ 添加单个UP主"，依次添加

# 或者使用 "3️⃣ 批量添加"，格式：
# mid|名字|备注
# 完成后选 "1️⃣" 查看结果
```

### 场景2：有订阅列表文件要导入

```bash
# 1. 准备文件 subscriptions.txt，每行一个UP主
# 2. 运行导入
uv run python manage_subscriptions.py
# 选择 "3️⃣ 批量添加"
```

### 场景3：暂时不想看某个UP主

```bash
uv run python manage_subscriptions.py
# 选择 "5️⃣ 启用/禁用UP主"，输入 mid 禁用
```

---

## 📌 关键提示

| 操作 | 命令 | 说明 |
|------|------|------|
| **打开管理工具** | `uv run python manage_subscriptions.py` | 推荐方式 |
| **快速查看** | `uv run python -c "from app.models.database import get_db, Subscription; [print(s.name) for s in get_db().query(Subscription).all()]"` | 一行看所有 |
| **快速添加** | Python代码片段 | 见上方 |
| **批量导入** | 文本文件 | 见方式2 |
| **删除UP主** | Python代码 | 见上方 |
| **禁用UP主** | Python代码 | 保留数据，只暂停检测 |

---

## ✅ 检查清单

- [ ] 已添加至少1个UP主
- [ ] 运行 `uv run python main.py` 启动系统
- [ ] 查看日志 `tail -f logs/bili.log`
- [ ] 看到 `[检测] 开始检查新视频...` 即成功

---

**建议：第一次使用，推荐用管理工具！** 🎉
