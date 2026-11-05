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
    parser.add_argument('--cli-cmd', '--exec-cmd', dest='cli_cmd', help='CLI/Linux executable command template to fetch config (e.g. "sshpass -p \'{password}\' ssh {user}@{host} cat /etc/config")')
    parser.add_argument('--input', help='input driver to use (ssh, telnet, cli, exec, mock)')
    parser.add_argument('--host', help='target device hostname or IP for direct execution')
    parser.add_argument('--username', '-u', help='username variable for authentication')
    parser.add_argument('--password', '-p', help='password variable for authentication')
    parser.add_argument('--model', '-m', help='device model OS type')
    parser.add_argument('--group', '-g', help='device group')
    parser.add_argument('--output', '-o', help='output driver (file, git, db)')
    parser.add_argument('--var', action='append', help='custom variable in KEY=VALUE format (can be specified multiple times)')

    args = parser.parse_args()

    import logging
    logger = logging.getLogger("oxidized.cli")
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

    # Parse custom vars if provided
    custom_vars = {}
    if args.var:
        for v_pair in args.var:
            if '=' in v_pair:
                k, v = v_pair.split('=', 1)
                custom_vars[k.strip()] = v.strip()

    # If --host or ad-hoc node execution requested from CLI:
    if args.host:
        from oxidized.node import Node
        node_name = args.node or args.host
        node_opt = {
            'name': node_name,
            'ip': args.host,
            'model': args.model or 'ios',
            'group': args.group or 'default',
            'username': args.username,
            'password': args.password,
            'input': args.input or ('cli' if args.cli_cmd else 'ssh'),
            'output': args.output or 'db',
            'cli_cmd': args.cli_cmd,
            'vars': custom_vars,
        }
        node = Node(node_opt)
        logger.info("Executing ad-hoc backup for node %s via %s (cli_cmd: %s)", node.name, node.input.name, args.cli_cmd)
        success = node.run()
        print(f"Node backup {'succeeded' if success else 'failed'}")
        sys.exit(0 if success else 1)

    core = Core(opts)
    if args.node:
        n = core.nodes.get(args.node)
        if not n:
            print(f"Node '{args.node}' not found")
            sys.exit(1)
        if args.cli_cmd:
            n.cli_cmd = args.cli_cmd
        if args.input:
            from oxidized.input import resolve_input
            n.input_class = resolve_input(args.input)
            n.input = n.input_class(cfg={})
        if args.username:
            n.auth['username'] = args.username
        if args.password:
            n.auth['password'] = args.password
        if custom_vars:
            n.vars.update(custom_vars)
        res = n.run()
        sys.exit(0 if res else 1)

    core.run()

if __name__ == '__main__':
    main()
