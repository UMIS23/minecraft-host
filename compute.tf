
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.compartment_ocid
}

data "oci_core_images" "ubuntu" {
  compartment_id   = var.compartment_ocid
  operating_system = "Canonical Ubuntu"
  shape            = "VM.Standard.A1.Flex"
  sort_by          = "TIMECREATED"
  sort_order       = "DESC"
}

resource "oci_core_vcn" "mc_vcn" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = ["10.0.0.0/16"]
  display_name   = "minecraft-vcn"
  dns_label      = "mcvcn"
}

resource "oci_core_internet_gateway" "mc_ig" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.mc_vcn.id
  display_name   = "minecraft-ig"
}

resource "oci_core_route_table" "mc_rt" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.mc_vcn.id
  display_name   = "minecraft-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.mc_ig.id
  }
}

resource "oci_core_security_list" "mc_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.mc_vcn.id
  display_name   = "minecraft-sl"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options {
      min = 25565
      max = 25565
    }
  }

  ingress_security_rules {
    protocol = "17" # UDP
    source   = "0.0.0.0/0"
    udp_options {
      min = 25565
      max = 25565
    }
  }

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "0.0.0.0/0"
    tcp_options {
      min = 22
      max = 22
    }
  }

  ingress_security_rules {
    protocol = "6" # TCP
    source   = "10.0.0.0/16"
    tcp_options {
      min = 25565
      max = 25565
    }
  }

  ingress_security_rules {
    protocol = "17" # UDP
    source   = "10.0.0.0/16"
    udp_options {
      min = 25565
      max = 25565
    }
  }
}

resource "oci_core_subnet" "mc_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.mc_vcn.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "minecraft-subnet"
  dns_label         = "mcsub"
  route_table_id    = oci_core_route_table.mc_rt.id
  security_list_ids = [oci_core_security_list.mc_sl.id]
}

resource "oci_core_instance" "mc_server" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name
  display_name        = "Minecraft-Server"
  shape               = "VM.Standard.A1.Flex"

  shape_config {
    ocpus         = 4
    memory_in_gbs = 24
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.mc_subnet.id
    assign_public_ip = true
  }

  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.ubuntu.images[0].id
  }

  metadata = {
    ssh_authorized_keys = file("key1.pem.pub")
    user_data = base64encode(<<-USERDATA
#!/bin/bash
exec > /var/log/user-data.log 2>&1
set -ex

echo "=== STEP 1: Firewall ==="
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT

echo "Acquire::ForceIPv4 \"true\";" > /etc/apt/apt.conf.d/99force-ipv4

echo "=== STEP 2: Packages ==="
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y netfilter-persistent iptables-persistent docker.io docker-compose-v2
netfilter-persistent save

echo "=== STEP 3: Docker ==="
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu

echo "=== STEP 4: MC Server ==="
mkdir -p /opt/minecraft/data /opt/minecraft/panel
chmod -R 777 /opt/minecraft/data

docker run -d \
  --name mc \
  --restart unless-stopped \
  -p ${local.config.server_port}:${local.config.server_port}/tcp \
  -p ${local.config.server_port}:${local.config.server_port}/udp \
  -e EULA=TRUE \
  -e VERSION=${local.config.minecraft_version} \
  -e TYPE=${upper(local.config.server_type)} \
  -e MEMORY=${local.config.ram_gb}G \
  -e ONLINE_MODE=${upper(tostring(local.config.online_mode))} \
  -e MAX_PLAYERS=${local.config.max_players} \
  -e VIEW_DISTANCE=${local.config.view_distance} \
  -e ENABLE_RCON=${upper(tostring(local.config.enable_rcon))} \
  -e MOTD="${local.config.server_name}" \
  -v /opt/minecraft/data:/data \
  itzg/minecraft-server

sleep 5
chmod -R 777 /opt/minecraft/data

echo "=== USER_DATA COMPLETE ==="
USERDATA
    )
  }
}

resource "null_resource" "setup_panel" {
  depends_on = [oci_core_instance.mc_server]

  triggers = {
    instance_id = oci_core_instance.mc_server.id
  }

  provisioner "file" {
    source      = "web_panel/"
    destination = "/opt/minecraft/panel"

    connection {
      type        = "ssh"
      host        = oci_core_instance.mc_server.public_ip
      user        = "ubuntu"
      private_key = file(var.private_key_path)
      timeout     = "5m"
    }
  }

  provisioner "file" {
    source      = var.private_key_path
    destination = "/opt/minecraft/panel/key1.pem"

    connection {
      type        = "ssh"
      host        = oci_core_instance.mc_server.public_ip
      user        = "ubuntu"
      private_key = file(var.private_key_path)
      timeout     = "5m"
    }
  }

  provisioner "remote-exec" {
    inline = [
      "sudo mkdir -p /opt/minecraft/panel/data",
      "sudo chown -R ubuntu:ubuntu /opt/minecraft/panel",
      "sudo chmod 600 /opt/minecraft/panel/key1.pem",
      "sudo chmod 600 /opt/minecraft/panel/app/ssh_client.py",
      "cat > /tmp/config.json << 'JSONEOF'\n{\"minecraft_version\":\"${local.config.minecraft_version}\",\"server_type\":\"${local.config.server_type}\",\"ram_gb\":${local.config.ram_gb},\"server_port\":${local.config.server_port},\"max_players\":${local.config.max_players},\"online_mode\":${tostring(local.config.online_mode)},\"view_distance\":${local.config.view_distance},\"server_name\":\"${local.config.server_name}\",\"enable_rcon\":${tostring(local.config.enable_rcon)},\"ssh_user\":\"ubuntu\",\"ssh_key_path\":\"/app/key1.pem\",\"server_ip\":\"${oci_core_instance.mc_server.public_ip}\"}\nJSONEOF",
      "sudo mv /tmp/config.json /opt/minecraft/panel/config.json",
      "cd /opt/minecraft/panel && sudo docker compose up -d --build",
    ]

    connection {
      type        = "ssh"
      host        = oci_core_instance.mc_server.public_ip
      user        = "ubuntu"
      private_key = file(var.private_key_path)
      timeout     = "10m"
    }
  }
}

output "mc_server_ip" {
  value       = [for ip in oci_network_load_balancer_network_load_balancer.mc_nlb.ip_addresses : ip.ip_address if ip.is_public][0]
  description = "Minecraft server IP (for players to connect)"
}

output "ssh_ip" {
  value       = oci_core_instance.mc_server.public_ip
  description = "SSH IP (for admin access via terminal)"
}
