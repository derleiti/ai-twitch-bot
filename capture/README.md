# Optional stream capture on a desktop

The OBS capture service uploads only the active OBS program scene while streaming. Enable the local OBS WebSocket server with authentication enabled. The password is read from the local OBS configuration; it is never transmitted to the SSH server. Use a trusted SSH destination with an already verified host key. The server writes only the latest JPEG atomically under its user's home directory.

Configure the destination explicitly in ~/.config/zephyr-capture/capture.env (see capture.env.example). Install the Python dependency from capture/requirements.txt in the capture service's separate environment. Install the service and script under the paths in zephyr-capture.service; start it only when desired.

The Spectacle alternative is a MANUALLY STARTED primary-monitor capture service, not stream-aware. It captures screen contents even if OBS is not streaming, and refuses unexpected monitor geometry. Review the geometry and avoid displaying private information while it is running. Do not enable it at login. Stop either capture service when finished.

The bot can use capture/server.env.example as a configuration template. Supply credentials separately and never commit actual environment files.
