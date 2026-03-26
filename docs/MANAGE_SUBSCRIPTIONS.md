# UP主订阅管理指南

## 📺 方法一：交互式管理工具（推荐）

使用我为你创建的管理脚本，可以轻松添加、查看、编辑和删除UP主订阅。

### 启动管理工具

```bash
cd /Users/aniss/Code/bili-auto
uv run python manage_subscriptions.py
```

### 功能说明

```
1️⃣  查看所有UP主订阅
    显示当前数据库中的所有订阅UP主及其状态

2️⃣  添加单个UP主
    逐个输入UP主ID (mid)、名字、备注等信息
    示例:
    - mid: 1988098633
    - 名字: 李毓佳
    - 备注: 科技UP主（可选）

3️⃣  批量添加UP主
    一次性添加多个UP主，格式为: mid|名字|备注
    示例:
    1988098633|李毓佳|科技UP主
    399658881|罗翔说法律|法律讲解
    （按 Ctrl+D 结束输入）

4️⃣  编辑UP主信息
    修改UP主的名字或备注

5️⃣  启用/禁用UP主
    暂时停止或恢复对某个UP主的检测

6️⃣  删除UP主
    删除不再需要关注的UP主订阅

0️⃣  退出
    退出程序
```

---

## 🐍 方法二：Python 一行命令

### 添加单个UP主

```bash
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()
sub = Subscription(mid='1988098633', name='李毓佳', notes='科技UP主')
db.add(sub)
db.commit()
print('✅ 成功添加UP主: 李毓佳')
"
```

### 批量添加多个UP主

```bash
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()

# UP主信息列表
uppers = [
    {'mid': '1988098633', 'name': '李毓佳', 'notes': '科技UP主'},
    {'mid': '399658881', 'name': '罗翔说法律', 'notes': '法律讲解'},
    {'mid': '2070143629', 'name': '油管搬运工', 'notes': '英文字幕搬运'},
]

for upper in uppers:
    # 检查是否已存在
    existing = db.query(Subscription).filter_by(mid=upper['mid']).first()
    if existing:
        print(f\"⏭️  跳过: {upper['name']} (已存在)\")
        continue
    
    sub = Subscription(
        mid=upper['mid'],
        name=upper['name'],
        notes=upper['notes']
    )
    db.add(sub)
    print(f\"✅ 添加: {upper['name']}\")

db.commit()
print('✅ 全部完成')
"
```

---

## 📋 方法三：配置文件导入

首先，创建一个 `subscriptions.txt` 文件，格式为 `mid|名字|备注`：

```txt
1988098633|李毓佳|科技UP主
399658881|罗翔说法律|法律讲解
2070143629|油管搬运工|英文字幕搬运
156160448|朱一旦的枯燥生活|幽默UP主
```

然后运行导入脚本：

```bash
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()

with open('subscriptions.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split('|')
        if len(parts) < 2:
            continue
        
        mid = parts[0].strip()
        name = parts[1].strip()
        notes = parts[2].strip() if len(parts) > 2 else None
        
        # 检查是否已存在
        existing = db.query(Subscription).filter_by(mid=mid).first()
        if existing:
            print(f'⏭️  跳过: {name}')
            continue
        
        sub = Subscription(mid=mid, name=name, notes=notes)
        db.add(sub)
        print(f'✅ 添加: {name}')

db.commit()
print('✅ 导入完成')
"
```

---

## 📊 如何获取UP主的 MID

### 方式1：从网址获取
- 访问UP主主页，URL格式: `https://space.bilibili.com/{MID}`
- 复制 `{MID}` 部分即可

### 方式2：B站API查询
```bash
curl "https://api.bilibili.com/x/web-interface/search/type?search_type=bili_user&keyword=李毓佳" | grep -o '"mid":[0-9]*' | head -1
```

### 方式3：常见UP主的MID

| UP主 | MID | 类别 |
|------|------|------|
| 李毓佳 | 1988098633 | 科技/评测 |
| 罗翔说法律 | 399658881 | 法律讲解 |
| 油管搬运工 | 2070143629 | 英文搬运 |
| 朱一旦的枯燥生活 | 156160448 | 娱乐/幽默 |
| 半泽直树研究所 | 1395169867 | 番剧/分析 |
| 高山定士 | 159041871 | 动漫评测 |
| 狼叔 | 337338227 | 游戏 |

---

## ✅ 验证订阅是否添加成功

添加后，可以通过以下方式验证：

```bash
# 查看所有订阅
uv run python -c "
from app.models.database import get_db, Subscription

db = get_db()
subs = db.query(Subscription).filter_by(is_active=True).all()

print('\\n=== 活跃UP主订阅 ===\\n')
for sub in subs:
    print(f'📺 {sub.name} (MID: {sub.mid})')
    if sub.notes:
        print(f'   📝 {sub.notes}')
print(f'\\n📊 总计: {len(subs)} 个')
"
```

---

## 🚀 启动系统开始检测

添加UP主后，启动主程序：

```bash
uv run python main.py
```

系统将：
1. 每 10 分钟检测一次所有UP主的新视频
2. 每 5 分钟检测一次所有UP主的新动态
3. 自动处理发现的新内容

查看实时日志：
```bash
tail -f logs/bili.log
```

---

## 💡 常见问题

**Q: 如何暂停某个UP主的检测？**
A: 运行管理工具，选择 "5️⃣ 启用/禁用UP主"，禁用即可。

**Q: 如何修改UP主的信息？**
A: 运行管理工具，选择 "4️⃣ 编辑UP主信息"。

**Q: 添加后多久会开始处理？**
A: 最多等待 5-10 分钟（取决于检测周期）。

**Q: 如何导出已添加的UP主列表？**
A: 运行管理工具，选择 "1️⃣ 查看所有UP主"，或用以下命令：
```bash
uv run python -c "
from app.models.database import get_db, Subscription
db = get_db()
for sub in db.query(Subscription).all():
    print(f'{sub.mid}|{sub.name}|{sub.notes or \"\"}')
"
```

---

## 🔄 数据库字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `mid` | UP主UID（唯一） | 1988098633 |
| `name` | UP主昵称 | 李毓佳 |
| `notes` | 备注（可选） | 科技UP主 |
| `is_active` | 是否激活 | true |
| `last_check_time` | 最后检测时间 | 2026-03-26 16:30 |
| `last_video_bvid` | 最后检测的视频ID | BVxxxxxx |
| `last_dynamic_id` | 最后检测的动态ID | 123456789 |

---

**现在就开始添加你的首个UP主吧！** 🎉
