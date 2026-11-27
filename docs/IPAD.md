# Preparar el iPad

iPad Monitor se probó en un **iPad Mini 1** (A5, 32 bits, 1024×768) con **iOS 9.3.5**. Debería funcionar en otros iPad de 32 bits con iOS 9, sin probar.

## Modo web: sin preparación

El modo web solo necesita Safari. Ver [WEB.md](WEB.md).

## Visor nativo: jailbreak

El visor se instala como paquete `.deb`, así que necesita un iPad con jailbreak y [Filza](https://www.tigisoftware.com/default/?page_id=78), que se instala desde Cydia. Este proyecto no explica cómo hacer el jailbreak: para iOS 9.3.5 de 32 bits, las herramientas habituales son Phœnix y openpwnage. Seguí una guía actualizada de la comunidad, por ejemplo [ios.cfw.guide](https://ios.cfw.guide/).

Algunos jailbreak de iOS 9 son semi‑untethered: después de apagar el iPad hay que volver a activarlo con su app. Un respring no lo pierde.

## Instalar el visor

1. Descargá `ipad-monitor-*.deb` desde **Releases** en la PC.
2. Pasalo al iPad. La forma más simple es el servidor Wi‑Fi de Filza (Filza → ícono de Wi‑Fi → abrir la dirección que muestra desde el navegador de la PC). En iOS 9, Safari no descarga bien desde GitHub por su TLS viejo.
3. En Filza, tocá el `.deb` → **Instalar**.
4. Si el ícono **iPad Monitor** no aparece, hacé un respring o ejecutá `uicache` en una terminal del iPad.

Las versiones nuevas se instalan encima de las anteriores sin perder el emparejamiento.

## Por SSH (opcional)

Con OpenSSH instalado desde Cydia, el iPad acepta `ssh root@IP_DEL_IPAD`. Los clientes de SSH modernos necesitan habilitar el algoritmo viejo del iPad:

```bash
ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa root@IP_DEL_IPAD
```

Cambiá la contraseña predeterminada (`alpine`) de `root` y `mobile` con `passwd`. Para copiar archivos sirve `scp` con las mismas opciones.

## Recomendaciones

- Conectá el iPad a la red de 5 GHz si llega con buena señal: es la menos saturada.
- Desactivá el bloqueo automático mientras lo usás como pantalla (Ajustes → Pantalla y brillo).
- En modo web, agregá `/kiosk` a la pantalla de inicio para tener el espejo a un toque.
