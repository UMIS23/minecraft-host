import json
import os
from pathlib import Path

import paramiko

CONFIG_FILE = Path(__file__).parent.parent / "config.json"

DEFAULT_CONFIG = {
    "minecraft_version": "1.20.1",
    "server_type": "vanilla",
    "ram_gb": 4,
    "server_port": 25565,
    "max_players": 20,
    "online_mode": False,
    "view_distance": 10,
    "server_name": "MC Server",
    "enable_rcon": True,
    "ssh_user": "ubuntu",
    "ssh_key_path": "~/.ssh/id_rsa",
    "server_ip": "",
}


def load_config():
    if not CONFIG_FILE.exists():
        return dict(DEFAULT_CONFIG)
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    for key, val in DEFAULT_CONFIG.items():
        config.setdefault(key, val)
    return config


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_server_ip():
    config = load_config()
    return config.get("server_ip")


def is_configured():
    config = load_config()
    return bool(config.get("server_ip"))


def ssh_connect():
    config = load_config()
    ip = get_server_ip()
    if not ip:
        raise Exception("Sunucu IP'si ayarlanmamis. Ayarlardan config.json'i guncelleyin.")

    key_path = Path("/app/key1.pem")
    if not key_path.exists():
        key_path = Path(os.path.expanduser(config.get("ssh_key_path", "~/.ssh/id_rsa")))
    if not key_path.exists():
        key_path = Path("key1.pem")
    if not key_path.exists():
        raise Exception(f"SSH key bulunamadi: {key_path}")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        hostname=ip,
        username=config.get("ssh_user", "ubuntu"),
        key_filename=str(key_path),
        timeout=15
    )
    return ssh


def ssh_exec(ssh, command, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    return exit_code, stdout.read().decode().strip(), stderr.read().decode().strip()


def docker_cmd(cmd):
    return f"docker exec mc {cmd}"


def get_java_tag(mc_version):
    try:
        parts = mc_version.split(".")
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return "java21"

    if minor <= 16:
        return "java17"
    if minor <= 20 and patch <= 4:
        return "java17"
    if minor == 20 and patch >= 5:
        return "java21"
    if minor == 21 and patch <= 4:
        return "java21"
    return "java21"


def build_docker_run(version, server_type, java_tag, memory, port,
                     online_mode, max_players, view_distance,
                     enable_rcon, motd):
    return (
        f"docker rm -f mc 2>/dev/null; "
        f"docker run -d "
        f"--name mc "
        f"--restart unless-stopped "
        f"-p {port}:{port}/tcp "
        f"-p {port}:{port}/udp "
        f"-e EULA=TRUE "
        f"-e VERSION={version} "
        f"-e TYPE={server_type.upper()} "
        f"-e MEMORY={memory}G "
        f"-e ONLINE_MODE={online_mode} "
        f"-e MAX_PLAYERS={max_players} "
        f"-e VIEW_DISTANCE={view_distance} "
        f"-e ENABLE_RCON={enable_rcon} "
        f'-e MOTD="{motd}" '
        f"-v /opt/minecraft/data:/data "
        f"itzg/minecraft-server:{java_tag}"
    )


def get_server_status():
    config = load_config()
    result = {
        "server_ip": get_server_ip(),
        "port": config.get("server_port", 25565),
        "version": config.get("minecraft_version", "1.20.1"),
        "server_type": config.get("server_type", "vanilla"),
        "ram_gb": config.get("ram_gb", 16),
        "max_players": config.get("max_players", 20),
        "online_mode": config.get("online_mode", False),
        "motd": config.get("server_name", "A Cool Server"),
        "container_status": "unknown",
        "resources": None,
        "players": [],
    }

    if not is_configured():
        result["error"] = "Config ayarlanmamis. /settings sayfasindan sunucu IP'sini girin."
        return result

    try:
        ssh = ssh_connect()
        _, status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
        result["container_status"] = status or "not found"

        if status == "running":
            _, resources, _ = ssh_exec(ssh, "docker stats mc --no-stream --format 'CPU: {{.CPUPerc}} | MEM: {{.MemUsage}}' 2>/dev/null")
            result["resources"] = resources

            _, logs, _ = ssh_exec(ssh, docker_cmd("grep -c 'logged in' /data/logs/latest.log 2>/dev/null || echo 0"), timeout=10)
            try:
                result["online_count"] = int(logs)
            except (ValueError, TypeError):
                result["online_count"] = 0

        ssh.close()
    except Exception as e:
        result["error"] = str(e)

    return result
