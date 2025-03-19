# AppImage2RPM

Nástroj na konverziu AppImage súborov do RPM balíkov pre Fedora a RHEL distribúcie.

## Funkcie

- Konverzia AppImage súborov do RPM balíkov
- Automatická extrakcia metadát z AppImage súborov
- Podpora vlastného nastavenia RPM špecifikácií
- Jednoduchá správa závislostí
- Grafické užívateľské rozhranie

## Požiadavky

- Fedora 41 alebo kompatibilná RHEL distribúcia
- Python 3.10+
- PyQt5
- RPM build nástroje

## Inštalácia

```bash
# Inštalácia závislostí
pip install -r requirements.txt

# Inštalácia RPM build nástrojov
sudo dnf install rpm-build rpmdevtools
```

## Použitie

```bash
python appimage2rpm.py
```

## Licencia

GPL-3.0
