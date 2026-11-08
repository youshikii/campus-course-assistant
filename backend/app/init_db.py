"""Non-destructive schema initialization and optional first administrator setup."""
import argparse
from getpass import getpass

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import campus
from app.models.user import User
from app.utils.password import hash_password


def main():
    parser = argparse.ArgumentParser(description="创建缺失的表，可选初始化管理员；不清空已有数据")
    parser.add_argument("--admin", help="新管理员账号（已存在则不修改）")
    parser.add_argument("--migrate-legacy-schedules", action="store_true", help="显式迁移旧课程中的学生上课安排；仅升级时使用")
    args = parser.parse_args()
    Base.metadata.create_all(engine)
    print("数据库表已就绪；已有表和数据保留。")
    if args.migrate_legacy_schedules:
        from app.migrate_schedules import migrate_legacy_schedules

        with SessionLocal() as db:
            print("课表迁移结果:", migrate_legacy_schedules(db))
    if args.admin:
        if not 1 <= len(args.admin) <= 50:
            parser.error("账号长度应为 1–50 个字符")
        with SessionLocal() as db:
            if db.scalar(select(User).where(User.username == args.admin)):
                print("账号已存在，未修改其密码或权限。")
                return
            password = getpass("管理员密码（至少 8 位，不超过 72 UTF-8 字节）: ")
            if len(password) < 8 or len(password.encode()) > 72:
                parser.error("密码长度不符合要求")
            if password != getpass("再次输入密码: "):
                parser.error("两次输入的密码不一致")
            db.add(User(username=args.admin, password=hash_password(password), name=args.admin, role="admin", status=1))
            db.commit()
            print("管理员已创建。")


if __name__ == "__main__":
    main()
