# Videos iPad Monitor

Copiá acá películas y subtítulos para ver en el iPad desde **`/cinema`**.

## Archivos

| Tipo | Formato | Ejemplo |
|------|---------|---------|
| Video | **MP4** (H.264) | `Pelicula.mp4` |
| Subtítulos | **WebVTT** | `Pelicula.vtt` |

### Nombres para VLC (offline)

Usá el **mismo nombre base**:

```
Pelicula.mp4
Pelicula.vtt
```

También funciona: `Pelicula.es.vtt`, `Pelicula.en.vtt`

## En el iPad

1. iPad Monitor → **Cine**
2. **▶ Ver** — streaming con subtítulos (si hay `.vtt`)
3. **↓ Video** / **↓ Subs** — descargar para VLC sin depender del PC

## Convertir (si hace falta)

- Video: MP4 con H.264 (HandBrake, FFmpeg)
- Subs: SRT → VTT (muchas herramientas online o FFmpeg)

## Ubicación

`ipad/library/videos/`
