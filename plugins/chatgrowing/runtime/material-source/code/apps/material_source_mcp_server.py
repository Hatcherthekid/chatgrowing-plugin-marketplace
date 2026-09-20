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
from shared.material_source.client import MaterialSourceClient, source_manifest


def build_server(*, environ=None, inspector=None):
    env=os.environ if environ is None else environ
    server=FastMCP('chatgrowing-material-local')
    origin=env.get('CHATGROWING_MATERIAL_SERVICE_ORIGIN') or 'https://chatgrowing.com'
    prepared={}

    @server.tool(description='查看本地文件检查与交接能力；不登录，不读取 OAuth 凭据。企业身份由远程 ChatGrowing Gateway 提供。')
    def material_local_status() -> dict:
        return {'inspection':'available','transfer_auth':'gateway_file_handoff',
            'requires_user_token_in_chat':False,'requires_local_login':False}

    @server.tool(description='实际检查用户指定的本地文件，并准备只绑定该文件的交接。将返回的 proof_digest、manifest_digest、name 交给远程 material_local_handoff。文件不会上传，证明密钥只保留在本地进程内。')
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

    @server.tool(description='使用远程 material_local_handoff 返回的登记交接 ID 登记已检查文件；不上传视频，不要求第二次登录。')
    async def material_local_register(preparation_id: str, handoff_id: str) -> dict:
        return await call('register',preparation_id,handoff_id,request_key=handoff_id)

    @server.tool(description='使用远程 material_local_handoff 返回的传输交接 ID 推进已确认上传任务；只读取已检查文件，不创建或批准任务。可重复调用继续传输。')
    async def material_local_transfer(preparation_id: str, handoff_id: str, distribution_id: str, max_chunks: int=16) -> dict:
        return await call('transfer',preparation_id,handoff_id,distribution_id=distribution_id,max_chunks=max_chunks)

    return server


if __name__=='__main__':build_server().run(transport='stdio')
