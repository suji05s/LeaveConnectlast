import jwt
from jwt import PyJWKClient
import os
import uuid
from functools import wraps
from urllib.parse import urlencode
import requests
import logging

from flask import g, session, redirect, request, render_template, url_for
from flask_dance.consumer import (
    OAuth2ConsumerBlueprint,
    oauth_authorized,
    oauth_error,
)
from flask_dance.consumer.storage import BaseStorage
from flask_login import LoginManager, login_user, logout_user, current_user
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from sqlalchemy.exc import NoResultFound
from werkzeug.local import LocalProxy

from app import app, db
from models import OAuth, User, LeaveBalance

logger = logging.getLogger(__name__)

login_manager = LoginManager(app)

def get_jwks_uri():
    """Fetch JWKS URI from OIDC discovery endpoint"""
    issuer_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc")
    discovery_url = f"{issuer_url}/.well-known/openid-configuration"
    try:
        response = requests.get(discovery_url, timeout=5)
        if response.status_code == 200:
            return response.json().get('jwks_uri')
    except Exception as e:
        logger.error(f"Failed to fetch OIDC configuration: {e}")
    return None

def verify_jwt_token(token, issuer_url):
    """Verify JWT signature and decode token with full validation"""
    try:
        jwks_uri = get_jwks_uri()
        if not jwks_uri:
            raise Exception("Could not fetch JWKS URI")
        
        jwks_client = PyJWKClient(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        repl_id = os.environ.get('REPL_ID')
        if not repl_id:
            raise Exception("REPL_ID not configured")
        
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=issuer_url,
            audience=repl_id,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": True
            }
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("JWT token has expired")
        raise
    except jwt.InvalidSignatureError:
        logger.error("JWT signature verification failed")
        raise
    except jwt.InvalidAudienceError:
        logger.error("JWT audience validation failed")
        raise
    except Exception as e:
        logger.error(f"JWT verification failed: {e}")
        raise

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

class UserSessionStorage(BaseStorage):
    def get(self, blueprint):
        try:
            token = db.session.query(OAuth).filter_by(
                user_id=current_user.get_id(),
                browser_session_key=g.browser_session_key,
                provider=blueprint.name,
            ).one().token
        except NoResultFound:
            token = None
        return token

    def set(self, blueprint, token):
        db.session.query(OAuth).filter_by(
            user_id=current_user.get_id(),
            browser_session_key=g.browser_session_key,
            provider=blueprint.name,
        ).delete()
        new_model = OAuth()
        new_model.user_id = current_user.get_id()
        new_model.browser_session_key = g.browser_session_key
        new_model.provider = blueprint.name
        new_model.token = token
        db.session.add(new_model)
        db.session.commit()

    def delete(self, blueprint):
        db.session.query(OAuth).filter_by(
            user_id=current_user.get_id(),
            browser_session_key=g.browser_session_key,
            provider=blueprint.name).delete()
        db.session.commit()

def make_replit_blueprint():
    try:
        repl_id = os.environ['REPL_ID']
    except KeyError:
        raise SystemExit("the REPL_ID environment variable must be set")

    issuer_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc")

    replit_bp = OAuth2ConsumerBlueprint(
        "replit_auth",
        __name__,
        client_id=repl_id,
        client_secret=None,
        base_url=issuer_url,
        authorization_url_params={
            "prompt": "login consent",
        },
        token_url=issuer_url + "/token",
        token_url_params={
            "auth": (),
            "include_client_id": True,
        },
        auto_refresh_url=issuer_url + "/token",
        auto_refresh_kwargs={
            "client_id": repl_id,
        },
        authorization_url=issuer_url + "/auth",
        use_pkce=True,
        code_challenge_method="S256",
        scope=["openid", "profile", "email", "offline_access"],
        storage=UserSessionStorage(),
    )

    @replit_bp.before_app_request
    def set_applocal_session():
        if '_browser_session_key' not in session:
            session['_browser_session_key'] = uuid.uuid4().hex
        session.modified = True
        g.browser_session_key = session['_browser_session_key']
        g.flask_dance_replit = replit_bp.session

    @replit_bp.route("/logout")
    def logout():
        del replit_bp.token
        logout_user()

        end_session_endpoint = issuer_url + "/session/end"
        encoded_params = urlencode({
            "client_id": repl_id,
            "post_logout_redirect_uri": request.url_root,
        })
        logout_url = f"{end_session_endpoint}?{encoded_params}"

        return redirect(logout_url)

    @replit_bp.route("/error")
    def error():
        return render_template("403.html"), 403

    return replit_bp

def save_user(user_claims):
    user = User()
    user.id = user_claims['sub']
    user.email = user_claims.get('email')
    user.first_name = user_claims.get('first_name')
    user.last_name = user_claims.get('last_name')
    user.profile_image_url = user_claims.get('profile_image_url')
    merged_user = db.session.merge(user)
    db.session.commit()
    
    balance = LeaveBalance.query.filter_by(user_id=merged_user.id).first()
    if not balance:
        balance = LeaveBalance(user_id=merged_user.id)
        db.session.add(balance)
        db.session.commit()
    
    return merged_user

@oauth_authorized.connect
def logged_in(blueprint, token):
    try:
        issuer_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc")
        user_claims = verify_jwt_token(token['id_token'], issuer_url)
        user = save_user(user_claims)
        login_user(user)
        blueprint.token = token
        next_url = session.pop("next_url", None)
        if next_url is not None:
            return redirect(next_url)
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return redirect(url_for('replit_auth.error'))

@oauth_error.connect
def handle_error(blueprint, error, error_description=None, error_uri=None):
    return redirect(url_for('replit_auth.error'))

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            session["next_url"] = get_next_navigation_url(request)
            return redirect(url_for('replit_auth.login'))

        expires_in = replit.token.get('expires_in', 0)
        if expires_in < 0:
            issuer_url = os.environ.get('ISSUER_URL', "https://replit.com/oidc")
            refresh_token_url = issuer_url + "/token"
            try:
                token = replit.refresh_token(token_url=refresh_token_url, client_id=os.environ['REPL_ID'])
            except InvalidGrantError:
                session["next_url"] = get_next_navigation_url(request)
                return redirect(url_for('replit_auth.login'))
            replit.token_updater(token)

        return f(*args, **kwargs)

    return decorated_function

def get_next_navigation_url(request):
    is_navigation_url = request.headers.get('Sec-Fetch-Mode') == 'navigate' and request.headers.get('Sec-Fetch-Dest') == 'document'
    if is_navigation_url:
        return request.url
    return request.referrer or request.url

replit = LocalProxy(lambda: g.flask_dance_replit)
