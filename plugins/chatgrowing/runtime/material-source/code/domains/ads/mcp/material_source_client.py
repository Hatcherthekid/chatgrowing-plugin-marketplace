"""Thin Host-side source client. Host supplies authenticated HTTP; no media tokens."""
import hashlib
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

import httpx
from domains.ads.contracts.material_library import MaterialError, digest
from domains.ads.services.material_remote_sources import CHUNK_SIZE, MAX_CHUNKS
from domains.ads.services.material_file_store import FFmpegVideoInspector, LocalMaterialFileStore


def source_manifest(path, *, inspector=None):
    """Inspect original locally; no thumbnail, copy, or persistent sidecar is created."""
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        raise MaterialError('material_source_not_regular',422)
    signature = lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    before = path.stat()
    if not 0 < before.st_size <= CHUNK_SIZE*MAX_CHUNKS:
        raise MaterialError('material_source_size_invalid',422)
    if path.suffix.lower()=='.mp4':
        width,height,duration=(inspector or FFmpegVideoInspector()).inspect(path)
        mime='video/mp4'
    elif path.suffix.lower() in ('.jpg','.jpeg','.png','.webp'):
        width,height,mime=LocalMaterialFileStore._inspect_image(path,path.suffix.lower())
        duration=None
    else:
        raise MaterialError('material_file_invalid',422)
    hashes=[];whole=hashlib.sha256()
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or signature(os.fstat(stream.fileno()))!=signature(before):
            raise MaterialError('material_source_changed')
        for data in iter(lambda:stream.read(CHUNK_SIZE),b''):
            whole.update(data);hashes.append(hashlib.sha256(data).hexdigest())
        if signature(os.fstat(stream.fileno()))!=signature(before) or signature(path.stat())!=signature(before):
            raise MaterialError('material_source_changed')
    return {'sha256':whole.hexdigest(),'byte_size':before.st_size,'width':width,'height':height,
        'duration':duration,'mime':mime,'chunk_sha256':hashes}


class MaterialSourceClient:
    def __init__(self, client):
        # Credentials belong to the configured ChatGrowing origin only.
        origin=urlsplit(str(client.base_url))
        if (origin.username or origin.password or origin.query or origin.fragment or origin.path not in ('','/')
                or not (origin.scheme=='https' or origin.scheme=='http' and origin.hostname in ('127.0.0.1','localhost','::1'))):
            raise MaterialError('material_service_origin_invalid',422)
        self.client=client

    async def _request(self, method, path, **kwargs):
        try:
            response=await self.client.request(method,path,follow_redirects=False,**kwargs)
        except httpx.HTTPError:
            # The next call reuses the distribution and queries media progress.
            raise MaterialError('material_transfer_result_unknown',502) from None
        if response.status_code!=200:
            raise MaterialError('material_transfer_rejected',response.status_code)
        try:return response.json()
        except ValueError:raise MaterialError('material_transfer_receipt_invalid',502) from None

    async def register(self, path, *, request_key, inspector=None):
        import asyncio
        manifest=await asyncio.to_thread(source_manifest,path,inspector=inspector)
        receipt=await self._request('POST','/v1/materials/files/remote-reference',json={
            'name':Path(path).name,'request_key':request_key,'manifest':manifest})
        if receipt.get('source_kind')!='remote_reference' or receipt.get('server_copy') is not False:
            raise MaterialError('material_transfer_receipt_invalid',502)
        return receipt

    async def register_many(self, paths, *, request_key, inspector=None):
        if not isinstance(paths,(list,tuple)) or not 1<=len(paths)<=100:
            raise MaterialError('material_source_batch_invalid',422)
        from domains.ads.contracts.material_library import bounded_text
        bounded_text(request_key,limit=128)
        results=[]
        for index,path in enumerate(paths):
            try:
                receipt=await self.register(path,request_key=digest({'batch':request_key,'index':index}),inspector=inspector)
                results.append({'index':index,'name':Path(path).name,'receipt':receipt})
            except MaterialError as exc:
                results.append({'index':index,'name':Path(path).name,'error':exc.code})
        return {'items':results,'registered':sum('receipt' in x for x in results)}

    async def transfer(self, path, distribution_id, *, max_chunks=16, inspector=None):
        """Bounded pump of an already authorized task. Repeat to continue; no enqueue."""
        import asyncio
        if not isinstance(distribution_id,str) or not re.fullmatch('[A-Za-z0-9_-]{1,200}',distribution_id):
            raise MaterialError('material_distribution_invalid',422)
        if type(max_chunks) is not int or not 1<=max_chunks<=256:raise MaterialError('material_chunk_limit_invalid',422)
        manifest=await asyncio.to_thread(source_manifest,path,inspector=inspector)
        base='/v1/materials/transfers/'+distribution_id
        result=await self._request('GET',base)
        def validate_progress(result):
            if (result.get('distribution_id')!=distribution_id or result.get('manifest_digest')!=digest(manifest)
                    or result.get('chunk_size')!=CHUNK_SIZE or result.get('byte_size')!=manifest['byte_size']):
                raise MaterialError('material_source_changed')
        for _ in range(max_chunks):
            validate_progress(result)
            if result['intent_state'] in ('succeeded','failed','cancelled','closed_data_purged','processing'):
                return result
            if result.get('next_attempt_at',0)>result.get('server_time',0):return result
            offset=result.get('next_offset')
            if type(offset) is not int or offset<0 or offset%CHUNK_SIZE or offset>=manifest['byte_size']:
                return result  # Complete bytes await the persistent worker's receipt/readback.
            def read():
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
                with os.fdopen(fd,'rb') as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise MaterialError('material_source_not_regular')
                    stream.seek(offset);return stream.read(CHUNK_SIZE)
            data=await asyncio.to_thread(read)
            if hashlib.sha256(data).hexdigest()!=manifest['chunk_sha256'][offset//CHUNK_SIZE]:
                raise MaterialError('material_source_changed')
            result=await self._request('PUT',base+'/chunks/'+str(offset),content=data,
                headers={'Content-Type':'application/octet-stream','Content-Length':str(len(data))})
        validate_progress(result)
        return result
