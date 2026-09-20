"""Explicit user OAuth for the local helper; no Codex cache or token handoff.

The helper uses a dedicated first-party native/public client with PKCE. Tokens and
callback codes remain in this process only. The server publishes only public OAuth
configuration and never exposes a client secret.
"""
import asyncio
import base64
import hashlib
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from .protocol import MaterialError

LOCAL_PORT = 18976
LOCAL_AUTH_CALLBACK = f'http://127.0.0.1:{LOCAL_PORT}/oauth/chatgrowing/callback'
LOCAL_YOUTUBE_CALLBACK = f'http://127.0.0.1:{LOCAL_PORT}/oauth/youtube/callback'


class LoopbackCallback:
    def __init__(self, path, state):
        self.path,self.state=path,state
        self.loop=asyncio.get_running_loop();self.future=self.loop.create_future()
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                parsed=urlsplit(self.path);values=parse_qs(parsed.query,keep_blank_values=True)
                matched=(self.headers.get('Host')==f'127.0.0.1:{LOCAL_PORT}'
                    and parsed.path==owner.path and len(values.get('state',[]))==1
                    and secrets.compare_digest(values['state'][0],owner.state))
                oauth_error=values.get('error',[])
                denied=matched and len(oauth_error)==1 and 'code' not in values
                valid=(matched and len(values.get('code',[]))==1 and 0<len(values['code'][0])<=4096
                    and 'error' not in values)
                self.send_response(200 if valid else 400)
                for k,v in {'Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Type':'text/plain; charset=utf-8','Content-Security-Policy':"default-src 'none'"}.items():self.send_header(k,v)
                if valid: message='已收到授权，请返回 Codex。'
                elif denied: message='授权未完成，请返回 Codex 查看具体原因。'
                else: message='授权回调校验失败，请返回 Codex 重试。'
                self.end_headers();self.wfile.write(message.encode())
                if valid or denied:
                    def finish():
                        if owner.future.done():return
                        if denied:
                            safe={'access_denied':'access_denied','unauthorized_client':'client_not_authorized',
                                'invalid_request':'request_invalid','login_required':'login_required',
                                'consent_required':'consent_required','interaction_required':'interaction_required'}
                            reason=safe.get(oauth_error[0],'oauth_denied')
                            owner.future.set_exception(MaterialError('material_authorization_'+reason,403))
                        else:owner.future.set_result(values['code'][0])
                    owner.loop.call_soon_threadsafe(finish)
        self.server=ThreadingHTTPServer(('127.0.0.1',LOCAL_PORT),Handler)
        self.server.daemon_threads=True
        import threading
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    async def receive(self):
        try:return await asyncio.wait_for(self.future,300)
        finally:await self.close()

    async def close(self):
        if self.server:
            server,self.server=self.server,None
            await asyncio.to_thread(server.shutdown);server.server_close()


class MaterialLocalAuth:
    def __init__(self,origin,*,client_factory=None,browser_open=None):
        parsed=urlsplit(origin)
        if parsed.scheme!='https' or not parsed.netloc or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise MaterialError('material_service_origin_invalid',422)
        self.origin=origin.rstrip('/');self.config=None;self.tokens={};self.cookies=httpx.Cookies()
        self.status='host_auth_required';self.task=None;self.last_error=None
        self.client_factory=client_factory or (lambda **kwargs:httpx.AsyncClient(timeout=30,trust_env=False,follow_redirects=False,**kwargs))
        self.browser_open=browser_open or webbrowser.open
        self.lock=asyncio.Lock()

    async def configure(self):
        async with self.client_factory() as client:
            response=await client.get(self.origin+'/material-actions/local-auth-config')
        if response.status_code!=200:raise MaterialError('material_local_login_not_configured',503)
        cfg=response.json()
        if not isinstance(cfg,dict):raise MaterialError('material_local_login_config_invalid',503)
        issuer=urlsplit(cfg.get('issuer',''))
        if (issuer.scheme!='https' or issuer.username or issuer.password or issuer.query or issuer.fragment
            or issuer.path not in ('','/') or not issuer.netloc
            or cfg.get('resource')!=self.origin+'/material-actions/mcp'
            or cfg.get('redirect_uri')!=LOCAL_AUTH_CALLBACK
            or not isinstance(cfg.get('client_id'),str) or not cfg['client_id']):
            raise MaterialError('material_local_login_config_invalid',503)
        self.config=cfg

    async def start(self,kind='login',*,name='YouTube 频道',enable_manage=True,organization=None):
        if self.task and not self.task.done():return {'status':'authorization_pending'}
        if kind not in ('login','youtube'):raise MaterialError('material_authorization_kind_invalid',422)
        if kind=='login':
            async with self.lock:
                self.tokens={};self.cookies.clear()
        self.last_error=None;self.status='authorization_pending'
        if organization is not None and (not isinstance(organization,str) or not organization or len(organization)>128):
            raise MaterialError('material_organization_invalid',422)
        self.task=asyncio.create_task(self._run(kind,name,enable_manage,organization))
        return {'status':'authorization_pending','requires_user_token_in_chat':False}

    async def _run(self,kind,name,enable_manage,organization):
        listener=None
        try:
            await self.configure()
            if kind=='login':
                state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
                challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
                listener=LoopbackCallback('/oauth/chatgrowing/callback',state)
                params=dict(response_type='code',client_id=self.config['client_id'],redirect_uri=LOCAL_AUTH_CALLBACK,scope='openid profile offline_access chatgrowing.materials',audience=self.config['resource'],resource=self.config['resource'],state=state,code_challenge=challenge,code_challenge_method='S256')
                if organization: params['organization']=organization
                url=self.config['issuer'].rstrip('/')+'/authorize?'+urlencode(params)
                if not await asyncio.to_thread(self.browser_open,url):raise MaterialError('material_browser_open_failed',503)
                code=await listener.receive()
                await self._token(dict(grant_type='authorization_code',client_id=self.config['client_id'],redirect_uri=LOCAL_AUTH_CALLBACK,code=code,code_verifier=verifier))
                # Only the authenticated server can establish the enterprise member.
                response=await self.request('GET','/v1/materials/session')
                if response.status_code!=200:
                    error='material_local_membership_denied'
                    try:
                        detail=response.json().get('detail')
                        if isinstance(detail,dict):detail=detail.get('error_code')
                        if detail in ('organization_context_required','membership_required'):error='material_'+detail
                    except Exception:pass
                    raise MaterialError(error,403)
            else:
                if self.config.get('youtube_redirect_uri')!=self.origin+'/material-actions/youtube/callback':
                    raise MaterialError('material_local_youtube_callback_not_configured',503)
                response=await self.request('POST','/v1/materials/youtube/authorize',json={'name':name,'enable_manage':enable_manage})
                if response.status_code!=200:raise MaterialError('material_youtube_authorize_failed',403)
                url=response.json()['authorization_url'];parsed=urlsplit(url);values=parse_qs(parsed.query,keep_blank_values=True)
                if parsed.scheme!='https' or parsed.netloc!='accounts.google.com' or len(values.get('state',[]))!=1:
                    raise MaterialError('material_youtube_authorize_invalid',502)
                listener=LoopbackCallback('/oauth/youtube/callback',values['state'][0])
                if not await asyncio.to_thread(self.browser_open,url):raise MaterialError('material_browser_open_failed',503)
                code=await listener.receive()
                response=await self.request('POST','/v1/materials/youtube/complete',json={'state':values['state'][0],'code':code})
                if response.status_code!=200:raise MaterialError('material_youtube_complete_failed',403)
            self.status='authenticated' if kind=='login' else 'youtube_connected'
        except asyncio.CancelledError:raise
        except Exception as exc:
            self.status='authorization_failed';self.last_error=exc.code if isinstance(exc,MaterialError) else 'material_local_authorization_failed'
            if kind=='login':self.tokens={}
        finally:
            if listener:await listener.close()

    async def _token(self,body):
        async with self.client_factory() as client:
            response=await client.post(self.config['issuer'].rstrip('/')+'/oauth/token',json=body)
        if response.status_code!=200:raise MaterialError('material_local_token_exchange_failed',403)
        values=response.json()
        if not isinstance(values.get('access_token'),str) or not values['access_token'] or values.get('token_type','').lower()!='bearer':
            raise MaterialError('material_local_token_response_invalid',502)
        expires=values.get('expires_in',0)
        if not isinstance(expires,(int,float)) or not 0<expires<=604800:raise MaterialError('material_local_token_response_invalid',502)
        self.tokens={'access_token':values['access_token'],'refresh_token':values.get('refresh_token') or self.tokens.get('refresh_token'),'expires_at':time.time()+expires}

    async def access_token(self):
        async with self.lock:
            if self.tokens.get('expires_at',0)<=time.time()+30:
                if not self.tokens.get('refresh_token') or not self.config:raise MaterialError('material_host_auth_required',401)
                try:await self._token(dict(grant_type='refresh_token',client_id=self.config['client_id'],refresh_token=self.tokens['refresh_token']))
                except Exception:
                    self.tokens={};raise
            return self.tokens['access_token']

    async def request(self,method,path,**kwargs):
        token=await self.access_token()
        async with self.client_factory(headers={'Authorization':'Bearer '+token},cookies=self.cookies) as client:
            response=await client.request(method,self.origin+path,**kwargs)
            self.cookies.update(client.cookies)
        return response

    async def logout(self):
        if self.task and not self.task.done():
            self.task.cancel()
            try:await self.task
            except asyncio.CancelledError:pass
        async with self.lock:
            self.tokens={};self.cookies.clear();self.status='host_auth_required';self.last_error=None
        return {'status':'logged_out_locally'}
