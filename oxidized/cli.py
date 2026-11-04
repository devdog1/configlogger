import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Oxidized - Network device configuration backup tool")
    parser.add_argument('-d', '--debug', action='store_true', help='turn on debugging')
    parser.add_argument('-1', '--run-once', action='store_true', help='run once and exit')
    parser.add_argument('-c', '--config', help='config file path')
    parser.add_argument('--node', help='run only for specified node')

    args = parser.parse_args()

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oxidized_project.settings')
    try:
        import django
        django.setup()
    except Exception:
        pass

    from oxidized.core import Core

    opts = {
        'debug': args.debug,
        'run_once': args.run_once,
    }
    if args.config:
        opts['config_file'] = args.config

    core = Core(opts)
    if args.node:
        n = core.nodes.get(args.node)
        if not n:
            print(f"Node '{args.node}' not found")
            sys.exit(1)
        res = n.run()
        sys.exit(0 if res else 1)

    core.run()

if __name__ == '__main__':
    main()
