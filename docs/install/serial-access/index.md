---
title: Serial access
---

# Serial access

The install runs at the serial console of the control board, because the
factory firmware offers no SSH. This page tells you the three ways to reach
that console: the Micro-USB port that early machines have, the OpenGlow
serial adapter, or a soldered FTDI cable.

!!! danger "1.8 V only"

    The console domain of the control board is 1.8 V. **Never connect a
    3.3 V or 5 V adapter to these test points.** Anything higher than 1.8 V
    irreversibly destroys the control board.

The console settings are **115200 8N1** in every case. Select a color
terminal with UTF-8 encoding for the best experience from ForgeFIRM (PuTTY
works well). The console test points and their nets are in
[Buses](../../technical/machine/buses.md).

The console login is `root` with no password, on the factory firmware and
on ForgeFIRM alike. On ForgeFIRM root works at the console only: SSH refuses
root, and the panel's account opens SSH
([The control panel](../../usage/control-panel.md#login)).

| Page | Contents |
|---|---|
| [Facgtory USB Console](factory-usb.md) | Early production machines with a factory installed console adapter. |
| [OpenGlow Console Adapter](openglow-adapter.md) | The one-stage installer, run at the factory console, and the first boot. |
