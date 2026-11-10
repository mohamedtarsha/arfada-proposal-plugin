# ARFADA Brand Assets

The DOCX cover page can optionally include the official ARFADA logo.

The plugin does **not** ship or fabricate the logo. To use it:

1. Obtain the authorized ARFADA logo file (PNG preferred).
2. Either:
   - Place it here as `assets/brand/arfada_logo.png` (only if authorized to
     commit it to this private repo), **or**
   - Keep it anywhere on your machine and pass its path at export time:
     ```bash
     python scripts/render_docx.py <run_dir> --client --logo "C:/path/to/arfada_logo.png"
     ```

If no logo is provided, the cover renders a clean text-only ARFADA cover.

**Do not** fabricate, redraw, or AI-generate the ARFADA logo.
