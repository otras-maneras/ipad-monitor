# Biblioteca iPad Monitor

Copiá acá libros en **EPUB** o **PDF** para bajarlos al iPad desde `/library`.

**Videos:** usá la subcarpeta [`videos/`](videos/) y abrí `/cinema` en el iPad.

## Cómo agregar libros

1. Copiá archivos `.epub` o `.pdf` a esta carpeta (desde el explorador de archivos).
2. Reiniciá iPad Monitor en el PC si ya estaba corriendo (o esperá unos segundos y recargá la página en el iPad).
3. En el iPad: iPad Monitor → **Biblioteca** → tocá el libro.

## Leer en iBooks

1. Tocá el libro en la lista.
2. Cuando se abra o descargue, tocá **Compartir** (icono cuadrado con flecha).
3. Elegí **Abrir en iBooks** (o **Copiar a iBooks**).

## Formatos

| Formato | iBooks iOS 9 |
|---------|----------------|
| `.epub` | ✅ Recomendado |
| `.pdf`  | ✅ Funciona |

No uses MOBI ni AZW; convertí con Calibre a EPUB si hace falta.

## Ubicación

Carpeta por defecto del proyecto: `ipad/library/`

Configurable en `config.json` con `"library_dir": "library"`.
