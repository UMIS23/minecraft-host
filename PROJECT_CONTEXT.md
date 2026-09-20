# PROJECT_CONTEXT.md

> Bu döküman, her yeni oturum açıldığında projeyi hızlıca anlayıp çalışmaya başlamak için hazırlanmıştır.

---

## 1. Projenin Amacı ve Özeti

**MC Sunucu Otomasyonu**, Oracle Cloud Free Tier üzerinde Terraform ile Minecraft sunucusu deploy eden, SSH ile yöneten ve web paneli sunan tam kapsamlı bir otomasyon projesidir.

**Temel işlevler:**
- Oracle Cloud'da VM oluşturma (Terraform ile IaC)
- Minecraft sunucusu kurma ve yönetme (Docker + SSH)
- Mod/modpack yükleme (Modrinth API entegrasyonu)
- Web tabanlı kontrol paneli (FastAPI)
- CLI komut satırı yöneticisi

---

## 2. Teknoloji Yığını (Tech Stack)

### Altyapı
| Teknoloji | Amaç |
|-----------|------|
| **Oracle Cloud (OCI)** | Free Tier VM hosting (VM.Standard.A1.Flex - 4 OCPU, 24GB RAM) |
| **Terraform** | Infrastructure as Code - OCI kaynak yönetimi |
| **Docker** | Minecraft sunucusu ve web panel container'ları |

### Backend
| Teknoloji | Amaç |
|-----------|------|
| **Python 3.12** | CLI ve web panel backend |
| **FastAPI** (v0.115.0) | Web panel REST API |
| **Uvicorn** (v0.30.0) | ASGI sunucusu |
| **Jinja2** (v3.1.4) | HTML template motoru |
| **Paramiko** (v3.4.0) | SSH bağlantısı ve uzak komut çalıştırma |
| **Requests** (v2.32.3) | Modrinth API HTTP istekleri |

### Frontend
| Teknoloji | Amaç |
|-----------|------|
| **HTML5** | Sayfa iskeleti |
| **CSS3** | Dark tema, glassmorphism, responsive tasarım |
| **Google Fonts (Inter)** | Yazı tipi |

### Networking
| Teknoloji | Amaç |
|-----------|------|
| **Nginx** (alpine) | Reverse proxy (web panel için) |
| **Network Load Balancer** | TCP/UDP 25565 yönlendirme |

### Bağımlılık Dosyaları
- `/requirements.txt` → CLI tool (paramiko, requests)
- `/web_panel/requirements.txt` → Web panel (fastapi, uvicorn, jinja2, paramiko, requests, python-multipart)

---

## 3. Proje Mimarısı ve Klasör Yapısı

```
mc_sunucu_otomasyonu/
│
├── main.tf                    # Terraform provider ve locals tanımı
├── compute.tf                 # OCI VM, VCN, subnet, security list, user_data
├── nlb.tf                     # Network Load Balancer yapılandırması
├── variables.tf               # Terraform input değişkenleri (OCI credentials)
├── terraform.tfvars           # [HASSAS] OCI credential değerleri
├── terraform.tfvars.example   # tfvars şablonu
├── terraform.tfstate          # [HASSAS] Mevcut state
├── terraform.tfstate.backup   # State yedeği
│
├── config.json                # [HASSAS] Sunucu yapılandırması (MC sürümü, RAM, port vb.)
├── config.example.json        # Config şablonu
├── key1.pem                   # [HASSAS] OCI API özel anahtarı (isim kullanıcı seçer)
├── key1                       # [HASSAS] SSH özel anahtarı (isim kullanıcı seçer)
├── key1.pub                   # SSH public anahtarı (VM'e gömülür)
│
├── mc_manager.py              # CLI yönetim aracı (1614 satır)
├── requirements.txt           # CLI Python bağımlılıkları
│
├── readme.md                  # Kurulum ve kullanım kılavuzu
├── .gitignore                 # Git ignored dosyalar
│
└── web_panel/                 # Web tabanlı yönetim paneli
    ├── Dockerfile             # Panel Docker imajı (python:3.12-slim)
    ├── docker-compose.yml     # panel + nginx servisleri
    ├── nginx.conf             # Nginx reverse proxy (port 80)
    ├── requirements.txt       # Panel Python bağımlılıkları
    ├── config.json            # Sunucu yapılandırması (deploy sırasında oluşur)
    ├── .dockerignore          # Docker build ignored
    │
    └── app/
        ├── __init__.py        # Boş paket init
        ├── main.py            # FastAPI endpoint'leri (746 satır)
        ├── ssh_client.py      # SSH yardımcı fonksiyonlar (175 satır)
        │
        ├── templates/
        │   ├── base.html      # Temel layout (sidebar + content)
        │   ├── dashboard.html # Ana kontrol paneli
        │   ├── logs.html      # Log görüntüleme
        │   ├── mods.html      # Mod yönetimi
        │   ├── players.html   # Oyuncu yönetimi
        │   └── settings.html  # Sunucu ayarları
        │
        └── static/
            └── css/
                └── style.css  # Dark tema CSS (645 satır)
```

---

## 4. Bileşenler ve Bağlantıları (Data/Logic Flow)

### 4.1. Üst Düzey Mimari Akışı

```
┌─────────────────────────────────────────────────────────────────┐
│                        Oracle Cloud (OCI)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    VM (ARM - 4 OCPU, 24GB)               │  │
│  │                                                          │  │
│  │  ┌─────────────────────┐  ┌──────────────────────────┐  │  │
│  │  │  Minecraft Server   │  │     Web Panel Stack      │  │  │
│  │  │  (itzg/mc-server)   │  │                          │  │  │
│  │  │  Port: 25565        │  │  ┌───────┐ ┌──────────┐  │  │  │
│  │  └─────────┬───────────┘  │  │ Nginx │→│ FastAPI  │  │  │  │
│  │            │              │  │ :80   │ │ :8000    │  │  │  │
│  │            │              │  └───────┘ └──────────┘  │  │  │
│  │            │              └──────────────────────────┘  │  │
│  └────────────┼───────────────────────────────────────────┘  │
│               │                                              │
│  ┌────────────┴──────────────────────────────────────────┐   │
│  │           Network Load Balancer (NLB)                 │   │
│  │           TCP/UDP 25565 → MC Container                 │   │
│  └───────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                        ▲
                        │
            ┌───────────┴───────────┐
            │     Yönetim Erişimi    │
            ├───────────────────────┤
            │  • CLI (mc_manager.py)│
            │  • Web Panel (HTTP)   │
            │  • SSH                │
            └───────────────────────┘
```

### 4.2. Modül Bağlantı Haritası

```
mc_manager.py (CLI)
├── config.json oku/yaz
├── terraform output → sunucu IP'si
├── Modrinth API (requests) → mod arama/indirme
└── SSH (paramiko) → uzak sunucu komutları

web_panel/app/main.py (FastAPI)
├── ssh_client.py import (tüm SSH fonksiyonları)
├── templates/*.html (Jinja2 render)
├── static/css/style.css
└── Modrinth API (requests) → mod arama

web_panel/app/ssh_client.py (Altyapı)
├── config.json oku/yaz
└── paramiko SSH bağlantısı

Terraform (.tf dosyaları)
├── config.json (locals.config)
├── variables.tf (OCI credentials + key yolları: private_key_path, ssh_private_key_path, ssh_public_key_path)
├── terraform.tfvars (değerler)
├── key1.pub (SSH public key → VM authorized_keys)
└── web_panel/ (tarball ile sunucuya yüklenir, docker compose ile deploy)
```

### 4.3. Veri Akışı Örnekleri

**Mod Yükleme (Web Panel):**
1. Kullanıcı → `/mods` sayfasında arama yapar
2. `main.py` → Modrinth API'ye HTTP isteği gönderir
3. Sonuçlar → `mods.html` template'inde gösterilir
4. Kullanıcı "Install" butonuna basar
5. `main.py` → Modrinth'ten `.jar` dosyasını indirir (tempfile)
6. `main.py` → SSH ile sunucuya bağlanır
7. SFTP ile dosyayı `/opt/minecraft/data/mods/` dizinine yükler
8. Docker restart ile sunucu yeniden başlatılır

**Modpack Yükleme (CLI):**
1. `mc_manager.py install-pack <name>` çalıştırılır
2. Modrinth API ile modpack aranır
3. `.mrpack` dosyası indirilir
4. Overrides çıkarılır (sunucuda SSH ile)
5. `modrinth.index.json` okunur, ek modlar indirilir
6. Client-side modlar karantinaya alınır
7. `config.json` güncellenir (server_type değiştirilir)
8. Docker container yeniden oluşturulur

---

## 5. Tamamlanan Adımlar ve Mevcut Durum

### ✅ Tamamlananlar

| Modül | Durum | Detay |
|-------|-------|-------|
| Terraform Altyapısı | ✅ Tamamlandı | VCN, Subnet, IGW, Security List, VM, NLB |
| Docker Container | ✅ Tamamlandı | itzg/minecraft-server kurulumu |
| CLI Yöneticisi | ✅ Tamamlandı | mod/modpack/map kurma, versiyon değiştirme, durum |
| Web Panel Backend | ✅ Tamamlandı | FastAPI endpoint'leri, SSH yönetimi |
| Web Panel Frontend | ✅ Tamamlandı | Dashboard, Logs, Mods, Players, Settings |
| Web Panel Deploy | ✅ Tamamlandı | Docker Compose + Nginx reverse proxy |
| Modrinth Entegrasyonu | ✅ Tamamlandı | Mod/modpack arama, indirme, yükleme |
| Mod Karantina Sistemi | ✅ Tamamlandı | Client-side mod filtreleme, crash detection |
| Harita Yükleme | ✅ Tamamlandı | .zip/.mcworld desteği, resource pack |
| Key Ayrımı (API vs SSH) | ✅ Tamamlandı | `key1.pem` (OCI API) + `key1`/`key1.pub` (SSH); adlar değişkenle seçiliyor |
| Oyuncu IP'si (`mc_ip`) | ✅ Tamamlandı | NLB public IP output + dashboard/CLI'de ayrı gösterim |
| Panel Deploy Fix | ✅ Tamamlandı | Tarball upload + mkdir sıralaması (scp race çözüldü) |

### 🔧 Mevcut Durum

- Proje **çalışır durumda**
- Oracle Cloud Free Tier VM üzerinde deploy edilmiş
- İki ayrı IP: yönetim/SSH (`ssh_ip` output) + oyuncular (`mc_ip` output, NLB)
- Hem CLI hem Web Panel üzerinden yönetim mümkün
- Modrinth API entegrasyonu aktif
- Web panelde Oracle Cloud bölümü **kaldırıldı** (kullanıcı isteği; deploy Terraform CLI ile yapılıyor)

---

## 6. Gelecek Adımlar ve Yol Haritası

### Genel Vizyon
Tüm yönetim işlemleri web paneli ve CLI üzerinden yapılacak. Deploy Terraform CLI ile yapılıyor (web paneldeki Oracle Cloud bölümü güvenlik/sadelik için kaldırıldı). Oyuncu trafiği NLB üzerinden, yönetim (SSH/panel/CLI) doğrudan VM IP'si üzerinden yürüyor.

### Yakın Vadeli (Sıradaki Adım)
- [ ] **Orphan Kaynak Temizliği** — Eski state yedeğindeki (`terraform.tfstate.backup`) kaynakların OCI konsolundan kontrol edilip free-tier aşımı yapmaması için temizlenmesi

### Kısa Vadeli
- [ ] **Test Coverage** — Birim testleri ve entegrasyon testleri eklenmesi
- [ ] **Error Handling** — Daha detaylı hata yönetimi ve kullanıcı bildirimleri

### Orta Vadeli
- [ ] **Monitoring** — CPU/RAM/disk monitoring dashboard'u
- [ ] **Bildirim Sistemi** — Discord webhook / email bildirimleri

---

## 7. Önemli Kurallar ve Mimari Kararlar

### 7.1. Güvenlik Kuralları

| Kural | Açıklama |
|-------|----------|
| **Hassas dosyalar gitignore'da** | `config.json`, `terraform.tfvars`, `*.pem`, `/key1`, `/key1.pub`, `*.tfstate` asla commit edilmez |
| **OCI API key** | `key1.pem` (ad kullanıcı seçer) salt okunabilir (`chmod 400`); sadece Terraform provider kullanır |
| **SSH key** | `key1` (ad kullanıcı seçer) `chmod 600`; provisioner/panel/CLI kullanır, public yarısı VM'e gömülür |
| **OCI credentials** | `terraform.tfvars` dosyasında tutulur, example dosyası sablon olarak paylaşılır |
| **Panel erişimi** | Nginx sadece `127.0.0.1:80`'de dinler, dışarıya açık değildir |

### 7.2. Mimari Kararlar

| Karar | Gerekçe |
|-------|---------|
| **ARM tabanlı VM (A1.Flex)** | Free Tier'da 4 OCPU + 24GB RAM ücretsiz |
| **Docker ile container** | İzole ortam, kolay güncelleme/yedekleme |
| **FastAPI + Jinja2** | Hafif, hızlı, template ile server-side rendering |
| **SSH tabanlı yönetim** | Docker socket paylaşımı yerine güvenli uzak erişim |
| **Modrinth API** | CurseForge'a göre daha açık API, rate limit daha yüksek |
| **Client-side mod filtreleme** | Sunucuda çalışmayan modları otomatik karantinaya alma |

### 7.3. Kod Standartları

| Standart | Açıklama |
|----------|----------|
| **Python 3.12** | f-string, type hints (kısmen), pathlib kullanımı |
| **Docstring** | Ana modüller ve fonksiyonlar docstring ile belgelenmiş |
| **Error try/except** | SSH ve API çağrıları try/except ile sarılmış |
| **Config yönetimi** | Tek bir `config.json` üzerinden tüm ayarlar |
| **Template inheritance** | `base.html` template'inden türetme |

### 7.4. Dosya Konumları ve Öncelikler

| Dosya | Konum | Kritiklik |
|-------|-------|-----------|
| `config.json` | Kök dizin | Yüksek (çalışma zamanı) |
| `terraform.tfvars` | Kök dizin | Yüksek (deploy zamanı) |
| `key1.pem` | Kök dizin | Yüksek (OCI API erişimi) |
| `key1` / `key1.pub` | Kök dizin | Yüksek (SSH erişimi; adlar değişkenle seçilir) |
| `mc_manager.py` | Kök dizin | Yüksek (CLI yönetimi) |
| `web_panel/app/main.py` | Web panel | Yüksek (web arayüzü) |
| `web_panel/app/ssh_client.py` | Web panel | Orta (yardımcı modül) |

### 7.5. Ortak Fonksiyonlar ve Tekrar Eden Kalıplar

**mc_manager.py ve ssh_client.py paylaşılan fonksiyonlar:**
- `load_config()` / `save_config()` — Config yönetimi
- `ssh_connect()` / `ssh_exec()` — SSH bağlantısı
- `docker_cmd()` — Docker komut sarmalayıcı
- `get_java_tag()` — MC sürümü → Java tag eşleştirmesi
- `build_docker_run()` — Docker run komutu oluşturma

**Not:** Bu fonksiyonlar iki dosyada da tekrarlanmıştır. Gelecekte refactor ile tek bir modüle taşınabilir.

### 7.6. Desteklenen Sunucu Türleri

```
vanilla, forge, fabric, paper, spigot, bukkit, purpur, sponge, velocity, quilt, neoforge, fml, limbo, bedrock
```

### 7.7. Client-Side Mod Filtresi

Sunucuda çalışmayan ve karantinaya alınan modlar:
```
iris, irisfixes, oculus, embeddium, rubidium, optifine, optifog,
sodium, sodium-extra, sodiumextras, sodiumdynamiclights,
sodiumoptionsapi, sodiumoptionsmodcompat, reeses_sodium_options,
entity_texture_features, entity_model_features, skinlayers3d,
dynamiclights, lambdynamiclights, betterclouds, smartlighting,
continuity, immediatelyfast, lithium, ferritecore, lazydfu, starlight,
cavedust, voidfog, modmenu, zoomify, minihud, tweakeroo,
xaerominimap, xaeroworldmap, journeymap, inventoryhud, craftpresence,
keybindings, nemos_inventory_sorting, nemos-inventory-sorting,
presencefootsteps, sound-physics-remastered, notenoughanimations,
player-animation-lib, better-third-person, leawind_third_person,
flerovium, colorwheel, colorwheel_patcher, geckolib-fabric
```

---

## 8. Hızlı Referans

### Terraform Komutları
```bash
terraform init
terraform plan
terraform apply
terraform output -raw ssh_ip   # yönetim/SSH IP'si
terraform output -raw mc_ip    # oyuncu IP'si (NLB)
```

### CLI Komutları
```bash
./mc_manager.py status
./mc_manager.py install <mod_name>
./mc_manager.py install-pack <pack_name>
./mc_manager.py install-map <file>
./mc_manager.py list
./mc_manager.py set-version <version>
./mc_manager.py set-type <type>
./mc_manager.py restart
```

### Web Panel Başlatma
```bash
cd web_panel
docker compose up -d --build
```

### SSH Bağlantısı
```bash
ssh -i <ssh-key> ubuntu@<SERVER_IP>
sudo docker exec -it mc rcon-cli
```

---

*Son Güncelleme: 2026-09-20*
