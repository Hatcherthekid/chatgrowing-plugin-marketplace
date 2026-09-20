#!/usr/bin/env python3
"""Local file access with explicit browser login; credentials never enter tool arguments."""
import asyncio
import os
from pathlib import Path
import sys

CODE=Path(__file__).resolve().parents[1]
if str(CODE) not in sys.path:sys.path.insert(0,str(CODE))
import httpx
from mcp.server.fastmcp import FastMCP
from shared.material_source.protocol import MaterialError
from shared.material_source.client import MaterialSourceClient, source_manifest


def build_server(*, environ=None, inspector=None):
    env=os.environ if environ is None else environ
    server=FastMCP('chatgrowing-material-local')
    from shared.material_source.auth import MaterialLocalAuth
    origin=env.get('CHATGROWING_MATERIAL_SERVICE_ORIGIN') or 'https://chatgrowing.com'
    auth=MaterialLocalAuth(origin)

    @server.tool(description='打开浏览器登录现有 ChatGrowing 企业账号，授权本地素材工具。只有用户属于多个企业时才填写 Auth0 organization 标识；不要求复制 token。')
    async def material_local_login(organization: str|None=None) -> dict:
        return await auth.start(organization=organization)

    @server.tool(description='清除本地素材工具进程内的登录凭据；不撤销企业 Google 授权，不登出其他工具。')
    async def material_local_logout() -> dict:
        return await auth.logout()

    @server.tool(description='已登录 ChatGrowing 后，在浏览器连接自己的 YouTube 频道。默认一次申请上传及视频管理权限，以支持上传、更新、字幕和删除；只读场景可关闭 enable_manage。')
    async def material_local_youtube_connect(name: str='YouTube 频道',enable_manage: bool=True) -> dict:
        return await auth.start('youtube',name=name,enable_manage=enable_manage)


    @server.tool(description='查看本地素材工具和浏览器登录是否就绪；不读取或输出任何凭据。')
    def material_local_status() -> dict:
        ready=bool(env.get('CHATGROWING_MATERIAL_SERVICE_ORIGIN') and env.get('CHATGROWING_MATERIAL_HOST_ACCESS_TOKEN'))
        return {'inspection':'available','transfer_auth':('injected_unverified' if ready else ('local_user_session' if auth.tokens else 'host_auth_required')),
            'requires_user_token_in_chat':False,'authorization_status':auth.status,'authorization_error':auth.last_error}

    @server.tool(description='实际读取用户指定的本地视频/图片并检查，返回素材登记需要的manifest。不要编造路径；不保存副本，不上传媒体。')
    async def material_local_inspect(path: str) -> dict:
        try:
            manifest=await asyncio.to_thread(source_manifest,path,inspector=inspector)
            # Prevent large checksum lists from consuming the model context. The
            # authenticated local registration path sends large manifests directly.
            if len(manifest['chunk_sha256'])>256:
                return {'error':'material_manifest_requires_local_register','byte_size':manifest['byte_size']}
            return {'name':Path(path).name,'manifest':manifest,'server_copy':False}
        except MaterialError as exc:return {'error':exc.code}
        except Exception:return {'error':'material_local_inspection_failed'}

    async def call(action,**kwargs):
        token=env.get('CHATGROWING_MATERIAL_HOST_ACCESS_TOKEN','')
        try:
            if not token:token=await auth.access_token()
            async with httpx.AsyncClient(base_url=origin,headers={'Authorization':'Bearer '+token},trust_env=False,
                    timeout=httpx.Timeout(90,connect=10)) as client:
                source=MaterialSourceClient(client)
                return await getattr(source,action)(**kwargs,inspector=inspector)
        except MaterialError as exc:return {'error':exc.code,'requires_user_token_in_chat':False}
        except Exception:return {'error':'material_local_transfer_failed'}

    @server.tool(description='批量登记本地素材，独立返回成功和失败；不上传媒体。先通过 material_local_login 登录，不接受模型传入 token。')
    async def material_local_register(paths: list[str], request_key: str) -> dict:
        return await call('register_many',paths=paths,request_key=request_key)

    @server.tool(description='向ChatGrowing内存转发用户指定原文件的分块，仅推进已经确认的发布任务。不会创建或批准发布，未登录时拒绝。')
    async def material_local_transfer(path: str, distribution_id: str, max_chunks: int=16) -> dict:
        return await call('transfer',path=path,distribution_id=distribution_id,max_chunks=max_chunks)

    return server


if __name__=='__main__':build_server().run(transport='stdio')
