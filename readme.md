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

### 3. Değişkenleri Yapılandır

```bash
# Örnek dosyaları kopyala
cp terraform.tfvars.example terraform.tfvars
cp config.example.json config.json
```

**terraform.tfvars** dosyasını düzenle — Oracle credential'ları yapıştır.

**config.json** dosyasını düzenle — Minecraft sunucu ayarları:

```json
{
  "minecraft_version": "1.21.1",
  "server_type": "forge",
  "ram_gb": 16,
  "server_port": 25565,
  "max_players": 20,
  "server_name": "A Cool Server",
  "ssh_user": "ubuntu"
}
```

### 4. Deploy

```bash
terraform init
terraform plan
terraform apply
```

Deploy sonrası terminalde sunucu IP'si çıkacak. Bunu not et.

---

## Web Paneli

Deploy sonrası sunucu otomatik olarak web panelini kurar. Tarayıcıdan sunucu IP'sine bağlan:

```
http://<SUNUCU_IP>
```

### Dashboard

Sunucu durumunu Görüntüle:
- Container durumu (Running / Stopped)
- IP adresi, versiyon, tür
- RAM ve CPU kullanımı
- Start / Stop / Restart butonları

### Logs

Sunucu loglarını tarayıcıdan görüntüle. Satır sayısı seçebilirsin (50-500).

### Mods

**Mods sekmesi:**
- Modrinth'te mod ara ve yükle
- Yüklü modları gör ve kaldır

**Modpacks sekmesi:**
- Modrinth'te modpack ara ve kur
- Yüklü modpack'i gör ve tek tıkla kaldır (vanilla moda dön)

### Players

- OP listesi (oyuncuya OP ver / al)
- Whitelist (oyuncu ekle / kaldır)
- Ban listesi (yasakla / affet)

### Settings

- Minecraft versiyonu ve sunucu türü
- RAM, max oyuncu, view distance
- MOTD, online mode, RCON
- SSH ayarları

---

## CLI Yöneticisi (mc_manager.py)

Web paneline alternatif olarak terminal üzerinden de yönetebilirsin:

```bash
pip install -r requirements.txt
chmod +x mc_manager.py
```

### Komutlar

| Komut | Açıklama |
|-------|----------|
| `./mc_manager.py status` | Sunucu durumunu göster |
| `./mc_manager.py install <mod>` | Mod yükle |
| `./mc_manager.py install-pack <pack>` | Modpack kur |
| `./mc_manager.py install-map <file>` | Harita yükle |
| `./mc_manager.py remove <mod>` | Mod kaldır |
| `./mc_manager.py list` | Yüklü modları listele |
| `./mc_manager.py uninstall-pack` | Modpack kaldır (vanilla'ya dön) |
| `./mc_manager.py set-version <ver>` | MC versiyonunu değiştir |
| `./mc_manager.py set-type <type>` | Sunucu türünü değiştir |
| `./mc_manager.py set-motd <msg>` | MOTD değiştir |
| `./mc_manager.py restart` | Sunucuyu yeniden başlat |
| `./mc_manager.py stop` | Sunucuyu durdur |
| `./mc_manager.py start` | Sunucuyu başlat |

---

## SSH (İleri Düzey)

Sadece gelişmiş işlemler veya sorun giderme için gerekli:

```bash
ssh ubuntu@<SUNUCU_IP>
```

Docker konsolu:
```bash
sudo docker exec -it mc rcon-cli
```

Faydalı rcon komutları:
- `list` — Online oyuncuları göster
- `say <mesaj>` — Herkese mesaj gönder
- `op <oyuncu>` — Oyuncuya OP ver
- `whitelist on/off` — Whitelist aç/kapat
- `stop` — Sunucuyu durdur

---

## Desteklenen Sunucu Türleri

`vanilla`, `forge`, `fabric`, `paper`, `spigot`, `bukkit`, `purpur`, `quilt`, `neoforge`

## Desteklenen MC Versiyonları

1.16.x ve üzeri (Java 17 / Java 21)
