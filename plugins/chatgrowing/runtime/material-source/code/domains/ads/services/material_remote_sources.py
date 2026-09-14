"""Host-declared file manifests and request-scoped bytes; never store media bytes."""
import hashlib
import json
import math
import re
from domains.ads.contracts.material_library import MaterialError, digest, encode
from .material_file_store import FileDescriptor

CHUNK_SIZE = 4 * 1024 * 1024
MAX_CHUNKS = 16384


class MaterialRemoteSources:
    def __init__(self, library):
        self.library, self.store = library, library.store

    def get_in(self, conn, org, file_id):
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='material_remote_sources'").fetchone():
            return None
        row = conn.execute('SELECT * FROM material_remote_sources WHERE organization_id=? AND file_id=?', (org, file_id)).fetchone()
        return dict(row) if row else None

    def register(self, actor, *, name, request_key, manifest):
        self.library.require_contribution(actor); actor.require('materials.read')
        self.validate(manifest)
        from pathlib import Path
        suffix_mime={'.mp4':'video/mp4','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}
        if not isinstance(name,str) or suffix_mime.get(Path(name).suffix.lower())!=manifest['mime']:
            raise MaterialError('material_source_manifest_invalid',422)
        if len(manifest['chunk_sha256'])==1 and manifest['chunk_sha256'][0]!=manifest['sha256']:
            raise MaterialError('material_source_manifest_invalid',422)
        # Bind the complete immutable manifest to the existing reservation key.
        receipt = self.library.begin_file(actor, name=name, byte_size=manifest['byte_size'],
            idempotency_key=request_key, reference=True, remote_manifest_digest=digest(manifest))
        with self.store.transaction() as conn:
            row = self.library._file(conn, actor.organization_id, receipt['file_id'])
            if row['retention_state'] != 'retained':
                raise MaterialError('material_file_deleted', 410)
            old = self.get_in(conn, actor.organization_id, receipt['file_id'])
            if old and old['manifest_json'] != encode(manifest):
                raise MaterialError('material_file_idempotency_conflict')
            if not old:
                conn.execute('INSERT INTO material_remote_sources VALUES (?,?,?,?,?)',
                    (actor.organization_id, receipt['file_id'], encode(manifest), actor.membership_id, self.store.now()))
        if row['validation_state'] != 'passed':
            self.library.finalize_file(actor, receipt['file_id'], FileDescriptor(**{
                k: manifest[k] for k in ('sha256','byte_size','width','height','duration','mime')}), generate_preview=False)
        return {k:receipt[k] for k in ('material_id','revision_id','file_id')} | {
            'state':'registered', 'source_kind':'remote_reference', 'server_copy':False,
            'validation_origin':'host_declared', 'chunk_size':CHUNK_SIZE}

    @staticmethod
    def validate(manifest):
        fields = {'sha256','byte_size','width','height','duration','mime','chunk_sha256'}
        valid_hash = lambda v: isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) is not None
        if not isinstance(manifest, dict) or set(manifest) != fields:
            raise MaterialError('material_source_manifest_invalid', 422)
        size = manifest['byte_size']; hashes = manifest['chunk_sha256']
        if (type(size) is not int or not 0 < size <= CHUNK_SIZE * MAX_CHUNKS
                or not valid_hash(manifest['sha256']) or not isinstance(hashes, list)
                or len(hashes) != (size + CHUNK_SIZE - 1)//CHUNK_SIZE or not all(map(valid_hash, hashes))
                or any(type(manifest[k]) is not int or not 0 < manifest[k] <= 65536 for k in ('width','height'))
                or manifest['mime'] not in ('video/mp4','image/jpeg','image/png','image/webp')):
            raise MaterialError('material_source_manifest_invalid', 422)
        duration = manifest['duration']
        if manifest['mime'] == 'video/mp4':
            if type(duration) not in (int,float) or not math.isfinite(duration) or duration <= 0:
                raise MaterialError('material_source_manifest_invalid', 422)
        elif duration is not None:
            raise MaterialError('material_source_manifest_invalid', 422)

    def chunk_reader(self, actor, file_id, *, offset, data):
        actor.require('materials.read'); actor.require('materials.distribute')
        with self.store.transaction(write=False) as conn:
            file = self.library._file(conn, actor.organization_id, file_id)
            source = self.get_in(conn, actor.organization_id, file_id)
        if not source or file['retention_state'] != 'retained' or file['validation_state'] != 'passed':
            raise MaterialError('material_source_unavailable')
        manifest = json.loads(source['manifest_json'])
        if (type(offset) is not int or offset < 0 or offset % CHUNK_SIZE or offset >= manifest['byte_size']
                or not isinstance(data, bytes) or len(data) != min(CHUNK_SIZE, manifest['byte_size']-offset)):
            raise MaterialError('material_chunk_invalid', 422)
        if hashlib.sha256(data).hexdigest() != manifest['chunk_sha256'][offset//CHUNK_SIZE]:
            raise MaterialError('material_source_chunk_mismatch', 422)

        def read(requested_offset, count):
            if not offset <= requested_offset < offset + len(data):
                raise MaterialError('material_source_chunk_required')
            return data[requested_offset-offset:requested_offset-offset+count]
        return read
