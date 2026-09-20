resource "oci_network_load_balancer_network_load_balancer" "mc_nlb" {
  compartment_id = var.compartment_ocid
  display_name   = "minecraft-nlb"
  is_private     = false
  subnet_id      = oci_core_subnet.mc_subnet.id

  is_preserve_source_destination = false

  network_security_group_ids = []
}

resource "oci_network_load_balancer_backend_set" "mc_backend_set" {
  network_load_balancer_id = oci_network_load_balancer_network_load_balancer.mc_nlb.id
  name                     = "minecraft-backend-set"
  policy                   = "TWO_TUPLE"

  health_checker {
    protocol           = "TCP"
    port               = local.config.server_port
    interval_in_millis = 10000
    timeout_in_millis  = 5000
    retries            = 5
  }
}

resource "oci_network_load_balancer_backend" "mc_backend" {
  network_load_balancer_id = oci_network_load_balancer_network_load_balancer.mc_nlb.id
  backend_set_name         = oci_network_load_balancer_backend_set.mc_backend_set.name
  ip_address               = oci_core_instance.mc_server.private_ip
  port                     = local.config.server_port
}

resource "oci_network_load_balancer_listener" "mc_listener" {
  network_load_balancer_id = oci_network_load_balancer_network_load_balancer.mc_nlb.id
  default_backend_set_name = oci_network_load_balancer_backend_set.mc_backend_set.name
  name                     = "minecraft-listener"
  port                     = local.config.server_port
  protocol                 = "TCP_AND_UDP"
}

output "mc_ip" {
  value       = [for ip in oci_network_load_balancer_network_load_balancer.mc_nlb.ip_addresses : ip.ip_address if ip.is_public][0]
  description = "Public NLB IP for Minecraft players"
}
