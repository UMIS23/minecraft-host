# MC Server Automation

Deploy a Minecraft server on Oracle Cloud Free Tier and manage it through a web panel.

---

## Prerequisites

- **Oracle Cloud account** — [Sign up](https://cloud.oracle.com) (Free Tier eligible)

---

## Step 1: Create Oracle Cloud API Key

1. Log in to [Oracle Cloud Console](https://cloud.oracle.com)
2. Click your **profile icon** (top right) → **Tokens and Keys**
3. Left menu → **API Keys** → **Add API Key**
4. Select **Generate API Key Pair**
5. Download the **Private Key** (`.pem` file) → save it to this project folder
6. Click **Add** → copy the **Tenancy OCID**, **User OCID**, **Fingerprint**, and **Region** shown on screen.
7. For **Compartment OCID**: click the navigation menu (top left) → **Identity & Security** → **Compartments** → select your compartment → **Copy OCID**.
8. Set key permissions: `chmod 400 key1.pem`

---

## Step 2: Create SSH Key

```bash
ssh-keygen -t ed25519 -f key1 -N ""
chmod 600 key1
```

> Terraform automatically adds this key to your VM during deployment.

---

## Step 3: Configure Terraform

1. Copy the example file and rename it:

```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Open `terraform.tfvars` and fill in your values from Step 1:

```hcl
tenancy_ocid     = "ocid1.tenancy.oc1..aaaa..."
user_ocid        = "ocid1.user.oc1..aaaa..."
compartment_ocid = "ocid1.tenancy.oc1..aaaa..."
fingerprint      = "xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx:xx"
private_key_path = "key1.pem"
ssh_private_key_path = "key1"
region_key       = "il-jerusalem-1"
```

3. Install Terraform: `sudo snap install terraform --classic`

> Requires Terraform >= 1.5 and Python >= 3.12.

4. Install Python dependencies (for `mc_manager.py` CLI):

```bash
pip install -r requirements.txt
```

---

## Step 4: Deploy

```bash
terraform init
terraform apply
```

Wait 5-8 minutes for deployment to complete. The output will show your server's public IP.

---

## Step 5: Access Web Panel

1. Start an SSH tunnel:

```bash
ssh -i key1 -L 8080:127.0.0.1:80 ubuntu@<SERVER_IP>
```

2. Open in browser: `http://localhost:8080`

3. Go to **Settings** → paste your server's public IP into **Server IP** field → Save.

---

## Web Panel Overview

### Dashboard
Server status, IP, version, RAM/CPU usage. Start / Stop / Restart buttons.

### Logs
- **Minecraft** tab — server console logs
- **Terraform** tab — deploy/infrastructure logs

### Mods
Search and install mods from Modrinth. View and remove installed mods.

### Players
OP management, Whitelist, Ban list.

### Settings
Minecraft version, server type, RAM, players, MOTD, etc.

### Oracle Cloud
OCI credentials, Deploy/Destroy buttons, current infrastructure state.

---

## Supported Server Types

`vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `quilt`, `neoforge`

## Supported MC Versions

1.16.x and above (Java 17 / Java 21)
