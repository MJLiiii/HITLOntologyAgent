"""Offline account operations; passwords never appear in command arguments or output."""
import argparse
import getpass
import sys
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from . import accounts
from .db import Account, Database
from .settings import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    for name in ('create', 'disable', 'reset-password', 'revoke-sessions', 'set-roles'):
        command = commands.add_parser(name)
        command.add_argument('username')
        if name in {'create', 'reset-password'}:
            command.add_argument('--password-stdin', action='store_true', help='Read one password line from stdin')
        if name == 'set-roles':
            command.add_argument('project_id')
            command.add_argument('roles', nargs='*', choices=sorted(accounts.ROLES))
    args = parser.parse_args()
    settings = Settings()
    if settings.mode != 'team':
        parser.error('Account operations require OE_MODE=team')
    db = Database(settings.database_url)
    try:
        db.ensure_migrated()
        if args.operation == 'create':
            password = sys.stdin.readline().rstrip('\r\n') if args.password_stdin else getpass.getpass('Password: ')
            account = accounts.create_account(db, args.username, password)
        else:
            with db.session() as s:
                account = s.scalar(select(Account).where(Account.username == args.username.strip().lower()))
            if not account:
                parser.error('Unknown account')
            if args.operation == 'disable':
                accounts.disable_account(db, account.id)
            elif args.operation == 'reset-password':
                password = sys.stdin.readline().rstrip('\r\n') if args.password_stdin else getpass.getpass('New password: ')
                accounts.reset_password(db, account.id, password)
            elif args.operation == 'revoke-sessions':
                accounts.invalidate(db, account.id)
            else:
                accounts.grant_project(db, account.id, args.project_id, args.roles)
        print(f'{args.operation} completed for {account.username} ({account.id})')
    except ValueError as error:
        parser.error(str(error))
    except SQLAlchemyError:
        parser.error('Database operation failed; verify the account, project, connection and migrated schema')
    finally:
        db.engine.dispose()


if __name__ == '__main__':
    main()
