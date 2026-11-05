import logging
import time

logger = logging.getLogger("oxidized.input")

class Input:
    name = "base"

    def __init__(self, cfg=None):
        self.cfg = cfg or {}

    def connect(self, node):
        raise NotImplementedError

    def cmd(self, command):
        raise NotImplementedError

    def disconnect(self):
        pass


class MockInput(Input):
    name = "mock"

    def __init__(self, cfg=None, responses=None):
        super().__init__(cfg)
        self.node = None
        self.responses = responses or {}

    def connect(self, node):
        self.node = node
        return True

    def cmd(self, command):
        if command in self.responses:
            return self.responses[command]
        return f"! Output for command: {command}\n! Host: {self.node.name if self.node else 'node'}\nhostname {self.node.name if self.node else 'node'}\nend"


def _enable_legacy_ssh_algorithms():
    """Register legacy Diffie-Hellman KEX and RSA key algorithms for networking equipment."""
    try:
        import os
        from hashlib import sha1
        import paramiko
        from paramiko import util
        from paramiko.common import byte_mask
        from paramiko.transport import Transport
        from paramiko.kex_group14 import KexGroup14SHA256, b7fffffffffffffff, b0000000000000000
        from paramiko.kex_gex import KexGexSHA256

        class KexGroup14SHA1(KexGroup14SHA256):
            name = "diffie-hellman-group14-sha1"
            hash_algo = sha1

        class KexGroup1SHA1(KexGroup14SHA256):
            P = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE386BFB5A899FA5AE9F24117C4B1FE649286651ECE653ECA1CDF7
            G = 2
            name = "diffie-hellman-group1-sha1"
            hash_algo = sha1

            def _generate_x(self):
                while 1:
                    x_bytes = os.urandom(128)
                    x_bytes = byte_mask(x_bytes[0], 0x7F) + x_bytes[1:]
                    if (
                        x_bytes[:8] != b7fffffffffffffff
                        and x_bytes[:8] != b0000000000000000
                    ):
                        break
                self.x = util.inflate_long(x_bytes)

        class KexGexSHA1(KexGexSHA256):
            name = "diffie-hellman-group-exchange-sha1"
            hash_algo = sha1

        for cls in [KexGroup14SHA1, KexGroup1SHA1, KexGexSHA1]:
            Transport._kex_info[cls.name] = cls
            if cls.name not in Transport._preferred_kex:
                Transport._preferred_kex = Transport._preferred_kex + (cls.name,)

        if 'ssh-rsa' not in Transport._preferred_keys:
            Transport._key_info['ssh-rsa'] = paramiko.rsakey.RSAKey
            Transport._preferred_keys = Transport._preferred_keys + ('ssh-rsa',)
    except Exception as e:
        logger.debug("Legacy SSH algorithm setup note: %s", e)


_enable_legacy_ssh_algorithms()


class SSHInput(Input):
    name = "ssh"

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.client = None
        self.shell = None
        self.node = None

    def connect(self, node):
        import paramiko
        _enable_legacy_ssh_algorithms()
        self.node = node
        username = node.auth.get('username')
        password = node.auth.get('password')
        port = node.vars.get('ssh_port', 22)
        timeout = node.timeout or 20

        # Build custom transport or options based on per-host SSH Kex, HostKey, Ciphers, and Legacy SSH-RSA
        ssh_kex = node.vars.get('ssh_kex') or getattr(node, 'ssh_kex', None)
        ssh_hostkey = node.vars.get('ssh_hostkey') or getattr(node, 'ssh_hostkey', None)
        ssh_ciphers = node.vars.get('ssh_ciphers') or getattr(node, 'ssh_ciphers', None)
        clear_hostkey = node.vars.get('ssh_clear_hostkey') or getattr(node, 'ssh_clear_hostkey', False)
        legacy_rsa = (
            node.vars.get('ssh_legacy_rsa')
            or getattr(node, 'ssh_legacy_rsa', False)
            or node.vars.get('legacy_rsa', False)
        )

        def _parse_algos(val, default_list):
            if not val:
                return default_list
            items = [x.strip() for x in str(val).split(',') if x.strip()]
            res = list(default_list)
            for it in items:
                if it.startswith('+'):
                    algo = it[1:].strip()
                    if algo not in res:
                        res.insert(0, algo)
                elif it.startswith('-'):
                    algo = it[1:].strip()
                    if algo in res:
                        res.remove(algo)
                else:
                    if it not in res:
                        res.insert(0, it)
            return tuple(res)

        class NodeCustomTransport(paramiko.Transport):
            def __init__(self, sock, **kwargs):
                super().__init__(sock, **kwargs)
                sec = self.get_security_options()
                if ssh_kex:
                    sec.kex = _parse_algos(ssh_kex, sec.kex)
                if ssh_hostkey:
                    sec.key_types = _parse_algos(ssh_hostkey, sec.key_types)
                if ssh_ciphers:
                    sec.ciphers = _parse_algos(ssh_ciphers, sec.ciphers)

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # If clear_hostkey is set or default, ensure known host keys don't reject on change
        if clear_hostkey:
            self.client.get_host_keys().clear()

        logger.debug(
            "Initiating SSH connection to %s (%s:%s) with timeout=%ss, kex=%s, hostkey=%s, ciphers=%s, legacy_rsa=%s",
            node.name, node.ip, port, timeout, ssh_kex or 'default', ssh_hostkey or 'default', ssh_ciphers or 'default', legacy_rsa
        )

        disabled_algorithms = None
        if legacy_rsa:
            disabled_algorithms = {
                "keys": [
                    "rsa-sha2-256",
                    "rsa-sha2-512"
                ],
                "pubkeys": [
                    "rsa-sha2-256",
                    "rsa-sha2-512"
                ]
            }

        connect_kwargs = {
            'hostname': node.ip,
            'port': port,
            'username': username,
            'password': password,
            'timeout': timeout,
            'look_for_keys': False,
            'allow_agent': False,
        }
        if disabled_algorithms:
            connect_kwargs['disabled_algorithms'] = disabled_algorithms

        try:
            self.client.connect(
                transport_factory=NodeCustomTransport if (ssh_kex or ssh_hostkey or ssh_ciphers) else None,
                **connect_kwargs
            )
            logger.debug("SSH connection successfully established to %s (%s)", node.name, node.ip)
            return True
        except Exception as e:
            logger.error("SSH connection failed to %s (%s): %s", node.name, node.ip, e)
            return False

    def cmd(self, command):
        if not self.client:
            return False
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=self.node.timeout or 30)
            return stdout.read().decode('utf-8', errors='replace')
        except Exception as e:
            logger.error("SSH command execution '%s' failed on %s: %s", command, self.node.name, e)
            return False

    def disconnect(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None


class TelnetInput(Input):
    name = "telnet"

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.tn = None
        self.node = None

    def connect(self, node):
        import telnetlib
        self.node = node
        port = node.vars.get('telnet_port', 23)
        timeout = node.timeout or 20
        try:
            self.tn = telnetlib.Telnet(node.ip, port, timeout=timeout)
            return True
        except Exception as e:
            logger.error("Telnet connection failed to %s: %s", node.name, e)
            return False

    def cmd(self, command):
        if not self.tn:
            return False
        try:
            self.tn.write(command.encode('ascii') + b"\n")
            time.sleep(0.5)
            return self.tn.read_very_eager().decode('ascii', errors='replace')
        except Exception as e:
            logger.error("Telnet command error on %s: %s", self.node.name, e)
            return False

    def disconnect(self):
        if self.tn:
            try:
                self.tn.close()
            except Exception:
                pass
            self.tn = None


class ExecInput(Input):
    """
    Executes external Linux executables/commands outside of Python.
    Supports interpolating variables into the command string (e.g. {host}, {username}, {password}, etc.)
    and passing them as environment variables (OXIDIZED_HOST, OXIDIZED_USER, OXIDIZED_PASSWORD, etc.).
    """
    name = "exec"

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.node = None

    def connect(self, node):
        self.node = node
        return True

    def _get_context(self, command=None):
        """Prepare interpolation variables and environment variables from node context."""
        if not self.node:
            return {}, {}

        username = (self.node.auth.get('username') or '') if self.node.auth else ''
        password = (self.node.auth.get('password') or '') if self.node.auth else ''
        host = self.node.ip or self.node.name
        port = str(self.node.vars.get('port') or self.node.vars.get('ssh_port') or 22)

        context = {
            'host': host,
            'ip': self.node.ip,
            'name': self.node.name,
            'username': username,
            'user': username,
            'password': password,
            'pass': password,
            'model': self.node.model_name,
            'group': self.node.group or 'default',
            'port': port,
            'command': command or '',
            'cmd': command or '',
        }

        # Add node vars
        for k, v in getattr(self.node, 'vars', {}).items():
            if k not in context:
                context[k] = str(v)

        # Build environment variables with OXIDIZED_ prefix
        import os
        env = os.environ.copy()
        env['OXIDIZED_HOST'] = host
        env['OXIDIZED_IP'] = str(self.node.ip)
        env['OXIDIZED_NAME'] = str(self.node.name)
        env['OXIDIZED_USER'] = str(username)
        env['OXIDIZED_USERNAME'] = str(username)
        env['OXIDIZED_PASSWORD'] = str(password)
        env['OXIDIZED_MODEL'] = str(self.node.model_name)
        env['OXIDIZED_GROUP'] = str(self.node.group or 'default')
        env['OXIDIZED_PORT'] = port
        if command:
            env['OXIDIZED_CMD'] = str(command)
            env['OXIDIZED_COMMAND'] = str(command)

        for k, v in getattr(self.node, 'vars', {}).items():
            env[f"OXIDIZED_VAR_{k.upper()}"] = str(v)

        return context, env

    def interpolate_cmd(self, cmd_template, command=None):
        context, _ = self._get_context(command)
        # Safe string formatting; if a key is missing, leave it as is
        class SafeDict(dict):
            def __missing__(self, key):
                return '{' + key + '}'
        try:
            return cmd_template.format_map(SafeDict(context))
        except Exception:
            return cmd_template

    def cmd(self, command):
        import subprocess
        context, env = self._get_context(command)

        # Check if node or input cfg has a custom cli command template
        template = (
            getattr(self.node, 'cli_cmd', None)
            or (self.node.vars.get('cli_cmd') if self.node else None)
            or (self.cfg.get('cmd') if isinstance(self.cfg, dict) else None)
        )

        if template:
            exec_command = self.interpolate_cmd(template, command)
        else:
            exec_command = self.interpolate_cmd(command, command)

        timeout_val = getattr(self.node, 'timeout', 30) if self.node else 30
        try:
            logger.debug("Executing external command: %s", exec_command)
            res = subprocess.run(
                exec_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=timeout_val or 30
            )
            if res.returncode != 0:
                logger.warning("Exec command '%s' exited with code %s: %s", exec_command, res.returncode, res.stderr)
            return res.stdout
        except Exception as e:
            logger.error("Exec command failed on %s: %s", getattr(self.node, 'name', 'node') if self.node else "node", e)
            return False


class CLIInput(ExecInput):
    """Alias for ExecInput specifically for CLI / external Linux executables."""
    name = "cli"


INPUT_REGISTRY = {
    'ssh': SSHInput,
    'telnet': TelnetInput,
    'exec': ExecInput,
    'cli': CLIInput,
    'mock': MockInput,
}

def resolve_input(name):
    norm_name = str(name).strip().lower()
    return INPUT_REGISTRY.get(norm_name, MockInput)
