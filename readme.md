# MC Sunucu Otomasyonu

Oracle Cloud Free Tier üzerinde tek komutla Minecraft sunucusu kurar, web panelinden yönetirsin.

---

## Kurulum

### 1. Oracle Cloud Credential'ları

[Oracle Cloud Console](https://cloud.oracle.com) adresine giriş yap:

- **Tenancy OCID:** Profile (sağ üst) -> Tenancy -> Copy OCID
- **User OCID:** Profile -> Copy OCID
- **Compartment OCID:** Menu (sol üst) -> Identity & Security -> Compartments -> compartment seç -> Copy OCID
- **Region Key:** Developer Tools (profile solu) -> Cloud shell -> Üstte yazıyor

### 2. API Key Oluştur

1. Profile -> Tokens and Keys -> API Keys (sol menüden)
2. **Add API Key** -> **Generate API Key Pair** seç
3. **Private Key**'i (`.pem` dosyası) proje klasörüne indir
4. **Add** de, oluşan **Fingerprint**'i kopyala
5. Terminalde: `chmod 400 key.pem`

### 3. SSH Anahtarı Oluştur

```bash
ssh-keygen -t ed25519 -f key1.pem -N ""
```

Bu komut `key1.pem` (özel anahtar) ve `key1.pem.pub` (açık anahtar) dosyalarını oluşturur. Her iki dosya da proje kök dizininde olmalı.

### 4. Değişkenleri Yapılandır

```bash
cp terraform.tfvars.example terraform.tfvars
cp config.example.json config.json
```

**terraform.tfvars** dosyasını düzenle — Oracle credential'ları yapıştır.

**config.json** dosyasını düzenle — Minecraft sunucu ayarları:

```json
{
  "minecraft_version": "1.21.1",
  "server_type": "vanilla",
  "ram_gb": 16,
  "server_port": 25565,
  "max_players": 20,
  "server_name": "A Cool Server",
  "ssh_user": "ubuntu"
}
```

### 5. Deploy

```bash
terraform init
terraform plan
terraform apply
```

Deploy sonrası terminalde SSH IP'si çıkacak. Bunu kopyala.

---

## Bağlantı

### SSH ile Bağlan

```bash
ssh -i key1.pem ubuntu@<SSH_IP>
```

### Web Paneline Eriş

Panel sadece SSH tunnel üzerinden erişilebilir. Yeni bir terminal aç:

```bash
ssh -i key1.pem -L 8080:localhost:80 ubuntu@<SSH_IP>
```

Tarayıcıda aç:

```
http://localhost:8080
```

---

## Web Paneli

### Dashboard

- Container durumu (Running / Stopped)
- IP adresi, versiyon, tür
- RAM ve CPU kullanımı
- Start / Stop / Restart butonları

### Logs

Sunucu loglarını görüntüle. Satır sayısı seçebilirsin (50-500).

### Mods

**Mods sekmesi:**
- Modrinth'te mod ara ve yükle
- Yüklü modları gör ve kaldır

**Modpacks sekmesi:**
- Modrinth'te modpack ara ve kur
- Yüklü modpack'i gör ve tek tıkla kaldır

### Players

- OP listesi (oyuncuya OP ver / al)
- Whitelist (oyuncu ekle / kaldır)
- Ban listesi (yasakla / affet)

### Settings

- Minecraft versiyonu ve sunucu türü
- RAM, max oyuncu, view distance
- MOTD, online mode, RCON

---

## Desteklenen Sunucu Türleri

`vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `quilt`, `neoforge`

## Desteklenen MC Versiyonları

1.16.x ve üzeri (Java 17 / Java 21)
