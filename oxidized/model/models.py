import re
from oxidized.model.model import Model

class IOS(Model):
    _comment = "! "
    _prompt = r'^([\w.@()-]+[#>]\s?)$'

    @classmethod
    def setup_ios(cls):
        def clean_all(self, cfg, cmd=""):
            cfg = re.sub(r"^% Invalid input detected at '\^' marker\.$|^\s+\^$", "", cfg, flags=re.MULTILINE)
            lines = cfg.splitlines()
            if len(lines) >= 2:
                return "\n".join(lines[1:-1])
            return cfg

        def clean_secret(self, cfg, cmd=""):
            cfg = re.sub(r'^(snmp-server community).*', r'\1 <configuration removed>', cfg, flags=re.MULTILINE)
            cfg = re.sub(r'^(enable (password|secret)( level \d+)? \d) .+', r'\1 <secret hidden>', cfg, flags=re.MULTILINE)
            cfg = re.sub(r'^(username .+ (password|secret) \d) .+', r'\1 <secret hidden>', cfg, flags=re.MULTILINE)
            return cfg

        cls.add_all(clean_all)
        cls.add_secret(clean_secret)

        cls.add_cmd("show version", func=lambda self, out: "\n".join(
            f"! {line}" for line in out.splitlines() if not re.search(r"uptime is|reload", line)
        ))
        cls.add_cmd("show running-config")

IOS.setup_ios()


class JunOS(Model):
    _comment = "# "
    _prompt = r'^([\w.-]+@[\w.-]+[>#]\s?)$'

    @classmethod
    def setup_junos(cls):
        cls.add_cmd("show version", func=lambda self, out: "\n".join(f"# {l}" for l in out.splitlines()))
        cls.add_cmd("show configuration")

JunOS.setup_junos()


class EOS(Model):
    _comment = "! "
    _prompt = r'^([\w.@()-]+[#>]\s?)$'

    @classmethod
    def setup_eos(cls):
        cls.add_cmd("show version", func=lambda self, out: "\n".join(f"! {l}" for l in out.splitlines()))
        cls.add_cmd("show running-config")

EOS.setup_eos()
