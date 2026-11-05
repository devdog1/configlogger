import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Oxidized - Network device configuration backup tool")
    parser.add_argument('-d', '--debug', action='store_true', help='turn on debugging')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='increase verbosity (-v, -vv, -vvv for verbose SSH debug)')
    parser.add_argument('-1', '--run-once', action='store_true', help='run once and exit')
    parser.add_argument('-c', '--config', help='config file path')
    parser.add_argument('--node', help='run only for specified node')

    args = parser.parse_args()

    import logging
    # Enable verbose / debug logging
    log_level = logging.INFO
    if args.debug or args.verbose > 0:
        log_level = logging.DEBUG
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        # Enable very verbose Paramiko SSH transport debug logging
        paramiko_logger = logging.getLogger("paramiko")
        paramiko_logger.setLevel(logging.DEBUG)
        if not paramiko_logger.handlers:
            ch = logging.StreamHandler(sys.stderr)
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(logging.Formatter('[paramiko.ssh] %(levelname)s: %(message)s'))
            paramiko_logger.addHandler(ch)
            paramiko_logger.propagate = True
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )

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
