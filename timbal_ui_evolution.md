
# Timbal Digital · Evolución de UI/UX (Propuesta Técnica)
- UI nueva con `QMainWindow`, navegación lateral (`QStackedWidget`), layouts fluidos y tema QSS con tokens.
- Páginas: **Tocar (Pads)**, **Efectos**, (luego) **Asignación**, **Dispositivos**, **Presets**.
- **High DPI** activado, `QSplitter`, `QScrollArea`, tamaños mínimos y `QSizePolicy`.
- **Persistencia** con `QSettings`/JSON (posición de splitter, pestaña activa, presets).
- **Accesibilidad**: atajos, foco visible, tooltips claros.
- **Plan incremental** con flag `--legacy-ui`/`--new-ui`.
(Archivo completo y detallado para el equipo queda en este mismo `timbal_ui_evolution.md`.)
