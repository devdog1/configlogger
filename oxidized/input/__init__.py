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


class SSHInput(Input):
    name = "ssh"

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.client = None
        self.shell = None
        self.node = None

    def connect(self, node):
        import paramiko
        self.node = node
        username = node.auth.get('username')
        password = node.auth.get('password')
        port = node.vars.get('ssh_port', 22)
        timeout = node.timeout or 20

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.client.connect(
                hostname=node.ip,
                port=port,
                username=username,
                password=password,
                timeout=timeout,
                look_for_keys=False,
                allow_agent=False
            )
            return True
        except Exception as e:
            logger.error("SSH connection failed to %s: %s", node.name, e)
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
