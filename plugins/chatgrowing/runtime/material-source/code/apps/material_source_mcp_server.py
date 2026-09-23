#!/usr/bin/env python3
"""Local file I/O only. Gateway delegates a single file/task, never OAuth tokens."""
import asyncio
import hashlib
import os
from pathlib import Path
import secrets
import sys
import time

CODE=Path(__file__).resolve().parents[1]
if str(CODE) not in sys.path: sys.path.insert(0,str(CODE))
import httpx
from mcp.server.fastmcp import FastMCP
from shared.material_source.protocol import MaterialError, digest
from shared.material_source.client import MaterialSourceClient, source_manifest, source_fingerprint, source_stamp


def build_server(*, environ=None, inspector=None):
    env=os.environ if environ is None else environ
    server=FastMCP('chatgrowing-material-local')
    origin=env.get('CHATGROWING_MATERIAL_SERVICE_ORIGIN') or 'https://chatgrowing.com'
    prepared={}

    @server.tool(description='查看本地文件检查与交接能力；不登录，不读取 OAuth 凭据。企业身份由远程 ChatGrowing Gateway 提供。')
    def material_local_status() -> dict:
        return {'inspection':'available','transfer_auth':'gateway_file_handoff',
            'requires_user_token_in_chat':False,'requires_local_login':False,
            'temporary_server_intake':'available','intake_requires_local_ffmpeg':False,
            'legacy_direct_video_requires_ffmpeg':True}

    @server.tool(description='旧版本地直传兼容工具；视频需要本机 FFmpeg，新版服务器接收请使用 material_local_intake_inspect。文件不会上传，证明密钥只保留在本地进程内。')
    async def material_local_inspect(path: str) -> dict:
        try:
            for key in list(prepared):
                if prepared[key]['expires'] <= time.monotonic(): del prepared[key]
            if len(prepared)>=100: raise MaterialError('material_local_preparation_limit',409)
            manifest=await asyncio.to_thread(source_manifest,path,inspector=inspector)
            if len(prepared)>=100: raise MaterialError('material_local_preparation_limit',409)
            identifier,proof=secrets.token_urlsafe(24),secrets.token_urlsafe(48)
            prepared[identifier]={'path':str(Path(path).absolute()),'proof':proof,
                'manifest':manifest,'expires':time.monotonic()+900}
            return {'preparation_id':identifier, 'name':Path(path).name,
                'proof_digest':hashlib.sha256(proof.encode()).hexdigest(),
                'manifest_digest':digest(manifest),'byte_size':manifest['byte_size'],
                'mime':manifest['mime'],'server_copy':False}
        except MaterialError as exc:return {'error':exc.code}
        except Exception:return {'error':'material_local_inspection_failed'}

    @server.tool(description='为服务器临时存储模式读取本地 MP4 路径并计算 SHA256；不需要本机 FFmpeg，不上传、不发布。将摘要交给远程 material_local_intake_handoff。')
    async def material_local_intake_inspect(path: str) -> dict:
        try:
            for key in list(prepared):
                if prepared[key]['expires'] <= time.monotonic(): del prepared[key]
            if len(prepared) >= 100: raise MaterialError('material_local_preparation_limit',409)
            stamp=await asyncio.to_thread(source_stamp,path)
            fingerprint=await asyncio.to_thread(source_fingerprint,path)
            if await asyncio.to_thread(source_stamp,path)!=stamp:
                raise MaterialError('material_source_changed')
            identifier,proof=secrets.token_urlsafe(24),secrets.token_urlsafe(48)
            prepared[identifier]={'path':str(Path(path).absolute()),'proof':proof,
                'fingerprint':fingerprint,'stamp':stamp,'expires':time.monotonic()+900}
            return {'preparation_id':identifier,'name':fingerprint['name'],
                'proof_digest':hashlib.sha256(proof.encode()).hexdigest(),
                'sha256':fingerprint['sha256'],'byte_size':fingerprint['byte_size'],
                'server_copy':False,'requires_local_ffmpeg':False}
        except MaterialError as exc:return {'error':exc.code}
        except Exception:return {'error':'material_local_inspection_failed'}

    async def call(action, preparation_id, handoff_id, **kwargs):
        try:
            item=prepared.get(preparation_id)
            if not item or item['expires']<=time.monotonic():
                raise MaterialError('material_local_preparation_expired',409)
            manifest=await asyncio.to_thread(source_manifest,item['path'],inspector=inspector)
            if manifest!=item['manifest']: raise MaterialError('material_source_changed')
            async with httpx.AsyncClient(base_url=origin,
                    headers={'X-Material-Handoff':handoff_id,'X-Material-Proof':item['proof']},
                    timeout=httpx.Timeout(90,connect=10)) as client:
                source=MaterialSourceClient(client,api_prefix='/control/agent-material')
                return await getattr(source,action)(path=item['path'],**kwargs,inspector=inspector)
        except MaterialError as exc:return {'error':exc.code,'requires_user_token_in_chat':False}
        except Exception:return {'error':'material_local_transfer_failed'}

    @server.tool(description='旧版本地直传兼容：使用 material_local_handoff 的交接 ID 登记已检查文件；新视频上传请使用服务器临时接收模式。')
    async def material_local_register(preparation_id: str, handoff_id: str) -> dict:
        return await call('register',preparation_id,handoff_id,request_key=handoff_id)

    @server.tool(description='旧版本地直传兼容：推进已确认上传任务；新版运行包不含本机 FFmpeg，请使用 material_local_intake_transfer。')
    async def material_local_transfer(preparation_id: str, handoff_id: str, distribution_id: str, max_chunks: int=16) -> dict:
        return await call('transfer',preparation_id,handoff_id,distribution_id=distribution_id,max_chunks=max_chunks)

    @server.tool(description='将已哈希的本地 MP4 通过当前企业授权的短期交接传入 ChatGrowing 15 天临时存储；断点续传，不执行 YouTube 上传。需先调用远程 material_local_intake_handoff。')
    async def material_local_intake_transfer(preparation_id: str, handoff_id: str, max_chunks: int=16) -> dict:
        try:
            item=prepared.get(preparation_id)
            if not item or 'fingerprint' not in item or item['expires'] <= time.monotonic():
                raise MaterialError('material_local_preparation_expired',409)
            if await asyncio.to_thread(source_stamp,item['path'])!=item['stamp']:
                raise MaterialError('material_source_changed')
            async with httpx.AsyncClient(base_url=origin,
                    headers={'X-Material-Handoff':handoff_id,'X-Material-Proof':item['proof']},
                    timeout=httpx.Timeout(90,connect=10)) as client:
                source=MaterialSourceClient(client,api_prefix='/control/agent-material')
                return await source.intake(item['path'],max_chunks=max_chunks,
                    expected_fingerprint=item['fingerprint'],expected_stamp=item['stamp'])
        except MaterialError as exc:return {'error':exc.code,'requires_user_token_in_chat':False}
        except Exception:return {'error':'material_local_transfer_failed'}

    return server


if __name__=='__main__':build_server().run(transport='stdio')
