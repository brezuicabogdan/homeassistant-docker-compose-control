# Home Assistant Docker Compose Control (DCC)

## 📌 About

**Home Assistant Docker Compose Control (DCC)** is a custom integration for **Home Assistant** that allows you to **monitor and manage Docker Compose deployments** directly from the Home Assistant UI.

### 🔹 Features

- 🏠 **Device & Entity Creation**: Each Docker Compose project is registered as a device, with each service appearing as an entity.
- 📊 **Real-time Monitoring**: Track the status of each service (running, stopped, exited, etc.).
- 🩺 **Health Status & Attributes**: View additional container details like **health status, restart count, image version, and uptime**.
- 🔄 **Service Restarting**: Restart individual services directly from Home Assistant.
- 🛠 **Seamless Integration**: Works with Home Assistant's UI and automation engine.

---

## ❓ Why?

### **Bridging the Gap for Docker & Docker Compose Users**

Home Assistant users running **HassOS** benefit from a built-in **Supervisor** and **Add-ons**, allowing them to easily manage services like **ESPHome, Mosquitto, Zigbee2MQTT, and more** from within Home Assistant.

However, users running Home Assistant in **Docker** or **Docker Compose** **do not have access** to these built-in management tools. This results in:

- **Manual intervention** required to restart or update services.
- **No centralized way** to monitor running services.
- **Lack of Home Assistant integration**, making automation difficult.

This integration was created to **bring similar functionality to Docker Compose users**, allowing them to **monitor and manage their services** **directly from the Home Assistant UI**, just like HassOS users do with Add-ons and the Supervisor.

---

## 🚀 Installation

### **1️⃣ Install via HACS (Recommended)**

1. Open **HACS** in Home Assistant.
2. Go to **Integrations**.
3. Click the **+ (Add Integration)** button.
4. Search for **Docker Compose Control (DCC)** and install it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & Services → Add Integration** and search for **Docker Compose Control**.
7. Provide the **Docker socket path** and the **Docker Compose file path** to set up the integration.

### **2️⃣ Manual Installation**

1. Download the latest release from the [**GitHub Releases**](https://github.com/brezuicabogdan/homeassistant-docker-compose-control) page.
2. Extract and place the `custom_components/dcc` folder inside your Home Assistant `config/custom_components/` directory.
   ```bash
   mkdir -p /config/custom_components/dcc
   cp -r dcc /config/custom_components/
   ```
3. Restart Home Assistant.
4. Add the integration via **Settings → Devices & Services**.

---

## ⚙️ Configuration

### 🛠️ Prerequisites

Before configuring this integration, ensure that:

- The **Docker socket** (`/var/run/docker.sock`) and the **Docker Compose file** (e.g., `/opt/home-automation/docker-compose.yml`) are correctly mapped into your Home Assistant container.
- Home Assistant has the necessary permissions to access the Docker socket.

#### 🔹 Example: Home Assistant in Docker Compose with Required Mappings

If you are running Home Assistant inside a **Docker container**, ensure your `docker-compose.yml` includes these volume mappings:

```yaml
docker-compose:
  homeassistant:
    image: "ghcr.io/home-assistant/home-assistant:latest"
    container_name: homeassistant
    restart: unless-stopped
    volumes:
      - /path/to/your/config:/config
      - /var/run/docker.sock:/var/run/docker.sock  # Map Docker socket
      - /opt/home-automation/docker-compose.yml:/containers/docker-compose.yml  # Map Compose file
    network_mode: host
    environment:
      - TZ=Europe/Bucharest
```

Make sure to replace `/path/to/your/config`, `/var/run/docker.sock`, and `/opt/home-automation/docker-compose.yml` with your actual paths. Once installed, configure the integration by providing:

- **Docker Socket Path** (e.g., `/var/run/docker.sock`)
- **Docker Compose File Path** (e.g., `/opt/home-automation/docker-compose.yml`)

Each Docker Compose project will be registered as a **device**, with each service appearing as an **entity** under that device.

---

## 🔧 Usage

### **Entities & Attributes**

Each Docker service entity provides:

- **State**: `running`, `stopped`, `exited`, etc.
- **Health Status**: `healthy`, `unhealthy`, `starting`, or `unknown`.
- **Restart Count**: How many times the service has restarted.
- **Image**: The current Docker image version.
- **Uptime**: Start time of the container.

### **Service Control**

- Restart a service via Home Assistant **Developer Tools → Services**:
  ```json
  {
    "entity_id": "sensor.docker_homeassistant"
  }
  ```

---

## 🛣️ Project Roadmap

This project aims to provide full integration of Docker Compose into Home Assistant, making it easy to monitor and manage services. The following features are planned:

1️⃣ **Home Assistant Integration of Docker Compose Deployments** ✅ (Done)

- Each Docker Compose project appears as a device in HA.
- Each service is registered as an entity.

2️⃣ **Service Status Monitoring** ✅ (Done)

- Track container states (`running`, `stopped`, `exited`, etc.).
- Monitor container health (`healthy`, `unhealthy`, `starting`).

3️⃣ **Restart Services from Home Assistant** ✅ (Done)

- Restart services directly from the HA UI or via automation.

4️⃣ **Container Update Notifications** 🛠️ (Planned)

- Detect if an updated image is available for a service.
- Send HA notifications when updates are detected.

5️⃣ **Update Containers from Home Assistant** 🛠️ (Planned)

- Allow updating containers directly from HA.
- Trigger `docker-compose pull` and `docker-compose up -d` commands.

---

## ⚠️ Disclaimer

**This integration is provided "as is" without any guarantees.**

- **Use at your own risk.** We are not responsible for any misconfigurations that may cause issues.
- Ensure that **your Home Assistant instance has the correct permissions** to access Docker.
- Running Docker as `root` may pose security risks; consider using user-level access where possible.

---

## 🤝 Contributions

Want to improve this project? Contributions are welcome! 🛠️

### **How to Contribute**

1. Fork the repository.
2. Create a new feature branch.
3. Make your changes and commit.
4. Open a pull request.

### **Support & Discussion**

- Open an **issue** on [GitHub Issues](https://github.com/brezuicabogdan/homeassistant-docker-compose-control/issues) if you encounter problems.
- Join the **Home Assistant Community** forums for discussion.

---

## 📜 License

This project is open-source and available under the **MIT License**.

🚀 **Enjoy managing Docker Compose services within Home Assistant!** 🎉

