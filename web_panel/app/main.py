import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.ssh_client import (
    load_config, save_config, ssh_connect, ssh_exec, docker_cmd,
    get_server_status, get_java_tag, build_docker_run, get_server_ip,
    is_configured, CONFIG_FILE,
)

app = FastAPI(title="MC Server Panel")

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    status = get_server_status()
    return templates.TemplateResponse("dashboard.html", {"request": request, "status": status})


@app.post("/server/start")
async def server_start():
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    try:
        ssh = ssh_connect()
        ssh_exec(ssh, "docker start mc", timeout=30)
        ssh.close()
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)


@app.post("/server/stop")
async def server_stop():
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    try:
        ssh = ssh_connect()
        ssh_exec(ssh, "docker stop mc", timeout=30)
        ssh.close()
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)


@app.post("/server/restart")
async def server_restart():
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    try:
        ssh = ssh_connect()
        ssh_exec(ssh, "docker restart mc", timeout=60)
        ssh.close()
    except Exception:
        pass
    return RedirectResponse("/", status_code=303)


@app.get("/logs", response_class=HTMLResponse)
async def logs(request: Request, lines: int = 100):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    log_output = ""
    try:
        ssh = ssh_connect()
        _, log_output, _ = ssh_exec(ssh, f"docker logs mc --tail {lines} 2>&1", timeout=15)
        ssh.close()
    except Exception as e:
        log_output = f"Error: {e}"
    return templates.TemplateResponse("logs.html", {"request": request, "logs": log_output, "lines": lines})


@app.get("/mods", response_class=HTMLResponse)
async def mods_page(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    mod_list = []
    try:
        ssh = ssh_connect()
        _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
        if stdout and "No such file" not in stdout:
            mod_list = [m for m in stdout.strip().split("\n") if m.strip().endswith(".jar")]
        ssh.close()
    except Exception:
        pass
    return templates.TemplateResponse("mods.html", {"request": request, "mods": mod_list})


@app.post("/mods/install")
async def mod_install(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    mod_name = form.get("mod_name", "")
    result_msg = ""
    result_type = "info"
    mod_list = []

    if not mod_name:
        result_msg = "Mod adı boş olamaz."
        result_type = "error"
    else:
        try:
            import requests
            config = load_config()
            version = config["minecraft_version"]
            loader = config.get("server_type", "vanilla")

            loader_map = {
                "forge": "forge", "fabric": "fabric", "paper": "paper",
                "spigot": "spigot", "purpur": "purpur",
            }
            modrinth_loader = loader_map.get(loader)

            params = {"query": mod_name, "limit": 5, "index": "relevance"}
            facets = [["project_type:mod"]]
            if version and modrinth_loader:
                facets.append([f"versions:{version}"])
            if modrinth_loader:
                facets.append([f"categories:{modrinth_loader}"])
            params["facets"] = json.dumps(facets)

            resp = requests.get("https://api.modrinth.com/v2/search", params=params, timeout=15)
            resp.raise_for_status()
            hits = resp.json().get("hits", [])

            if not hits:
                result_msg = f"'{mod_name}' için sonuç bulunamadı."
                result_type = "error"
            else:
                top = hits[0]
                project_id = top["slug"] or top["project_id"]
                title = top["title"]

                resp_v = requests.get(f"https://api.modrinth.com/v2/project/{project_id}/version", timeout=15)
                resp_v.raise_for_status()
                all_versions = resp_v.json()

                if modrinth_loader:
                    all_versions = [v for v in all_versions if modrinth_loader in v.get("loaders", [])]
                versions = [v for v in all_versions if version in v.get("game_versions", [])]
                if not versions:
                    prefix = ".".join(version.split(".")[:2])
                    versions = [v for v in all_versions if any(pv.startswith(prefix) for pv in v.get("game_versions", []))]

                if not versions:
                    result_msg = f"{title} için uyumlu versiyon bulunamadı."
                    result_type = "error"
                else:
                    ver_data = versions[0]
                    files = ver_data.get("files", [])
                    if not files:
                        result_msg = "Dosya bulunamadı."
                        result_type = "error"
                    else:
                        primary = next((f for f in files if f.get("primary")), files[0])
                        download_url = primary["url"]
                        filename = primary["filename"]

                        ssh = ssh_connect()
                        ssh_exec(ssh, "sudo mkdir -p /opt/minecraft/data/mods && sudo chmod 777 /opt/minecraft/data/mods")

                        import tempfile
                        r = requests.get(download_url, timeout=60, stream=True)
                        r.raise_for_status()
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jar")
                        for chunk in r.iter_content(chunk_size=8192):
                            tmp.write(chunk)
                        tmp.close()

                        sftp = ssh.open_sftp()
                        sftp.put(tmp.name, f"/opt/minecraft/data/mods/{filename}")
                        sftp.close()
                        os.unlink(tmp.name)

                        _, container_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
                        if container_status == "running":
                            ssh_exec(ssh, "docker restart mc", timeout=60)

                        ssh.close()
                        result_msg = f"{title} yüklendi ve sunucu yeniden başlatıldı."
                        result_type = "success"
        except Exception as e:
            result_msg = f"Hata: {e}"
            result_type = "error"

    try:
        ssh = ssh_connect()
        _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
        if stdout and "No such file" not in stdout:
            mod_list = [m for m in stdout.strip().split("\n") if m.strip().endswith(".jar")]
        ssh.close()
    except Exception:
        pass

    return templates.TemplateResponse("mods.html", {
        "request": request,
        "mods": mod_list,
        "result_msg": result_msg,
        "result_type": result_type,
    })


@app.post("/mods/remove")
async def mod_remove(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    mod_name = form.get("mod_name", "")
    result_msg = ""
    result_type = "info"

    if mod_name:
        try:
            ssh = ssh_connect()
            _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
            if stdout:
                mods = stdout.strip().split("\n")
                matching = [m for m in mods if mod_name.lower() in m.lower()]
                if matching:
                    target = matching[0]
                    ssh_exec(ssh, f"sudo rm /opt/minecraft/data/mods/{target}")
                    _, container_status, _ = ssh_exec(ssh, "docker inspect mc --format '{{.State.Status}}' 2>/dev/null")
                    if container_status == "running":
                        ssh_exec(ssh, "docker restart mc", timeout=60)
                    result_msg = f"{target} kaldırıldı."
                    result_type = "success"
                else:
                    result_msg = f"'{mod_name}' bulunamadı."
                    result_type = "error"
            ssh.close()
        except Exception as e:
            result_msg = f"Hata: {e}"
            result_type = "error"

    mod_list = []
    try:
        ssh = ssh_connect()
        _, stdout, _ = ssh_exec(ssh, "ls /opt/minecraft/data/mods/ 2>/dev/null")
        if stdout and "No such file" not in stdout:
            mod_list = [m for m in stdout.strip().split("\n") if m.strip().endswith(".jar")]
        ssh.close()
    except Exception:
        pass

    return templates.TemplateResponse("mods.html", {
        "request": request,
        "mods": mod_list,
        "result_msg": result_msg,
        "result_type": result_type,
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    config = load_config()
    return templates.TemplateResponse("settings.html", {"request": request, "config": config, "configured": is_configured()})


@app.post("/settings")
async def settings_save(request: Request):
    form = await request.form()
    config = load_config()

    config["minecraft_version"] = form.get("minecraft_version", config.get("minecraft_version", "1.20.1"))
    config["server_type"] = form.get("server_type", config.get("server_type", "vanilla"))
    config["ram_gb"] = int(form.get("ram_gb", config.get("ram_gb", 4)))
    config["max_players"] = int(form.get("max_players", config.get("max_players", 20)))
    config["view_distance"] = int(form.get("view_distance", config.get("view_distance", 10)))
    config["server_name"] = form.get("server_name", config.get("server_name", "MC Server"))
    config["online_mode"] = form.get("online_mode") == "on"
    config["enable_rcon"] = form.get("enable_rcon") == "on"
    config["server_ip"] = form.get("server_ip", config.get("server_ip", ""))
    config["ssh_user"] = form.get("ssh_user", config.get("ssh_user", "ubuntu"))

    save_config(config)

    if not is_configured():
        return RedirectResponse("/settings", status_code=303)

    version = config["minecraft_version"]
    java_tag = get_java_tag(version)
    docker_run = build_docker_run(
        version, config["server_type"], java_tag, config["ram_gb"],
        config["server_port"], str(config["online_mode"]).upper(),
        config["max_players"], config["view_distance"],
        str(config["enable_rcon"]).upper(), config["server_name"]
    )

    try:
        ssh = ssh_connect()
        ssh_exec(ssh, docker_run, timeout=120)
        ssh.close()
    except Exception:
        pass

    return RedirectResponse("/settings", status_code=303)


@app.get("/players", response_class=HTMLResponse)
async def players_page(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    ops = []
    whitelist = []
    bans = []
    try:
        ssh = ssh_connect()
        _, ops_out, _ = ssh_exec(ssh, docker_cmd("cat /data/ops.json 2>/dev/null || echo '[]'"), timeout=10)
        try:
            ops_data = json.loads(ops_out) if ops_out else []
            ops = [o.get("name", "") for o in ops_data]
        except json.JSONDecodeError:
            pass

        _, wl_out, _ = ssh_exec(ssh, docker_cmd("cat /data/whitelist.json 2>/dev/null || echo '[]'"), timeout=10)
        try:
            wl_data = json.loads(wl_out) if wl_out else []
            whitelist = [w.get("name", "") for w in wl_data]
        except json.JSONDecodeError:
            pass

        _, ban_out, _ = ssh_exec(ssh, docker_cmd("cat /data/banned-players.json 2>/dev/null || echo '[]'"), timeout=10)
        try:
            ban_data = json.loads(ban_out) if ban_out else []
            bans = [b.get("name", "") for b in ban_data]
        except json.JSONDecodeError:
            pass

        ssh.close()
    except Exception:
        pass

    return templates.TemplateResponse("players.html", {
        "request": request, "ops": ops, "whitelist": whitelist, "bans": bans
    })


@app.post("/players/op")
async def player_op(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"op {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/deop")
async def player_deop(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"deop {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/whitelist-add")
async def whitelist_add(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"whitelist add {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/whitelist-remove")
async def whitelist_remove(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"whitelist remove {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/ban")
async def player_ban(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    reason = form.get("reason", "Banned by admin")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f'ban {player} {reason}'), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)


@app.post("/players/pardon")
async def player_pardon(request: Request):
    if not is_configured():
        return RedirectResponse("/settings", status_code=303)
    form = await request.form()
    player = form.get("player", "")
    if player:
        try:
            ssh = ssh_connect()
            ssh_exec(ssh, docker_cmd(f"pardon {player}"), timeout=15)
            ssh.close()
        except Exception:
            pass
    return RedirectResponse("/players", status_code=303)
