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

        # Build custom transport or options based on per-host SSH Kex, HostKey, Ciphers
        ssh_kex = node.vars.get('ssh_kex') or getattr(node, 'ssh_kex', None)
        ssh_hostkey = node.vars.get('ssh_hostkey') or getattr(node, 'ssh_hostkey', None)
        ssh_ciphers = node.vars.get('ssh_ciphers') or getattr(node, 'ssh_ciphers', None)
        clear_hostkey = node.vars.get('ssh_clear_hostkey') or getattr(node, 'ssh_clear_hostkey', False)

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
            "Initiating SSH connection to %s (%s:%s) with timeout=%ss, kex=%s, hostkey=%s, ciphers=%s",
            node.name, node.ip, port, timeout, ssh_kex or 'default', ssh_hostkey or 'default', ssh_ciphers or 'default'
        )

        try:
            self.client.connect(
                hostname=node.ip,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
                transport_factory=NodeCustomTransport if (ssh_kex or ssh_hostkey or ssh_ciphers) else None
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
    name = "exec"

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.node = None

    def connect(self, node):
        self.node = node
        return True

    def cmd(self, command):
        import subprocess
        try:
            res = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.node.timeout or 30
            )
            return res.stdout
        except Exception as e:
            logger.error("Exec command failed on %s: %s", self.node.name, e)
            return False


INPUT_REGISTRY = {
    'ssh': SSHInput,
    'telnet': TelnetInput,
    'exec': ExecInput,
    'mock': MockInput,
}

def resolve_input(name):
    norm_name = str(name).strip().lower()
    return INPUT_REGISTRY.get(norm_name, MockInput)
