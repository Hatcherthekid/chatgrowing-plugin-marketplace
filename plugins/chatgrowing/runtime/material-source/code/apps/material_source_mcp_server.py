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
from shared.material_source.client import MaterialSourceClient, source_fingerprint, source_stamp


def build_server(*, environ=None, inspector=None):
    env=os.environ if environ is None else environ
    server=FastMCP('chatgrowing-material-local')
    origin=env.get('CHATGROWING_MATERIAL_SERVICE_ORIGIN') or 'https://chatgrowing.com'
    prepared={}
    jobs={}
    job_tasks={}
    job_keys={}
    transfer_slots=asyncio.Semaphore(2)

    @server.tool(description='查看本地文件检查与交接能力；不登录，不读取 OAuth 凭据。企业身份由远程 ChatGrowing Gateway 提供。')
    def material_local_status() -> dict:
        return {'inspection':'available','transfer_auth':'gateway_file_handoff',
            'requires_user_token_in_chat':False,'requires_local_login':False,
            'temporary_server_intake':'available','intake_requires_local_ffmpeg':False}

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

    @server.tool(description='启动本地视频批量接收任务。每项需已检查并取得独立交接 ID；启动后后台持续传输，使用 material_local_intake_batch_status 查询进度。本工具本身不发布到平台。')
    async def material_local_intake_batch_start(items: list[dict]) -> dict:
        try:
            if not isinstance(items, list) or not 1 <= len(items) <= 100:
                raise MaterialError('material_source_batch_invalid', 422)
            for old_id,state in list(jobs.items()):
                if state['state'] != 'running' and time.monotonic() - state['created_at'] > 3600:
                    jobs.pop(old_id,None);job_tasks.pop(old_id,None)
                    job_keys.pop(state['request_digest'],None)
            selected=[]
            seen=set()
            for value in items:
                if not isinstance(value, dict) or set(value) != {'preparation_id', 'handoff_id'}:
                    raise MaterialError('material_source_batch_invalid', 422)
                preparation_id, handoff_id=value['preparation_id'],value['handoff_id']
                if (not isinstance(preparation_id,str) or not isinstance(handoff_id,str)
                        or preparation_id in seen):
                    raise MaterialError('material_source_batch_invalid', 422)
                seen.add(preparation_id)
                item=prepared.get(preparation_id)
                if not item or 'fingerprint' not in item or item['expires'] <= time.monotonic():
                    raise MaterialError('material_local_preparation_expired', 409)
                if await asyncio.to_thread(source_stamp,item['path']) != item['stamp']:
                    raise MaterialError('material_source_changed')
                selected.append((item,handoff_id))
            request_digest=digest(items)
            previous=job_keys.get(request_digest)
            if previous in jobs:
                return {'job_id':previous,'state':jobs[previous]['state'],'item_count':len(selected)}
            if sum(not task.done() for task in job_tasks.values()) >= 4:
                raise MaterialError('material_local_batch_capacity', 429)
            job_id='local_batch_'+secrets.token_hex(16)
            state={'job_id':job_id,'state':'running','created_at':time.monotonic(),
                   'request_digest':request_digest,'items':[
                {'index':index,'name':item['fingerprint']['name'],'state':'queued',
                 'received_bytes':0,'reserved_bytes':item['fingerprint']['byte_size']}
                for index,(item,_) in enumerate(selected)]}
            jobs[job_id]=state
            job_keys[request_digest]=job_id
            async def transfer_one(index,item,handoff_id):
                entry=state['items'][index]
                async def keep_queued_grant_alive():
                    while True:
                        await asyncio.sleep(120)
                        try:
                            async with httpx.AsyncClient(base_url=origin,
                                    headers={'X-Material-Handoff':handoff_id,
                                             'X-Material-Proof':item['proof']},
                                    timeout=httpx.Timeout(30,connect=10)) as client:
                                source=MaterialSourceClient(client,api_prefix='/control/agent-material')
                                await source._request('POST','/v1/materials/intakes/keepalive')
                        except MaterialError as exc:
                            entry['state']='failed';entry['error']=exc.code
                            return
                        except Exception:
                            # A temporary network error must not abandon queued media.
                            # The next heartbeat or actual transfer checks the grant.
                            pass
                heartbeat=asyncio.create_task(keep_queued_grant_alive())
                async with transfer_slots:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat,return_exceptions=True)
                    if entry['state']=='failed': return
                    entry['state']='sending'
                    try:
                        async with httpx.AsyncClient(base_url=origin,
                                headers={'X-Material-Handoff':handoff_id,'X-Material-Proof':item['proof']},
                                timeout=httpx.Timeout(90,connect=10)) as client:
                            source=MaterialSourceClient(client,api_prefix='/control/agent-material')
                            retries=0
                            while True:
                                def progress(receipt):
                                    entry['received_bytes']=receipt.get('received_bytes',entry['received_bytes'])
                                    entry['file_id']=receipt.get('file_id',entry.get('file_id'))
                                    if receipt.get('state')=='ready': entry['state']='ready'
                                try:
                                    receipt=await source.intake(item['path'],max_chunks=256,
                                        expected_fingerprint=item['fingerprint'],expected_stamp=item['stamp'],
                                        on_progress=progress,adaptive_chunks=True)
                                except MaterialError as exc:
                                    if exc.code != 'material_transfer_result_unknown' or retries >= 3:
                                        raise
                                    retries+=1
                                    await asyncio.sleep(2 ** retries)
                                    continue
                                retries=0
                                if receipt.get('state')=='ready':
                                    entry['state']='ready'
                                    entry['material_id']=receipt.get('material_id')
                                    entry['revision_id']=receipt.get('revision_id')
                                    return
                                if (receipt.get('state')!='receiving' or
                                        receipt.get('received_bytes',0)>=item['fingerprint']['byte_size']):
                                    raise MaterialError('material_transfer_receipt_invalid',502)
                    except MaterialError as exc:
                        entry['state']='failed';entry['error']=exc.code
                    except Exception:
                        entry['state']='failed';entry['error']='material_local_transfer_failed'

            async def run_batch():
                await asyncio.gather(*(transfer_one(index,item,handoff_id)
                    for index,(item,handoff_id) in enumerate(selected)))
                state['state']='completed' if all(x['state']=='ready' for x in state['items']) else 'partial_failure'

            job_tasks[job_id]=asyncio.create_task(run_batch())
            return {'job_id':job_id,'state':'running','item_count':len(selected)}
        except MaterialError as exc:
            return {'error':exc.code,'requires_user_token_in_chat':False}

    @server.tool(description='查询本地批量接收任务的逐文件字节进度和接收结果；不返回交接凭证。')
    def material_local_intake_batch_status(job_id: str) -> dict:
        state=jobs.get(job_id)
        if state is None: return {'error':'material_local_batch_not_found'}
        return {'job_id':state['job_id'],'state':state['state'],
                'items':[dict(item) for item in state['items']]}

    return server


if __name__=='__main__':build_server().run(transport='stdio')
