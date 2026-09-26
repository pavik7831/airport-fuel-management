import argparse
import asyncio
from getpass import getpass

from sqlalchemy import select

from backend.app.db import SessionLocal
from backend.app.models import Admin
from backend.app.security import hash_password


async def bootstrap(username: str, password: str):
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    async with SessionLocal() as db:
        if await db.scalar(select(Admin).where(Admin.username == username)):
            raise SystemExit("Administrator already exists")
        db.add(Admin(username=username, password_hash=hash_password(password)))
        await db.commit()


async def reset_password(username: str, password: str):
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters")
    async with SessionLocal() as db:
        admin = await db.scalar(select(Admin).where(Admin.username == username))
        if not admin:
            raise SystemExit("Administrator not found; use create-admin first")
        admin.password_hash = hash_password(password)
        await db.commit()


def main():
    parser = argparse.ArgumentParser(description="Airport Fuel Management administration")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-admin")
    create.add_argument("--username", required=True)
    create.add_argument("--password")
    reset = sub.add_parser("reset-password")
    reset.add_argument("--username", required=True)
    reset.add_argument("--password")
    args = parser.parse_args()
    if args.command in {"create-admin", "reset-password"}:
        password = args.password or getpass("New administrator password: ")
        operation = bootstrap if args.command == "create-admin" else reset_password
        asyncio.run(operation(args.username, password))


if __name__ == "__main__":
    main()
