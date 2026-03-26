#!/usr/bin/env python3
"""
UP主订阅管理工具
支持添加、查看、编辑、删除UP主订阅
"""

import sys
from app.models.database import get_db, Subscription
from datetime import datetime

# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}")
    print(f"{text:^60}")
    print(f"{'='*60}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.ENDC}")

def list_subscriptions():
    """显示所有UP主订阅"""
    db = get_db()
    subs = db.query(Subscription).all()
    
    if not subs:
        print_warning("暂无任何UP主订阅")
        return
    
    print_header("UP主订阅列表")
    print(f"{'ID':<5} {'MID':<15} {'名字':<20} {'状态':<8} {'最后检测':<20}")
    print("-" * 80)
    
    for sub in subs:
        status = "✅ 激活" if sub.is_active else "❌ 禁用"
        last_check = sub.last_check_time.strftime("%Y-%m-%d %H:%M") if sub.last_check_time else "未检测"
        print(f"{sub.id:<5} {sub.mid:<15} {sub.name:<20} {status:<8} {last_check:<20}")
        if sub.notes:
            print(f"     📝 备注: {sub.notes}")
    
    print(f"\n📊 总计: {len(subs)} 个UP主")

def add_subscription():
    """添加新的UP主订阅"""
    print_header("添加 UP 主订阅")
    
    try:
        mid = input(f"{Colors.BLUE}请输入UP主ID (mid): {Colors.ENDC}").strip()
        if not mid:
            print_error("UP主ID不能为空")
            return
        
        name = input(f"{Colors.BLUE}请输入UP主名字: {Colors.ENDC}").strip()
        if not name:
            print_error("UP主名字不能为空")
            return
        
        notes = input(f"{Colors.BLUE}请输入备注 (可选): {Colors.ENDC}").strip()
        
        db = get_db()
        
        # 检查是否已存在
        existing = db.query(Subscription).filter_by(mid=mid).first()
        if existing:
            print_error(f"UP主ID '{mid}' 已存在 (名字: {existing.name})")
            return
        
        # 添加新订阅
        sub = Subscription(
            mid=mid,
            name=name,
            notes=notes if notes else None,
            is_active=True
        )
        db.add(sub)
        db.commit()
        
        print_success(f"成功添加UP主: {name} (MID: {mid})")
        
    except Exception as e:
        print_error(f"添加失败: {str(e)}")

def add_bulk_subscriptions():
    """批量添加UP主订阅"""
    print_header("批量添加 UP 主订阅")
    
    print_info("请按照以下格式输入UP主信息 (每行一个):")
    print(f"{Colors.YELLOW}mid|名字|备注 (最后一个参数可选){Colors.ENDC}")
    print("示例:")
    print(f"{Colors.CYAN}1988098633|李毓佳|科技UP主")
    print("399658881|罗翔说法律|")
    print("(按 Ctrl+D 或输入空行结束){Colors.ENDC}\n")
    
    try:
        db = get_db()
        added_count = 0
        error_count = 0
        
        while True:
            try:
                line = input()
                if not line.strip():
                    break
                
                parts = line.split('|')
                if len(parts) < 2:
                    print_error(f"格式错误: {line} (至少需要 mid|名字)")
                    error_count += 1
                    continue
                
                mid = parts[0].strip()
                name = parts[1].strip()
                notes = parts[2].strip() if len(parts) > 2 else None
                
                # 检查是否已存在
                existing = db.query(Subscription).filter_by(mid=mid).first()
                if existing:
                    print_warning(f"跳过: '{name}' (MID {mid} 已存在)")
                    error_count += 1
                    continue
                
                # 添加订阅
                sub = Subscription(
                    mid=mid,
                    name=name,
                    notes=notes,
                    is_active=True
                )
                db.add(sub)
                added_count += 1
                print_info(f"✓ {name}")
            
            except EOFError:
                break
            except Exception as e:
                print_error(f"处理错误: {str(e)}")
                error_count += 1
        
        if added_count > 0:
            db.commit()
            print_success(f"成功添加 {added_count} 个UP主")
        
        if error_count > 0:
            print_warning(f"遇到 {error_count} 个错误")
        
    except Exception as e:
        print_error(f"批量添加失败: {str(e)}")

def toggle_subscription():
    """启用/禁用UP主订阅"""
    print_header("启用/禁用 UP 主订阅")
    
    try:
        mid = input(f"{Colors.BLUE}请输入UP主ID (mid): {Colors.ENDC}").strip()
        if not mid:
            print_error("UP主ID不能为空")
            return
        
        db = get_db()
        sub = db.query(Subscription).filter_by(mid=mid).first()
        
        if not sub:
            print_error(f"未找到UP主: {mid}")
            return
        
        sub.is_active = not sub.is_active
        db.commit()
        
        status = "启用" if sub.is_active else "禁用"
        print_success(f"{status}: {sub.name}")
        
    except Exception as e:
        print_error(f"操作失败: {str(e)}")

def delete_subscription():
    """删除UP主订阅"""
    print_header("删除 UP 主订阅")
    
    try:
        mid = input(f"{Colors.BLUE}请输入UP主ID (mid): {Colors.ENDC}").strip()
        if not mid:
            print_error("UP主ID不能为空")
            return
        
        db = get_db()
        sub = db.query(Subscription).filter_by(mid=mid).first()
        
        if not sub:
            print_error(f"未找到UP主: {mid}")
            return
        
        confirm = input(f"{Colors.YELLOW}确认删除 '{sub.name}'? (y/n): {Colors.ENDC}").strip().lower()
        if confirm != 'y':
            print_info("已取消删除")
            return
        
        db.delete(sub)
        db.commit()
        
        print_success(f"已删除: {sub.name}")
        
    except Exception as e:
        print_error(f"删除失败: {str(e)}")

def update_subscription():
    """编辑UP主信息"""
    print_header("编辑 UP 主信息")
    
    try:
        mid = input(f"{Colors.BLUE}请输入UP主ID (mid): {Colors.ENDC}").strip()
        if not mid:
            print_error("UP主ID不能为空")
            return
        
        db = get_db()
        sub = db.query(Subscription).filter_by(mid=mid).first()
        
        if not sub:
            print_error(f"未找到UP主: {mid}")
            return
        
        print(f"\n当前信息:")
        print(f"  名字: {sub.name}")
        print(f"  备注: {sub.notes or '无'}")
        
        new_name = input(f"\n{Colors.BLUE}新名字 (留空保持不变): {Colors.ENDC}").strip()
        if new_name:
            sub.name = new_name
        
        new_notes = input(f"{Colors.BLUE}新备注 (留空保持不变): {Colors.ENDC}").strip()
        if new_notes or input(f"{Colors.BLUE}清空备注? (y/n): {Colors.ENDC}").strip().lower() == 'y':
            sub.notes = new_notes if new_notes else None
        
        db.commit()
        print_success("已更新UP主信息")
        
    except Exception as e:
        print_error(f"更新失败: {str(e)}")

def show_menu():
    """显示菜单"""
    print_header("UP 主订阅管理工具")
    print(f"""
{Colors.CYAN}选择操作:{Colors.ENDC}

  1️⃣  查看所有UP主订阅
  2️⃣  添加单个UP主
  3️⃣  批量添加UP主
  4️⃣  编辑UP主信息
  5️⃣  启用/禁用UP主
  6️⃣  删除UP主
  0️⃣  退出

""")

def main():
    """主函数"""
    while True:
        show_menu()
        choice = input(f"{Colors.BLUE}请选择操作 (0-6): {Colors.ENDC}").strip()
        
        if choice == '0':
            print_success("已退出")
            break
        elif choice == '1':
            list_subscriptions()
        elif choice == '2':
            add_subscription()
        elif choice == '3':
            add_bulk_subscriptions()
        elif choice == '4':
            update_subscription()
        elif choice == '5':
            toggle_subscription()
        elif choice == '6':
            delete_subscription()
        else:
            print_error("无效选择")
        
        input(f"\n{Colors.BLUE}按 Enter 继续...{Colors.ENDC}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}已中断{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"程序错误: {str(e)}")
        sys.exit(1)
