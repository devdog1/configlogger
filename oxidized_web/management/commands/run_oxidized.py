from django.core.management.base import BaseCommand
from oxidized.core import Core

class Command(BaseCommand):
    help = "Run the Oxidized network device backup daemon"

    def add_arguments(self, parser):
        parser.add_argument('--run-once', action='store_true', help='Run backup once for all nodes and exit')
        parser.add_argument('--debug', action='store_true', help='Enable debug logging')
        parser.add_argument('--node', type=str, help='Run backup only for a specific node')
        parser.add_argument('--cli-cmd', '--exec-cmd', dest='cli_cmd', type=str, help='CLI/Linux command template (e.g. "sshpass -p \'{password}\' ssh {user}@{host} cat /etc/config")')
        parser.add_argument('--input', type=str, help='Input driver (ssh, telnet, cli, exec, mock)')
        parser.add_argument('--host', type=str, help='Target host or IP address')
        parser.add_argument('--username', '-u', type=str, help='Target username')
        parser.add_argument('--password', '-p', type=str, help='Target password')
        parser.add_argument('--model', '-m', type=str, help='Target OS model')
        parser.add_argument('--group', '-g', type=str, help='Target group')
        parser.add_argument('--output', '-o', type=str, help='Target output')
        parser.add_argument('--var', action='append', help='Custom variable in KEY=VALUE format')

    def handle(self, *args, **options):
        import logging, sys
        if options.get('debug'):
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
            paramiko_logger = logging.getLogger("paramiko")
            paramiko_logger.setLevel(logging.DEBUG)
            if not paramiko_logger.handlers:
                ch = logging.StreamHandler(sys.stderr)
                ch.setLevel(logging.DEBUG)
                ch.setFormatter(logging.Formatter('[paramiko.ssh] %(levelname)s: %(message)s'))
                paramiko_logger.addHandler(ch)
                paramiko_logger.propagate = True

        self.stdout.write(self.style.SUCCESS("Starting Oxidized with PostgreSQL configuration..."))
        opts = {}
        if options.get('run_once'):
            opts['run_once'] = True
        if options.get('debug'):
            opts['debug'] = True

        # Parse vars
        custom_vars = {}
        if options.get('var'):
            for v_pair in options['var']:
                if '=' in v_pair:
                    k, v = v_pair.split('=', 1)
                    custom_vars[k.strip()] = v.strip()

        # Handle direct --host ad-hoc run
        if options.get('host'):
            from oxidized.node import Node
            node_name = options.get('node') or options['host']
            node_opt = {
                'name': node_name,
                'ip': options['host'],
                'model': options.get('model') or 'ios',
                'group': options.get('group') or 'default',
                'username': options.get('username'),
                'password': options.get('password'),
                'input': options.get('input') or ('cli' if options.get('cli_cmd') else 'ssh'),
                'output': options.get('output') or 'db',
                'cli_cmd': options.get('cli_cmd'),
                'vars': custom_vars,
            }
            node = Node(node_opt)
            self.stdout.write(f"Backing up {node.name} ({node.ip}) via {node.input.name}...")
            res = node.run()
            if res:
                self.stdout.write(self.style.SUCCESS(f"Successfully backed up {node.name}"))
            else:
                self.stderr.write(self.style.ERROR(f"Backup failed for {node.name}"))
            return

        core = Core(opts)
        if options.get('node'):
            node = core.nodes.get(options['node'])
            if not node:
                self.stderr.write(f"Node '{options['node']}' not found.")
                return
            if options.get('cli_cmd'):
                node.cli_cmd = options['cli_cmd']
            if options.get('input'):
                from oxidized.input import resolve_input
                node.input_class = resolve_input(options['input'])
                node.input = node.input_class(cfg={})
            if options.get('username'):
                node.auth['username'] = options['username']
            if options.get('password'):
                node.auth['password'] = options['password']
            if custom_vars:
                node.vars.update(custom_vars)
            self.stdout.write(f"Backing up node {node.name}...")
            res = node.run()
            if res:
                self.stdout.write(self.style.SUCCESS(f"Successfully backed up {node.name}"))
            else:
                self.stderr.write(self.style.ERROR(f"Backup failed for {node.name}"))
            return

        core.run()
