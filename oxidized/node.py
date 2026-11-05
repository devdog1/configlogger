import ipaddress
import socket
import logging
import datetime
from oxidized.config import Config
from oxidized.model import resolve_model
from oxidized.input import resolve_input
from oxidized.output import resolve_output

logger = logging.getLogger("oxidized.node")

class NodeStats:
    def __init__(self):
        self.history = []

    def add(self, start, end, status, error=None):
        self.history.append({
            'start': start,
            'end': end,
            'time': round((end - start).total_seconds(), 2) if end and start else 0,
            'status': status,
            'error': error
        })
        if len(self.history) > 10:
            self.history.pop(0)


class Node:
    def __init__(self, opt):
        self.opt = opt
        self.name = opt['name']
        self.group = opt.get('group') or 'default'
        self.model_name = opt.get('model') or Config.current().model or 'ios'
        self.model_class = resolve_model(self.model_name)
        self.model = self.model_class(node=self)

        ip_raw = opt.get('ip') or self.name
        self.ip = self._resolve_ip(ip_raw)

        self.auth = {
            'username': opt.get('username') or Config.current().username,
            'password': opt.get('password') or Config.current().password,
        }
        self.vars = dict(Config.current().vars or {})
        self.vars.update(opt.get('vars') or {})

        input_type = opt.get('input') or Config.current().input.default.split(',')[0].strip()
        self.input_class = resolve_input(input_type)
        self.input = self.input_class(cfg=Config.current().input)

        output_type = opt.get('output') or Config.current().output.default
        self.output = resolve_output(output_type, cfg=getattr(Config.current().output, output_type, {}))

        self.timeout = int(opt.get('timeout') or Config.current().timeout or 20)
        self.retries = int(opt.get('retries') or Config.current().retries or 3)
        self.stats = NodeStats()
        self.running = False
        self.last = None
        self.attempts = opt.get('attempts', 0)
        self.last_error = opt.get('last_error') or None
        self.nexted = False
        self.last_modified = opt.get('mtime') if opt.get('mtime') != 'never' else None
        self.initial_status = opt.get('status') or 'never'
        self.initial_time = opt.get('time') or 'never'

    def _resolve_ip(self, ip_str):
        if '/' in ip_str:
            ip_str = ip_str.split('/')[0]
        try:
            return str(ipaddress.ip_address(ip_str))
        except ValueError:
            pass

        if Config.current().resolve_dns:
            try:
                return socket.gethostbyname(ip_str)
            except Exception:
                pass
        return ip_str

    def run(self):
        self.running = True
        status = 'fail'
        start_time = datetime.datetime.now()
        error_msg = None
        max_attempts = max(1, self.retries)

        for attempt in range(1, max_attempts + 1):
            self.attempts = attempt
            try:
                connected = self.input.connect(self)
                if connected:
                    self.model.input = self.input
                    config_outputs = self.model.get()
                    if config_outputs:
                        status = 'success'
                        self.last_error = None
                        self.output.store(self.name, config_outputs, opt={'group': self.group})
                        break
                    else:
                        status = 'no_connection'
                        error_msg = f"Attempt {attempt}/{max_attempts}: Commands produced no output"
                else:
                    status = 'no_connection'
                    error_msg = f"Attempt {attempt}/{max_attempts}: Connection refused or timed out"
            except Exception as e:
                logger.exception("Error backing up node %s: %s", self.name, e)
                status = 'fail'
                error_msg = f"Attempt {attempt}/{max_attempts}: {str(e)}"
            finally:
                try:
                    self.input.disconnect()
                except Exception:
                    pass

        self.running = False
        end_time = datetime.datetime.now()

        if status != 'success':
            self.last_error = error_msg or f"Failed after {self.attempts} attempts"

        self.last = {
            'start': start_time,
            'end': end_time,
            'status': status,
            'time': round((end_time - start_time).total_seconds(), 2),
            'error': self.last_error
        }
        self.stats.add(start_time, end_time, status, error=self.last_error)

        if status == 'success':
            self.last_modified = end_time.strftime("%Y-%m-%d %H:%M:%S")

        self._persist_status_to_db(status, start_time, end_time)
        return status == 'success'

    def _persist_status_to_db(self, status, start_time, end_time):
        """Persist node execution status and timestamps to PostgreSQL database."""
        try:
            import django
            from django.apps import apps
            if apps.ready:
                from django.utils import timezone
                from oxidized_web.models import Device
                device, created = Device.objects.get_or_create(
                    name=self.name,
                    defaults={
                        'ip': self.ip,
                        'model': self.model_name,
                        'group': self.group or 'default',
                        'output_type': 'db',
                    }
                )
                device.last_status = status
                device.last_error = self.last_error or ""
                device.attempts = self.attempts
                device.last_update = timezone.now()
                if status == 'success':
                    device.last_changed = timezone.now()
                device.save(update_fields=['last_status', 'last_error', 'attempts', 'last_update', 'last_changed'])
        except Exception as e:
            logger.debug("Could not persist status to DB for %s: %s", self.name, e)

    def to_dict(self):
        status = self.last['status'] if self.last else getattr(self, 'initial_status', 'never')
        time_val = (self.last['end'].strftime("%Y-%m-%d %H:%M:%S")
                    if self.last and self.last.get('end')
                    else getattr(self, 'initial_time', 'never'))
        mtime_val = self.last_modified or 'never'

        input_driver_name = getattr(self.input, 'name', 'ssh') if hasattr(self, 'input') else 'ssh'
        output_name = getattr(self.opt, 'get', lambda k, d=None: d)('output', 'db')

        return {
            'name': self.name,
            'ip': self.ip,
            'model': self.model_name,
            'model_name': self.model_name,
            'group': self.group,
            'input': input_driver_name,
            'input_driver': input_driver_name,
            'output': output_name,
            'output_type': output_name,
            'timeout': self.timeout,
            'retries': self.retries,
            'status': status,
            'time': time_val,
            'last': self.last,
            'mtime': mtime_val,
            'attempts': self.attempts,
            'last_error': self.last_error,
            'history': self.stats.history,
            'ssh_kex': self.opt.get('ssh_kex', ''),
            'ssh_hostkey': self.opt.get('ssh_hostkey', ''),
            'ssh_ciphers': self.opt.get('ssh_ciphers', ''),
        }
