
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
    ssh_authorized_keys = file("~/.ssh/id_rsa.pub")
    user_data = base64encode(<<-EOF
      #!/bin/bash
      set -e

      iptables -F
      iptables -X
      iptables -t nat -F
      iptables -t nat -X
      iptables -t mangle -F
      iptables -t mangle -X
      iptables -P INPUT ACCEPT
      iptables -P FORWARD ACCEPT
      iptables -P OUTPUT ACCEPT

      echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

      apt-get update -y
      DEBIAN_FRONTEND=noninteractive apt-get install -y netfilter-persistent iptables-persistent
      netfilter-persistent save

      apt-get install -y docker.io
      systemctl start docker
      systemctl enable docker
      usermod -aG docker ubuntu

      mkdir -p /opt/minecraft/data
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
    EOF
    )
  }
}

output "load_balancer_public_ip" {
  value       = [for ip in oci_network_load_balancer_network_load_balancer.mc_nlb.ip_addresses : ip.ip_address if ip.is_public][0]
  description = "NLB IP address that players should connect to"
}

output "server_public_ip" {
  value       = oci_core_instance.mc_server.public_ip
  description = "Server's own public IP address (for administration)"
}
