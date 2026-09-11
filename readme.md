# MC Sunucu Otomasyonu

Oracle Cloud Free Tier üzerinde tek komutla Minecraft sunucusu kurar, web panelinden yönetirsin.

---

## Kurulum

### 1. Oracle Cloud Credential'ları Topla

[Oracle Cloud Console](https://cloud.oracle.com) adresine giriş yap ve şunları kopyala:

- **Tenancy OCID:** Profile (sağ üst) -> Tenancy -> Copy OCID
- **User OCID:** Profile -> Copy OCID
- **Compartment OCID:** Menu (sol üst) -> Identity & Security -> Compartments -> compartment seç -> Copy OCID
- **Region Key:** Developer Tools (profile solu) -> Cloud shell -> Üstte yazıyor

### 2. Oracle API Key Oluştur ve İndir

1. Profile -> Tokens and Keys -> API Keys (sol menüden)
2. **Add API Key** -> **Generate API Key Pair** seç
3. **Private Key**'i indir ve proje klasörüne koy (dosya adı önemli değil, `.pem` uzantılı olsun)
4. **Add** de, oluşan **Fingerprint**'i kopyala
5. Terminalde private key'e yetki ver: `chmod 400 indirdigin_key.pem`

### 3. SSH Anahtarı Oluştur ve Oracle'a Yükle

Sunucuya bağlanmak için SSH anahtarı lazım. Terminalde:

```bash
ssh-keygen -t ed25519 -f my_key -N ""
```

Bu iki dosya oluşturur: `my_key` (özel) ve `my_key.pub` (açık).

Şimdi Oracle'a yükle:
1. Profile -> My Profile -> SSH Keys (sol menüden)
2. **Add Public Key** tıkla
3. `my_key.pub` dosyasının içeriğini aç, kopyala ve yapıştır
4. **Add** de

### 4. Dosyaları Yapılandır

Proje klasöründe `terraform.tfvars.example` ve `config.example.json` dosyaları var. Bunları kopyala:

```bash
cp terraform.tfvars.example terraform.tfvars
cp config.example.json config.json
```

**terraform.tfvars** dosyasını düzenle. İçinde şunlar olmalı:

```
tenancy_ocid     = "ocid1.tenancy.oc1..buraya..."
user_ocid        = "ocid1.user.oc1..buraya..."
compartment_ocid = "ocid1.tenancy.oc1..buraya..."  (veya kendi compartment'ın)
fingerprint      = "xx:xx:xx:xx:..."
private_key_path = "indirdigin_key.pem"  (2. adımda indirdiğin dosya)
region_key       = "il-jerusalem-1"  (veya kendi bölgen)
```

**config.json** dosyasını düzenle. İçinde şunlar olmalı:

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

Terminalde proje klasöründe:

```bash
terraform init
terraform plan
terraform apply
```

`yes` de ve bekle. İşlem 5-10 dakika sürebilir. Bitince terminalde SSH IP'si çıkacak, onu kopyala.

---

## Bağlantı

### SSH ile Sunucuya Bağlan

Yeni bir terminal aç:

```bash
ssh -i my_key ubuntu@<ÇIKAN_IP>
```

### Web Paneline Eriş

Panel sunucuda çalışıyor ama doğrudan erişilemez. SSH tunnel aç:

Yeni bir terminal aç:

```bash
ssh -i my_key -L 8080:localhost:80 ubuntu@<ÇIKAN_IP>
```

Bu komut terminali açık tut. Şimdi tarayıcıda aç:

```
http://localhost:8080
```

Panel açıldı. Her şeyi buradan yönetebilirsin.

---

## Web Paneli

### Dashboard
- Sunucu durumu (Running / Stopped)
- IP, versiyon, sunucu türü
- RAM ve CPU kullanımı
- Start / Stop / Restart butonları

### Logs
Sunucu loglarını görüntüle. 50-500 arası satır seçebilirsin.

### Mods
- Modrinth'te mod ara ve yükle
- Yüklü modları gör ve kaldır

### Modpacks
- Modrinth'te modpack ara ve kur
- Yüklü modpack'i gör ve tek tıkla kaldır

### Players
- OP yönetimi
- Whitelist yönetimi
- Ban listesi yönetimi

### Settings
- Minecraft versiyonu ve sunucu türü
- RAM, max oyuncu, view distance
- MOTD, online mode, RCON

---

## Desteklenen Sunucu Türleri

`vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `quilt`, `neoforge`

## Desteklenen MC Versiyonları

1.16.x ve üzeri (Java 17 / Java 21)
