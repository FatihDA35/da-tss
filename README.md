# DA TTS

EMA Lightning için Docker Compose tabanlı Türkçe metin-ses WebUI'si. Metni ekrandaki kutuya yazabilir veya UTF-8 `.txt` dosyası yükleyebilirsin; sonuç 48 kHz mono WAV olarak indirilir.

## Başlatma

Docker Engine ve Docker Compose v2 kurulu olmalı. Repo kök dizininden:

```sh
docker compose -f da-tts/compose.yaml up --build -d
```

Arayüz: <http://localhost:7860>

İlk ses üretiminde EMA model ağırlıkları Hugging Face'den indirilir. `ema-model-cache` adlı Docker volume sonraki çalıştırmalarda modeli saklar. Logları görmek için:

```sh
docker compose -f da-tts/compose.yaml logs -f
```

Kapatmak için:

```sh
docker compose -f da-tts/compose.yaml down
```

## Erişim ayarı

Compose varsayılanı arayüzü sadece bu bilgisayara (`127.0.0.1`) açar. Yerel ağdaki diğer cihazlardan erişmek için `compose.yaml` içindeki port satırını `"7860:7860"` yapıp servisi yeniden oluştur.

## GPU

Bu Compose dosyası taşınabilir olması için CPU PyTorch kullanır. NVIDIA Container Toolkit kurulu bir Linux makinede GPU kullanımı için Dockerfile'daki PyTorch CPU kurulum satırını CUDA uyumlu PyTorch kurulumuyla değiştirip Compose servisine `gpus: all` ekleyebilirsin. Apple Silicon'da Docker konteyneri Mac'in MPS hızlandırıcısını kullanamaz; CPU'da çalışır.

## İçerik sınırları

Arayüz tek istekte en fazla 30.000 karakter kabul eder. Yüklenen `.txt` dosyası UTF-8 kodlamalı ve en fazla 1 MB olmalıdır. Model bir kez uygulama süreci başına belleğe yüklenir.
