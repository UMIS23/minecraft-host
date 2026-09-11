# MC Server Automation

Deploy a Minecraft server on Oracle Cloud Free Tier with a single command and manage it through a web panel.

---

## Setup

### 1. Gather Oracle Cloud Credentials

Log in to [Oracle Cloud Console](https://cloud.oracle.com) and copy the following:

- **Tenancy OCID:** Profile (top right) -> Tenancy -> Copy OCID
- **User OCID:** Profile -> Copy OCID
- **Compartment OCID:** Menu (top left) -> Identity & Security -> Compartments -> select your compartment -> Copy OCID
- **Region Key:** Developer Tools (left of profile) -> Cloud shell -> shown at the top

### 2. Create Oracle API Key

1. Profile -> Tokens and Keys -> API Keys (left menu)
2. Click **Add API Key** -> Select **Generate API Key Pair**
3. Download the **Private Key** (`.pem` file) and place it in the project folder
4. Click **Add** and copy the generated **Fingerprint**
5. Set key permissions: `chmod 400 your_key.pem`

### 3. Create SSH Key and Upload to Oracle

You need an SSH key to connect to the server. Run in terminal:

```bash
ssh-keygen -t ed25519 -f my_key -N ""
```

This creates two files: `my_key` (private) and `my_key.pub` (public).

Upload the public key to Oracle:
1. Profile -> My Profile -> SSH Keys (left menu)
2. Click **Add Public Key**
3. Open `my_key.pub`, copy its contents and paste
4. Click **Add**

### 4. Configure Files

Copy the example files in the project folder:

```bash
cp terraform.tfvars.example terraform.tfvars
cp config.example.json config.json
```

Edit **terraform.tfvars** with your Oracle credentials:

```
tenancy_ocid     = "ocid1.tenancy.oc1..your_value_here"
user_ocid        = "ocid1.user.oc1..your_value_here"
compartment_ocid = "ocid1.tenancy.oc1..your_value_here"
fingerprint      = "xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx"
private_key_path = "your_key.pem"
region_key       = "il-jerusalem-1"
```

Edit **config.json** with your Minecraft server settings:

```json
{
  "minecraft_version": "1.21.1",
  "server_type": "vanilla",
  "ram_gb": 16,
  "server_port": 25565,
  "max_players": 20,
  "online_mode": false,
  "view_distance": 20,
  "server_name": "A Cool Server",
  "enable_rcon": true,
  "ssh_user": "ubuntu",
  "ssh_key_path": "~/.ssh/id_rsa",
  "server_ip": ""
}
```

### 5. Deploy

Run in the project folder:

```bash
terraform init
terraform plan
terraform apply
```

Type `yes` and wait. It takes 5-10 minutes. When done, an SSH IP will appear in the terminal output. Copy it.

---

## Connecting

### SSH to Server

Open a new terminal:

```bash
ssh -i my_key ubuntu@<THE_IP_FROM_OUTPUT>
```

### Access Web Panel

The panel runs on the server but is not publicly accessible. Open an SSH tunnel:

Open a new terminal:

```bash
ssh -i my_key -L 8080:localhost:80 ubuntu@<THE_IP_FROM_OUTPUT>
```

Keep this terminal open. Now open in your browser:

```
http://localhost:8080
```

The panel is ready. Manage everything from here.

---

## Web Panel

### Dashboard
- Server status (Running / Stopped)
- IP, version, server type
- RAM and CPU usage
- Start / Stop / Restart buttons

### Logs
View server logs. Choose between 50-500 lines.

### Mods
- Search and install mods from Modrinth
- View and remove installed mods

### Modpacks
- Search and install modpacks from Modrinth
- View and uninstall installed modpack with one click

### Players
- OP management
- Whitelist management
- Ban list management

### Settings
- Minecraft version and server type
- RAM, max players, view distance
- MOTD, online mode, RCON

---

## Supported Server Types

`vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `quilt`, `neoforge`

## Supported MC Versions

1.16.x and above (Java 17 / Java 21)
