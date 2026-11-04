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

    def add(self, job):
        self.history.append({
            'start': job.start,
            'end': job.end,
            'time': (job.end - job.start).total_seconds() if job.end and job.start else 0,
            'status': job.status
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
        self.stats = NodeStats()
        self.running = False
        self.last = None
        self.retry = 0
        self.nexted = False
        self.last_modified = None

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
        config_outputs = None

        try:
            connected = self.input.connect(self)
            if connected:
                self.model.input = self.input
                config_outputs = self.model.get()
                if config_outputs:
                    status = 'success'
                    self.output.store(self.name, config_outputs, opt={'group': self.group})
                else:
                    status = 'no_connection'
            else:
                status = 'no_connection'
        except Exception as e:
            logger.exception("Error backing up node %s: %s", self.name, e)
            status = 'fail'
        finally:
            try:
                self.input.disconnect()
            except Exception:
                pass
            self.running = False

        now = datetime.datetime.now()
        self.last = {
            'start': now,
            'end': now,
            'status': status,
            'time': 0.1
        }
        if status == 'success':
            self.last_modified = now.isoformat()
        return status == 'success'

    def to_dict(self):
        return {
            'name': self.name,
            'ip': self.ip,
            'model': self.model_name,
            'group': self.group,
            'status': self.last['status'] if self.last else 'never',
            'time': self.last['end'].strftime("%Y-%m-%d %H:%M:%S") if self.last and self.last.get('end') else 'never',
            'last': self.last,
            'mtime': self.last_modified or 'never',
        }
