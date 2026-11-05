import os
import glob
import logging
import hashlib
import time
import difflib
from pathlib import Path

logger = logging.getLogger("oxidized.output")

def _get_pg_node_revision_model():
    """Dynamically get the NodeRevision Django model if Django is available."""
    try:
        import django
        from django.apps import apps
        if apps.ready:
            from oxidized_web.models import NodeRevision
            return NodeRevision
    except Exception as e:
        logger.debug("Database NodeRevision model lookup note: %s", e)
    return None

def _save_pg_revision(node_name, group, content, author="Oxidized <oxidized@localhost>", message=""):
    """Save configuration snapshot directly to PostgreSQL database."""
    NodeRevision = _get_pg_node_revision_model()
    if not NodeRevision:
        return None
    group = group or "default"
    try:
        # Avoid duplicate consecutive revisions if content has not changed
        latest = NodeRevision.objects.filter(node_name=node_name, group=group).order_by('-created_at').first()
        if latest and latest.content == content:
            return latest.oid

        ts = int(time.time())
        oid = hashlib.sha1(f"{node_name}:{group}:{ts}:{content}".encode('utf-8')).hexdigest()
        rev = NodeRevision.objects.create(
            node_name=node_name,
            group=group,
            oid=oid,
            author=author,
            message=message or f"update {node_name}",
            content=content
        )
        return rev.oid
    except Exception as e:
        logger.error("Error saving revision to PostgreSQL for %s: %s", node_name, e)
        return None

def _get_pg_versions(node_name, group=None):
    """Retrieve all revisions from PostgreSQL database."""
    NodeRevision = _get_pg_node_revision_model()
    if not NodeRevision:
        return []
    group = group or "default"
    try:
        qs = NodeRevision.objects.filter(node_name=node_name).order_by('-created_at')
        if group and group != 'default':
            qs = qs.filter(group=group)
        versions = []
        for r in qs:
            versions.append({
                'oid': r.oid,
                'time': int(r.created_at.timestamp()),
                'date': r.created_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
                'author': r.author,
                'message': r.message
            })
        return versions
    except Exception as e:
        logger.debug("Error querying PostgreSQL revisions: %s", e)
        return []

def _get_pg_version_content(node_name, group=None, oid=None):
    """Retrieve full content of a specific revision from PostgreSQL."""
    NodeRevision = _get_pg_node_revision_model()
    if not NodeRevision:
        return ""
    group = group or "default"
    try:
        qs = NodeRevision.objects.filter(node_name=node_name)
        if group and group != 'default':
            qs = qs.filter(group=group)
        if oid:
            rev = qs.filter(oid__startswith=oid).first()
        else:
            rev = qs.order_by('-created_at').first()
        return rev.content if rev else ""
    except Exception as e:
        logger.debug("Error getting revision content from PostgreSQL: %s", e)
        return ""

def _get_pg_diff(node_name, group=None, oid1=None, oid2=None):
    """Generate git-style unified diff using revisions stored in PostgreSQL."""
    v1_text = _get_pg_version_content(node_name, group, oid1)
    v2_text = _get_pg_version_content(node_name, group, oid2)
    diff = difflib.unified_diff(
        v1_text.splitlines(keepends=True),
        v2_text.splitlines(keepends=True),
        fromfile=f"{node_name} ({oid1[:8] if oid1 else 'initial'})",
        tofile=f"{node_name} ({oid2[:8] if oid2 else 'current'})"
    )
    return "".join(diff)


class Output:
    def __init__(self, cfg=None):
        self.cfg = cfg or {}

    def setup(self):
        pass

    def store(self, node_name, outputs, opt=None):
        raise NotImplementedError

    def fetch(self, node_name, group=None):
        raise NotImplementedError

    def version(self, node_name, group=None):
        return _get_pg_versions(node_name, group)

    def get_version(self, node_name, group=None, oid=None):
        return _get_pg_version_content(node_name, group, oid)

    def get_diff(self, node_name, group=None, oid1=None, oid2=None):
        return _get_pg_diff(node_name, group, oid1, oid2)


class DatabaseOutput(Output):
    """Stores backups and revision history directly in the PostgreSQL database."""
    def store(self, node_name, outputs, opt=None):
        opt = opt or {}
        if opt.get('significant_changes') is False:
            return False
        group = opt.get('group') or 'default'
        content = outputs.to_cfg() if hasattr(outputs, 'to_cfg') else str(outputs)
        author = f"{opt.get('user') or 'Oxidized'} <{opt.get('email') or 'oxidized@localhost'}>"
        msg = opt.get('msg') or f"backup {node_name}"
        oid = _save_pg_revision(node_name, group, content, author=author, message=msg)
        return oid

    def fetch(self, node_name, group=None):
        return _get_pg_version_content(node_name, group=group)

    def version(self, node_name, group=None):
        return _get_pg_versions(node_name, group)

    def get_version(self, node_name, group=None, oid=None):
        return _get_pg_version_content(node_name, group, oid)

    def get_diff(self, node_name, group=None, oid1=None, oid2=None):
        return _get_pg_diff(node_name, group, oid1, oid2)


class FileOutput(Output):
    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.directory = os.path.expanduser(self.cfg.get('directory', '~/.config/oxidized/configs'))
        os.makedirs(self.directory, exist_ok=True)

    def _get_path(self, node_name, group=None):
        if group and group != 'default':
            dir_path = os.path.join(self.directory, group)
        else:
            dir_path = self.directory
        os.makedirs(dir_path, exist_ok=True)
        return os.path.join(dir_path, node_name)

    def store(self, node_name, outputs, opt=None):
        opt = opt or {}
        if opt.get('significant_changes') is False:
            return False
        group = opt.get('group')
        path = self._get_path(node_name, group)
        content = outputs.to_cfg() if hasattr(outputs, 'to_cfg') else str(outputs)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        # Always mirror revision into local PostgreSQL DB
        _save_pg_revision(node_name, group, content, message=opt.get('msg') or f"update {node_name}")
        return path

    def fetch(self, node_name, group=None):
        path = self._get_path(node_name, group)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()

        matches = glob.glob(os.path.join(self.directory, '**', node_name), recursive=True)
        if matches and os.path.isfile(matches[0]):
            with open(matches[0], 'r', encoding='utf-8') as f:
                return f.read()
        return _get_pg_version_content(node_name, group)

    def version(self, node_name, group=None):
        return _get_pg_versions(node_name, group)

    def get_version(self, node_name, group=None, oid=None):
        if oid:
            return _get_pg_version_content(node_name, group, oid)
        return self.fetch(node_name, group) or ""

    def get_diff(self, node_name, group=None, oid1=None, oid2=None):
        return _get_pg_diff(node_name, group, oid1, oid2)


class GitOutput(Output):
    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.repo_path = os.path.expanduser(self.cfg.get('repo', '~/.config/oxidized/oxidized.git'))
        self.user = self.cfg.get('user', 'Oxidized')
        self.email = self.cfg.get('email', 'o@example.com')
        self._ensure_repo()

    def _ensure_repo(self):
        from dulwich import porcelain
        from dulwich.repo import Repo
        os.makedirs(self.repo_path, exist_ok=True)
        try:
            self.repo = Repo(self.repo_path)
        except Exception:
            self.repo = porcelain.init(self.repo_path)

    def _get_rel_path(self, node_name, group=None):
        if group and group != 'default':
            return f"{group}/{node_name}"
        return node_name

    def store(self, node_name, outputs, opt=None):
        from dulwich import porcelain
        opt = opt or {}
        rel_path = self._get_rel_path(node_name, opt.get('group'))
        full_path = os.path.join(self.repo_path, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        content = outputs.to_cfg() if hasattr(outputs, 'to_cfg') else str(outputs)
        with open(full_path, 'wb') as f:
            f.write(content.encode('utf-8'))

        porcelain.add(self.repo_path, paths=[rel_path])
        author = f"{opt.get('user') or self.user} <{opt.get('email') or self.email}>"
        msg = opt.get('msg') or f"update {node_name}"
        try:
            porcelain.commit(self.repo_path, message=msg.encode('utf-8'), author=author.encode('utf-8'))
        except Exception as e:
            logger.debug("Git commit note: %s", e)

        # Mirror revision into local PostgreSQL DB
        _save_pg_revision(node_name, opt.get('group'), content, author=author, message=msg)
        return full_path

    def fetch(self, node_name, group=None):
        rel_path = self._get_rel_path(node_name, group)
        full_path = os.path.join(self.repo_path, rel_path)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        return _get_pg_version_content(node_name, group)

    def version(self, node_name, group=None):
        # Prefer PostgreSQL revisions, fallback to Dulwich repo walker
        pg_vers = _get_pg_versions(node_name, group)
        if pg_vers:
            return pg_vers

        rel_path = self._get_rel_path(node_name, group)
        versions = []
        try:
            walker = self.repo.get_walker(paths=[rel_path.encode('utf-8')])
            for entry in walker:
                commit = entry.commit
                versions.append({
                    'oid': commit.id.decode('ascii'),
                    'time': commit.commit_time,
                    'date': str(commit.commit_time),
                    'author': commit.author.decode('utf-8', errors='replace'),
                    'message': commit.message.decode('utf-8', errors='replace').strip()
                })
        except Exception as e:
            logger.debug("Error getting versions: %s", e)
        return versions

    def get_version(self, node_name, group=None, oid=None):
        if not oid:
            return self.fetch(node_name, group) or ""
        # Check PostgreSQL first
        pg_content = _get_pg_version_content(node_name, group, oid)
        if pg_content:
            return pg_content

        rel_path = self._get_rel_path(node_name, group)
        try:
            commit = self.repo[oid.encode('ascii')]
            tree = self.repo[commit.tree]
            parts = rel_path.split('/')
            curr = tree
            for part in parts:
                entry = curr[part.encode('utf-8')]
                curr = self.repo[entry[1]]
            return curr.data.decode('utf-8', errors='replace')
        except Exception as e:
            logger.debug("Error getting commit version: %s", e)
            return ""

    def get_diff(self, node_name, group=None, oid1=None, oid2=None):
        v1_text = self.get_version(node_name, group, oid1)
        v2_text = self.get_version(node_name, group, oid2)
        diff = difflib.unified_diff(
            v1_text.splitlines(keepends=True),
            v2_text.splitlines(keepends=True),
            fromfile=f"{node_name} ({oid1[:8] if oid1 else 'initial'})",
            tofile=f"{node_name} ({oid2[:8] if oid2 else 'current'})"
        )
        return "".join(diff)


OUTPUT_REGISTRY = {
    'file': FileOutput,
    'git': GitOutput,
    'db': DatabaseOutput,
    'postgres': DatabaseOutput,
    'postgresql': DatabaseOutput,
}

def resolve_output(name, cfg=None):
    norm_name = str(name).strip().lower()
    cls = OUTPUT_REGISTRY.get(norm_name, FileOutput)
    return cls(cfg)
