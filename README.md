## 👤 Owner

- **Original project**: [@heavenknows1978](https://github.com/heavenknows1978) (hass-deyecloud)
- **Coordinator/control-entity rewrite**: [@lockhaty](https://github.com/lockhaty) (hass-deyecloud)
- **License**: MIT

# 🌞 Deye Cloud Home Assistant Integration

A custom integration to connect your Home Assistant with your Deye solar inverter via the official Deye Cloud API. This version merges the two most active forks of the project:

- lockhaty's rewrite onto a `DataUpdateCoordinator`, plus `switch`/`number`/`select`/`binary_sensor` entities for controlling the inverter (work mode, energy pattern, battery type, TOU, grid peak shaving, etc.), a richer async API client, and email-based auth.
- heavenknows1978's Company ID support for installer/business accounts (fixes `ConfigEntryNotReady` when no personal stations are visible), request retries on transient network errors, a midnight stale-data guard so the Energy Dashboard doesn't get fed yesterday's totals as "today", and Vietnamese translations.

---

## 📥 Features

- 🟢 Real-time station power flow (generation, consumption, battery, grid import/export)
- 📈 Monthly and daily history sensors (current/last month, today/yesterday/day before)
- 🔌 Per-device status sensors, auto-generated from whatever your inverter reports
- 🎛️ Control entities: work mode, energy pattern, battery type, TOU schedule, solar sell, battery charge modes, grid peak shaving, smart load, and numeric parameters (max sell/solar/zero-export power, battery charge/discharge current, etc.)
- 🔃 Auto refresh every minute via a shared coordinator (no YAML needed)
- 🏢 Optional Company ID field for installer/business accounts
- 🌙 Midnight stale-data guard to keep Energy Dashboard totals accurate
- ✅ Clean setup via UI, with reconfigure support
- 🌐 English and Vietnamese translations

---

## 🛠 Installation

### Option 1: Manual

1. Download or clone this repository
2. Copy `custom_components/deyecloud/` into your `/config/custom_components/` directory in Home Assistant
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration → DeyeCloud**
5. Fill in your credentials and API details

### Option 2: Via HACS

1. Go to HACS → Integrations → 3-dot menu → Custom repositories
2. Add this repository (as Integration)
3. Search for "DeyeCloud" in HACS Integrations and install
4. Restart Home Assistant and add via UI

---

## 🔐 Get your API Credentials

### Step 1 – Register developer account

👉 Go to: <https://developer.deyecloud.com/home>
→ Register or login with your Deye Cloud credentials

### Step 2 – Create a new App

👉 Go to: <https://developer.deyecloud.com/app>
→ Click **"Create App"**
→ You'll get:

- `App ID`
- `App Secret`

Use these during integration setup.

### Step 3 – Choose correct Base URL

Depending on your region:

| Region    | Base URL                                   |
| --------- | ------------------------------------------ |
| 🇪🇺 Europe | `https://eu1-developer.deyecloud.com/v1.0` |
| 🇺🇸 US     | `https://us1-developer.deyecloud.com/v1.0` |

---

## ⚙️ Configuration Fields

| Field         | Description                                             |
| ------------- | --------------------------------------------------------- |
| Username      | Your Deye Cloud username or email                          |
| Password      | Your Deye password                                          |
| Serial Number | The serial number of the inverter you want to monitor/control |
| App ID        | From developer portal                                       |
| App Secret    | From developer portal                                       |
| Base URL      | Based on your region                                         |
| Start Month   | First month to fetch history from (e.g. `2024-01`)          |
| Company ID    | Optional. Only needed for installer/business accounts       |

---

## 🧾 Troubleshooting

- Check **Settings → System → Logs** for errors
- Ensure you restarted HA after copying files
- Ensure `custom_components/deyecloud/` has correct permissions
- If setup fails with an empty station list on an installer/business account, fill in the **Company ID** field

---

## 📄 License

[MIT License](LICENSE)
