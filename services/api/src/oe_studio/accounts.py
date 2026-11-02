"""Operator-provisioned accounts and revocable, project-scoped browser sessions."""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select
from .db import Account, AccountSession, LoginThrottle, ProjectMembership
from .errors import Problem

PASSWORDS = PasswordHasher()
ROLES = {'viewer', 'researcher', 'reviewer', 'approver'}
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def utc():
    return datetime.now(timezone.utc)


def password_hash(password):
    if len(password) < 12 or len(password) > 1024:
        raise ValueError('Password must contain 12–1024 characters')
    return PASSWORDS.hash(password)


def create_account(db, username, password):
    username = username.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9_.-]{0,63}', username):
        raise ValueError('Username must contain 1–64 ASCII letters, numbers, dots, underscores or hyphens')
    hashed = password_hash(password)
    with db.session(write=True) as s:
        account = Account(username=username, password_hash=hashed)
        s.add(account)
        s.flush()
        return account


def invalidate(db, account_id, *, password=None, disable=False):
    hashed = password_hash(password) if password is not None else None
    with db.session(write=True) as s:
        account = s.get(Account, account_id)
        if not account:
            raise ValueError('Unknown account')
        account.auth_version += 1
        if disable:
            account.enabled = False
        if hashed:
            account.password_hash = hashed
        for session in s.scalars(select(AccountSession).where(AccountSession.account_id == account_id)):
            session.revoked = True


def reset_password(db, account_id, password):
    invalidate(db, account_id, password=password)


def disable_account(db, account_id):
    invalidate(db, account_id, disable=True)


def grant_project(db, account_id, project_id, roles):
    roles = sorted(set(roles))
    if not set(roles) <= ROLES:
        raise ValueError('Unknown project role')
    with db.session(write=True) as s:
        if not s.get(Account, account_id):
            raise ValueError('Unknown account')
        membership = s.get(ProjectMembership, (account_id, project_id))
        if membership:
            membership.roles = roles
        else:
            s.add(ProjectMembership(account_id=account_id, project_id=project_id, roles=roles))


def actor_for(account, session):
    return dict(subject=account.id, username=account.username, kind='human', roles=[], auth_mode='team',
                session_id=session.id, auth_version=account.auth_version)


def login(db, settings, username, password, peer):
    username = username.strip().lower()
    # Both account and client buckets prevent distributed account guessing and username spraying.
    keys = [digest('account:' + username), digest('peer:' + peer)]
    failure = None
    result = None
    with db.session(write=True) as s:
        buckets = []
        for key in keys:
            bucket = s.get(LoginThrottle, key)
            if bucket is None:
                bucket = LoginThrottle(key=key, failures=0, window_start=utc().isoformat())
                s.add(bucket)
            if datetime.fromisoformat(bucket.window_start) < utc() - timedelta(minutes=15):
                bucket.failures = 0
                bucket.window_start = utc().isoformat()
            buckets.append(bucket)
        if any(b.failures >= 5 for b in buckets):
            failure = Problem(429, 'login_throttled', 'Too many login attempts; try again later')
        else:
            account = s.scalar(select(Account).where(Account.username == username))
            try:
                valid = PASSWORDS.verify(account.password_hash if account else DUMMY_HASH, password)
            except (VerificationError, InvalidHashError):
                valid = False
            if not valid or not account or not account.enabled:
                for bucket in buckets:
                    bucket.failures += 1
                failure = Problem(401, 'invalid_credentials', 'Invalid username or password')
            else:
                for bucket in buckets:
                    bucket.failures = 0
                if PASSWORDS.check_needs_rehash(account.password_hash):
                    account.password_hash = PASSWORDS.hash(password)
                token = secrets.token_urlsafe(32)
                csrf = csrf_token(token)
                session = AccountSession(account_id=account.id, token_hash=digest(token), csrf_hash=digest(csrf),
                                         auth_version=account.auth_version,
                                         expires_at=(utc() + timedelta(hours=settings.session_hours)).isoformat())
                s.add(session)
                s.flush()
                result = actor_for(account, session), token, csrf
    if failure:
        raise failure
    return result


def checked(s, session_id, subject=None, version=None):
    session = s.get(AccountSession, session_id) if session_id else None
    account = s.get(Account, session.account_id) if session else None
    if (not session or not account or not account.enabled or session.revoked
            or datetime.fromisoformat(session.expires_at) <= utc()
            or session.auth_version != account.auth_version
            or (subject is not None and subject != account.id)
            or (version is not None and version != account.auth_version)):
        raise Problem(401, 'login_required', 'Sign in to Studio')
    return account, session


def revalidate_actor(db, actor):
    if actor.get('auth_mode') != 'team':
        return actor
    with db.session() as s:
        account, session = checked(s, actor.get('session_id'), actor.get('subject'), actor.get('auth_version'))
        return actor_for(account, session)


def authorize_project(db, actor, project_id, role='viewer'):
    if actor.get('auth_mode') != 'team':
        if role not in actor.get('roles', []):
            raise Problem(403, 'role_required', 'Project role required')
        return actor
    with db.session() as s:
        account, session = checked(s, actor.get('session_id'), actor.get('subject'), actor.get('auth_version'))
        membership = s.get(ProjectMembership, (account.id, project_id))
        if not membership or not membership.roles or (role != 'viewer' and role not in membership.roles):
            raise Problem(403, 'project_forbidden', 'Project role required')
        return {**actor_for(account, session), 'roles': sorted(membership.roles)}


def revoke_session(db, session_id, account_id):
    with db.session(write=True) as s:
        session = s.get(AccountSession, session_id)
        if session and session.account_id == account_id:
            session.revoked = True


def check_origin(request):
    if request.headers.get('origin') != request.app.state.settings.team_origin:
        raise Problem(403, 'origin_forbidden', 'Request origin is not the configured Studio')


def authenticate_request(request):
    db = request.app.state.studio.db
    token = request.cookies.get('oe_session', '')
    with db.session() as s:
        session = s.scalar(select(AccountSession).where(AccountSession.token_hash == digest(token)))
        account, session = checked(s, session.id if session else None)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            check_origin(request)
            csrf = request.headers.get('x-csrf-token', '')
            if not csrf or not hmac.compare_digest(session.csrf_hash, digest(csrf)):
                raise Problem(403, 'csrf_required', 'Valid CSRF token required')
        return actor_for(account, session)


def session_payload(db, settings, actor):
    actor = revalidate_actor(db, actor)
    with db.session() as s:
        memberships = [dict(project_id=m.project_id, roles=sorted(m.roles)) for m in
                       s.scalars(select(ProjectMembership).where(ProjectMembership.account_id == actor['subject']))
                       if m.roles]
    return dict(actor={**actor, 'roles': sorted({role for m in memberships for role in m['roles']})},
                memberships=memberships)


def csrf_token(token):
    return hmac.new(token.encode(), b"oe-csrf-v1", hashlib.sha256).hexdigest()


def rotate_csrf(db, actor, token):
    csrf = csrf_token(token)
    with db.session() as s:
        _, session = checked(s, actor.get('session_id'), actor.get('subject'), actor.get('auth_version'))
        if not hmac.compare_digest(session.token_hash, digest(token)):
            raise Problem(401, "login_required", "Sign in to Studio")
        if not hmac.compare_digest(session.csrf_hash, digest(csrf)):
            raise Problem(401, "login_required", "Sign in to Studio")
    return csrf
