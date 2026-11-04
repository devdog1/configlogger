from django.core.management.base import BaseCommand
from oxidized.core import Core

class Command(BaseCommand):
    help = "Run the Oxidized network device backup daemon"

    def add_arguments(self, parser):
        parser.add_argument('--run-once', action='store_true', help='Run backup once for all nodes and exit')
        parser.add_argument('--debug', action='store_true', help='Enable debug logging')
        parser.add_argument('--node', type=str, help='Run backup only for a specific node')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Oxidized with PostgreSQL configuration..."))
        opts = {}
        if options.get('run_once'):
            opts['run_once'] = True
        if options.get('debug'):
            opts['debug'] = True

        core = Core(opts)
        if options.get('node'):
            node = core.nodes.get(options['node'])
            if not node:
                self.stderr.write(f"Node '{options['node']}' not found.")
                return
            self.stdout.write(f"Backing up node {node.name}...")
            res = node.run()
            if res:
                self.stdout.write(self.style.SUCCESS(f"Successfully backed up {node.name}"))
            else:
                self.stderr.write(self.style.ERROR(f"Backup failed for {node.name}"))
            return

        core.run()
