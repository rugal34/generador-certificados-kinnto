from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageFont

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:  # pragma: no cover - shown in the Streamlit UI
    cloudinary = None


SUPPORTED_IMAGES = ("png", "jpg", "jpeg")
SUPPORTED_FONTS = ("ttf", "otf")
DEFAULT_CLOUDINARY_FOLDER = "certificados"
APP_DIR = Path(__file__).resolve().parent
ASSETS_DIR = APP_DIR / "assets"
GENERATED_DIR = APP_DIR / "certificados_guardados"
PRESETS_DIR = APP_DIR / "presets"
COMPONENTS_DIR = APP_DIR / "components"
COORDINATE_EDITOR_DIR = COMPONENTS_DIR / "coordinate_editor"
BRAND_LOGO_PATH = ASSETS_DIR / "brand" / "kinnto-space-wolf-transparent.png"
DEFAULT_FONT_CANDIDATES = (
    ASSETS_DIR / "Figtree-Bold.ttf",
    ASSETS_DIR / "Figtree-Bold (1).ttf",
    ASSETS_DIR / "Figtree.ttf",
)
CSV_TEMPLATE = "country_code,cellphone,nombre,certificado\n57,3001234567,Ana Martinez,\n57,3007654321,Juan Gomez,\n"
coordinate_editor_component = components.declare_component(
    "kinnto_coordinate_editor",
    path=str(COORDINATE_EDITOR_DIR),
)


@dataclass
class TextStyle:
    x: int
    y: int
    max_width: int
    font_size: int
    min_font_size: int
    color: str
    align_center: bool


def slugify(value: str) -> str:
    clean = unicodedata.normalize("NFKD", str(value))
    clean = clean.encode("ascii", "ignore").decode("ascii")
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", clean).strip("_").lower()
    return clean or "certificado"


def read_csv(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.getvalue()
    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", encoding=encoding)
        except Exception:
            continue
    return pd.read_csv(io.BytesIO(raw))


def get_font(font_bytes: bytes | None, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if not font_bytes:
        return ImageFont.load_default()

    return ImageFont.truetype(io.BytesIO(font_bytes), size)


def get_default_font_bytes() -> tuple[bytes | None, str]:
    for font_path in DEFAULT_FONT_CANDIDATES:
        if font_path.exists():
            return font_path.read_bytes(), font_path.name
    return None, "Fuente basica"


def text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    try:
        return int(draw.textlength(text, font=font))
    except Exception:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]


def fit_font(draw: ImageDraw.ImageDraw, text: str, font_bytes: bytes | None, style: TextStyle):
    size = style.font_size
    while size >= style.min_font_size:
        font = get_font(font_bytes, size)
        if text_width(draw, text, font) <= style.max_width:
            return font
        size -= 2
    return get_font(font_bytes, style.min_font_size)


def draw_single_line(
    img: Image.Image,
    text: str,
    font_bytes: bytes | None,
    style: TextStyle,
) -> Image.Image:
    if not text:
        return img

    draw = ImageDraw.Draw(img)
    font = fit_font(draw, text, font_bytes, style)
    width = text_width(draw, text, font)
    x = (img.width - width) // 2 if style.align_center else style.x
    draw.text((x, style.y), text, font=font, fill=style.color)
    return img


def compose_name(row: pd.Series, first_col: str, last_col: str | None, full_name_col: str | None) -> str:
    if full_name_col and full_name_col != "No usar":
        return str(row.get(full_name_col, "")).strip()

    pieces = [str(row.get(first_col, "")).strip()]
    if last_col and last_col != "No usar":
        pieces.append(str(row.get(last_col, "")).strip())
    return " ".join(piece for piece in pieces if piece and piece.lower() != "nan").strip()


def generate_certificate(
    base_bytes: bytes,
    font_bytes: bytes | None,
    name: str,
    name_style: TextStyle,
    document_text: str | None,
    document_style: TextStyle,
) -> bytes:
    img = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
    img = draw_single_line(img, name, font_bytes, name_style)
    if document_text:
        img = draw_single_line(img, document_text, font_bytes, document_style)

    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output.getvalue()


def upload_to_cloudinary(image_bytes: bytes, folder: str, public_id: str) -> str:
    if cloudinary is None:
        raise RuntimeError("Cloudinary no esta instalado.")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_image:
        tmp_image.write(image_bytes)
        tmp_path = tmp_image.name

    try:
        response = cloudinary.uploader.upload(
            tmp_path,
            public_id=public_id,
            folder=folder,
            overwrite=True,
            resource_type="image",
        )
        return response["secure_url"]
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def secret_value(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(os.getenv(name.upper(), value or "")).strip()


def get_cloudinary_settings() -> dict[str, str]:
    return {
        "cloud_name": secret_value("cloudinary_cloud_name"),
        "api_key": secret_value("cloudinary_api_key"),
        "api_secret": secret_value("cloudinary_api_secret"),
        "folder": secret_value("cloudinary_folder", DEFAULT_CLOUDINARY_FOLDER),
    }


def has_cloudinary_settings(settings: dict[str, str]) -> bool:
    return bool(settings["cloud_name"] and settings["api_key"] and settings["api_secret"])


def build_single_person_df(first_name: str, last_name: str, document: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "first name": first_name.strip(),
                "last name": last_name.strip(),
                "document": document.strip(),
            }
        ]
    )


def build_zip_from_folder(folder: Path) -> bytes:
    files = []
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            files.append((str(path.relative_to(folder)), path.read_bytes()))
    return build_zip(files)


def save_generation(
    rows: list[dict],
    files: list[tuple[str, bytes]],
    source_label: str,
) -> Path:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    first_name = rows[0]["nombre"] if rows else "certificados"
    batch_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify(source_label or first_name)}"
    batch_dir = GENERATED_DIR / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in files:
        (batch_dir / filename).write_bytes(content)

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(rows),
        "source": source_label,
        "rows": rows,
    }
    (batch_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return batch_dir


def saved_batches(limit: int = 8) -> list[Path]:
    if not GENERATED_DIR.exists():
        return []
    folders = [
        path
        for path in GENERATED_DIR.iterdir()
        if path.is_dir() and (path / "metadata.json").exists()
    ]
    return sorted(folders, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]


def saved_presets() -> list[Path]:
    if not PRESETS_DIR.exists():
        return []
    return sorted(PRESETS_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)


def read_preset(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_preset(preset: dict) -> Path:
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    path = PRESETS_DIR / f"{slugify(preset['name'])}.json"
    preset["saved_at"] = datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def apply_preset_to_session(preset: dict) -> None:
    name_text = preset.get("name_text", {})
    document_text = preset.get("document_text", {})

    mappings = {
        "center_name": name_text.get("align_center"),
        "name_position_x": name_text.get("x"),
        "name_position_y": name_text.get("y"),
        "name_style_size": name_text.get("font_size"),
        "name_style_min_size": name_text.get("min_font_size"),
        "name_style_width": name_text.get("max_width"),
        "name_style_color": name_text.get("color"),
        "center_doc": document_text.get("align_center"),
        "document_prefix": document_text.get("prefix"),
        "document_position_x": document_text.get("x"),
        "document_position_y": document_text.get("y"),
        "document_style_size": document_text.get("font_size"),
        "document_style_min_size": document_text.get("min_font_size"),
        "document_style_width": document_text.get("max_width"),
        "document_style_color": document_text.get("color"),
        "cloud_folder_input": preset.get("cloudinary_folder"),
    }
    for key, value in mappings.items():
        if value is not None:
            st.session_state[key] = value


def build_preset_data(
    preset_name: str,
    image_label: str,
    image_size: tuple[int, int],
    name_style: TextStyle,
    document_style: TextStyle,
    document_prefix: str,
    cloud_folder: str,
) -> dict:
    return {
        "version": 1,
        "name": preset_name.strip(),
        "source_image": image_label,
        "image_size": {"width": image_size[0], "height": image_size[1]},
        "cloudinary_folder": cloud_folder,
        "name_text": {
            "x": name_style.x,
            "y": name_style.y,
            "max_width": name_style.max_width,
            "font_size": name_style.font_size,
            "min_font_size": name_style.min_font_size,
            "color": name_style.color,
            "align_center": name_style.align_center,
        },
        "document_text": {
            "prefix": document_prefix,
            "x": document_style.x,
            "y": document_style.y,
            "max_width": document_style.max_width,
            "font_size": document_style.font_size,
            "min_font_size": document_style.min_font_size,
            "color": document_style.color,
            "align_center": document_style.align_center,
        },
    }


def build_zip(files: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for filename, content in files:
            bundle.writestr(filename, content)
    output.seek(0)
    return output.getvalue()


def image_data_uri(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    output = io.BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_certificate_preview(image_bytes: bytes) -> None:
    st.markdown(
        f"""
        <div class="certificate-preview-shell">
            <img src="{image_data_uri(image_bytes)}" alt="Vista previa del certificado" />
        </div>
        """,
        unsafe_allow_html=True,
    )


def editor_text_style(style: TextStyle, label: str, image_width: int) -> dict:
    x = max(0, (image_width - style.max_width) // 2)
    return {
        "x": x,
        "y": style.y,
        "maxWidth": style.max_width,
        "fontSize": style.font_size,
        "color": style.color,
        "text": label,
        "alignCenter": True,
    }


def apply_editor_value(value: dict | None) -> bool:
    if not isinstance(value, dict):
        return False

    target = value.get("target")
    if target not in {"name", "document"}:
        return False

    try:
        y = max(0, int(value.get("y", 0)))
    except (TypeError, ValueError):
        return False

    prefix = "name_position" if target == "name" else "document_position"
    center_key = "center_name" if target == "name" else "center_doc"
    changed = (
        st.session_state.get(f"{prefix}_y") != y
        or st.session_state.get(center_key) is not True
    )
    if not changed:
        return False

    st.session_state[f"{prefix}_y"] = y
    st.session_state[center_key] = True
    return True


def preferred_column(columns: list[str], candidates: list[str], fallback: str | None = None) -> str:
    normalized = {str(column).strip().lower(): column for column in columns}
    for candidate in candidates:
        match = normalized.get(candidate.lower())
        if match is not None:
            return match
    return fallback if fallback is not None else columns[0]


def build_treble_output_csv(source_df: pd.DataFrame, rows: list[dict]) -> bytes:
    treble_df = source_df.copy()
    if "certificado" not in treble_df.columns:
        treble_df["certificado"] = ""

    for row in rows:
        source_index = row.get("source_index")
        if source_index in treble_df.index:
            treble_df.at[source_index, "certificado"] = row.get("certificado", "")

    return treble_df.to_csv(index=False).encode("utf-8-sig")


def adjust_position(prefix: str, axis: str, delta: int) -> None:
    key = f"{prefix}_{axis}"
    st.session_state[key] = max(0, int(st.session_state.get(key, 0)) + delta)


def position_inputs(
    title: str,
    prefix: str,
    max_x: int,
    max_y: int,
    default_x: int,
    default_y: int,
    disable_x: bool = False,
    disabled: bool = False,
) -> tuple[int, int]:
    st.caption(title)
    st.session_state.setdefault(f"{prefix}_x", default_x)
    st.session_state.setdefault(f"{prefix}_y", default_y)
    st.session_state[f"{prefix}_x"] = min(max(0, int(st.session_state[f"{prefix}_x"])), max_x)
    st.session_state[f"{prefix}_y"] = min(max(0, int(st.session_state[f"{prefix}_y"])), max_y)

    y_key = f"{prefix}_y"
    slider_key = f"{prefix}_y_slider"
    last_y_key = f"{prefix}_last_y"
    last_y = int(st.session_state.get(last_y_key, st.session_state[y_key]))
    slider_y_value = int(st.session_state.get(slider_key, st.session_state[y_key]))

    if slider_y_value != last_y:
        st.session_state[y_key] = min(max(0, slider_y_value), max_y)
    elif int(st.session_state[y_key]) != last_y or slider_key not in st.session_state:
        st.session_state[slider_key] = st.session_state[y_key]
    st.session_state[last_y_key] = st.session_state[y_key]

    slider_y = st.slider(
        "Altura",
        min_value=0,
        max_value=max_y,
        value=st.session_state[y_key],
        step=5,
        key=slider_key,
        disabled=disabled,
    )
    st.session_state[y_key] = int(slider_y)
    st.session_state[last_y_key] = int(slider_y)

    if disable_x:
        x = max_x // 2
        y = st.number_input(
            "Y fino",
            min_value=0,
            max_value=max_y,
            step=1,
            key=y_key,
            disabled=disabled,
        )
    else:
        cols = st.columns(2)
        with cols[0]:
            x = st.number_input(
                "X fino",
                min_value=0,
                max_value=max_x,
                step=1,
                key=f"{prefix}_x",
                disabled=disabled,
            )
        with cols[1]:
            y = st.number_input(
                "Y fino",
                min_value=0,
                max_value=max_y,
                step=1,
                key=y_key,
                disabled=disabled,
            )
    return int(x), int(y)


def style_inputs(
    prefix: str,
    max_x: int,
    default_size: int,
    default_min_size: int,
    default_width: int,
    default_color: str,
    disabled: bool = False,
) -> tuple[int, int, int, str]:
    st.session_state.setdefault(f"{prefix}_size", default_size)
    st.session_state.setdefault(f"{prefix}_min_size", default_min_size)
    st.session_state.setdefault(f"{prefix}_width", min(default_width, max_x))
    st.session_state.setdefault(f"{prefix}_color", default_color)
    st.session_state[f"{prefix}_size"] = min(max(8, int(st.session_state[f"{prefix}_size"])), 180)
    st.session_state[f"{prefix}_min_size"] = min(max(8, int(st.session_state[f"{prefix}_min_size"])), 100)
    st.session_state[f"{prefix}_width"] = min(max(100, int(st.session_state[f"{prefix}_width"])), max_x)

    cols = st.columns([.9, .9, 1.1, .75])
    with cols[0]:
        size = st.number_input(
            "Tamano",
            min_value=8,
            max_value=180,
            value=st.session_state[f"{prefix}_size"],
            step=1,
            key=f"{prefix}_size",
            disabled=disabled,
        )
    with cols[1]:
        min_size = st.number_input(
            "Minimo",
            min_value=8,
            max_value=100,
            value=st.session_state[f"{prefix}_min_size"],
            step=1,
            key=f"{prefix}_min_size",
            disabled=disabled,
        )
    with cols[2]:
        width = st.number_input(
            "Ancho",
            min_value=100,
            max_value=max_x,
            value=st.session_state[f"{prefix}_width"],
            step=1,
            key=f"{prefix}_width",
            disabled=disabled,
        )
    with cols[3]:
        color = st.color_picker(
            "Color",
            default_color,
            key=f"{prefix}_color",
            disabled=disabled,
        )
    return int(size), int(min_size), int(width), color


def configure_page() -> None:
    st.set_page_config(page_title="Kinnto Certificados", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            --ink: #f7fbff;
            --muted: #a9b6c9;
            --space: #07070d;
            --panel: rgba(17, 19, 34, .78);
            --line: rgba(104, 246, 255, .34);
            --lime: #27ff73;
            --cyan: #36f6ff;
            --coral: #ff4f67;
            --violet: #7a4dff;
            --gold: #ffc83d;
        }
        .stApp {
            background:
                radial-gradient(circle at 78% 12%, rgba(54, 246, 255, .18), transparent 24rem),
                radial-gradient(circle at 16% 22%, rgba(122, 77, 255, .16), transparent 22rem),
                radial-gradient(circle at 38% 86%, rgba(39, 255, 115, .12), transparent 24rem),
                linear-gradient(135deg, rgba(255,255,255,.08) 1px, transparent 1px),
                var(--space);
            background-size: auto, auto, auto, 34px 34px, auto;
            color: var(--ink);
        }
        h1, h2, h3, label, p, span, div {
            letter-spacing: 0 !important;
        }
        h1 {
            color: #fff !important;
            font-size: clamp(2.4rem, 5vw, 5.3rem) !important;
            line-height: .94 !important;
            font-weight: 950 !important;
            margin-bottom: .25rem !important;
            text-shadow: 0 0 24px rgba(54, 246, 255, .25);
        }
        h2, h3 {
            color: #fff !important;
            font-weight: 900 !important;
        }
        p, span, label, div {
            color: var(--ink);
        }
        label, [data-testid="stWidgetLabel"] p {
            color: #f7fbff !important;
            font-weight: 800 !important;
        }
        [data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 50% 0%, rgba(54, 246, 255, .2), transparent 14rem),
                #090912;
            color: white;
            border-right: 1px solid rgba(54, 246, 255, .26);
        }
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {
            color: white;
        }
        [data-testid="stFileUploader"] {
            background: rgba(12, 14, 26, .82);
            border: 1px solid rgba(54, 246, 255, .32);
            border-radius: 8px;
            padding: .8rem;
            box-shadow: 0 0 0 1px rgba(255,255,255,.04), 0 18px 42px rgba(0,0,0,.28);
        }
        [data-testid="stFileUploader"] section {
            background: #f7fbff !important;
            border: 1px dashed rgba(7, 17, 31, .28) !important;
            border-radius: 8px !important;
        }
        [data-testid="stFileUploader"] section,
        [data-testid="stFileUploader"] section * {
            color: #07111f !important;
        }
        [data-testid="stFileUploader"] button {
            border-radius: 8px !important;
            background: #ffffff !important;
            border: 1px solid rgba(7, 17, 31, .18) !important;
            color: #07111f !important;
            box-shadow: none !important;
        }
        [data-testid="stFileUploaderFile"] {
            background: rgba(54, 246, 255, .1) !important;
            border: 1px solid rgba(54, 246, 255, .28) !important;
            border-radius: 8px !important;
            color: #f7fbff !important;
        }
        [data-testid="stFileUploaderFile"] * {
            color: #f7fbff !important;
        }
        .stButton > button,
        .stDownloadButton > button {
            border: 1px solid rgba(39, 255, 115, .74);
            border-radius: 999px;
            background: var(--lime);
            color: #06100b;
            font-weight: 900;
            min-height: 44px;
            box-shadow: 0 0 18px rgba(39, 255, 115, .22);
        }
        .stButton > button:hover,
        .stDownloadButton > button:hover {
            border: 1px solid #fff;
            color: #06100b;
            transform: translate(1px, 1px);
            box-shadow: 0 0 28px rgba(54, 246, 255, .25);
        }
        [data-testid="stNumberInput"] input,
        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background: #f7fbff !important;
            border-color: rgba(54, 246, 255, .34) !important;
            color: #07111f !important;
            font-weight: 850 !important;
        }
        [data-testid="stSelectbox"] [data-baseweb="select"] span,
        [data-testid="stSelectbox"] [data-baseweb="select"] svg {
            color: #07111f !important;
            fill: #07111f !important;
        }
        [data-baseweb="popover"] [role="listbox"],
        [data-baseweb="popover"] ul,
        [data-baseweb="popover"] li {
            background: #f7fbff !important;
            color: #07111f !important;
        }
        [data-baseweb="popover"] [role="option"],
        [data-baseweb="popover"] [role="option"] *,
        [data-baseweb="popover"] li,
        [data-baseweb="popover"] li * {
            color: #07111f !important;
            fill: #07111f !important;
        }
        [data-baseweb="popover"] [aria-selected="true"],
        [data-baseweb="popover"] [role="option"]:hover {
            background: #e7eef6 !important;
            color: #07111f !important;
        }
        [data-testid="stNumberInput"] button {
            background: #f7fbff !important;
            color: #07111f !important;
            border-color: rgba(7, 17, 31, .12) !important;
            font-weight: 950 !important;
        }
        [data-testid="stNumberInput"] {
            min-width: 0 !important;
        }
        [data-testid="stNumberInput"] input {
            min-width: 0 !important;
        }
        [data-testid="stMetric"],
        [data-testid="stAlert"] {
            border-radius: 8px;
            background: rgba(12, 14, 26, .72);
            border: 1px solid rgba(54, 246, 255, .18);
        }
        .kinnto-strip {
            display: inline-block;
            background: linear-gradient(90deg, var(--lime), var(--cyan));
            color: #06100b;
            border-radius: 999px;
            padding: .35rem .8rem;
            font-weight: 850;
            margin-bottom: .6rem;
        }
        .kinnto-note {
            background: rgba(39, 255, 115, .12);
            color: #eafff3;
            border: 1px solid rgba(39, 255, 115, .45);
            box-shadow: 0 0 20px rgba(39, 255, 115, .12);
            border-radius: 8px;
            padding: .7rem .9rem;
            font-weight: 800;
        }
        .mission-hero {
            border: 1px solid rgba(54, 246, 255, .24);
            background:
                linear-gradient(120deg, rgba(255,255,255,.07), rgba(255,255,255,.02)),
                rgba(8, 9, 18, .78);
            border-radius: 8px;
            padding: 1.1rem 1.2rem;
            margin-bottom: 1rem;
            box-shadow: 0 24px 80px rgba(0,0,0,.32);
        }
        .mission-copy {
            color: var(--muted);
            font-weight: 700;
            max-width: 54rem;
        }
        .signal-row {
            display: flex;
            gap: .5rem;
            flex-wrap: wrap;
            margin-top: .75rem;
        }
        .signal-chip {
            border: 1px solid rgba(54, 246, 255, .28);
            background: rgba(255,255,255,.06);
            border-radius: 999px;
            padding: .32rem .68rem;
            color: #dffcff;
            font-size: .84rem;
            font-weight: 850;
        }
        .signal-chip.hot {
            border-color: rgba(255, 79, 103, .48);
            color: #ffdce2;
        }
        .block-container {
            padding-top: 2rem;
        }
        div[data-testid="column"] {
            min-width: 0;
        }
        .compact-tools {
            border: 1px solid rgba(54, 246, 255, .18);
            background: rgba(7, 8, 16, .42);
            border-radius: 8px;
            padding: .75rem;
            margin-bottom: .7rem;
        }
        .compact-tools h3 {
            margin-top: 0 !important;
        }
        .compact-tools .stButton > button {
            min-height: 36px;
            padding: .2rem .35rem;
        }
        .certificate-preview-shell {
            display: flex;
            justify-content: center;
            align-items: center;
            max-height: min(64vh, 620px);
            width: 100%;
            overflow: hidden;
            border-radius: 8px;
        }
        .certificate-preview-shell img {
            display: block;
            max-width: 100%;
            max-height: min(64vh, 620px);
            width: auto;
            height: auto;
            object-fit: contain;
            border-radius: 8px;
            border: 1px solid rgba(54, 246, 255, .22);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    configure_page()
    cloudinary_settings = get_cloudinary_settings()
    cloudinary_ready = cloudinary is not None and has_cloudinary_settings(cloudinary_settings)
    if cloudinary_ready:
        cloudinary.config(
            cloud_name=cloudinary_settings["cloud_name"],
            api_key=cloudinary_settings["api_key"],
            api_secret=cloudinary_settings["api_secret"],
        )

    with st.sidebar:
        if BRAND_LOGO_PATH.exists():
            st.image(str(BRAND_LOGO_PATH), use_container_width=True)
        st.header("Presets")
        presets = saved_presets()
        if presets:
            preset_labels = []
            for preset_path in presets:
                preset = read_preset(preset_path) or {}
                preset_labels.append(preset.get("name") or preset_path.stem)
            selected_preset_index = st.selectbox(
                "Cargar ajuste",
                range(len(presets)),
                format_func=lambda index: preset_labels[index],
            )
            if st.button("Aplicar preset", use_container_width=True):
                preset = read_preset(presets[int(selected_preset_index)])
                if preset:
                    apply_preset_to_session(preset)
                    st.success("Preset aplicado.")
                    st.rerun()
                else:
                    st.error("No se pudo leer el preset.")
        else:
            st.caption("Aun no hay presets guardados.")
        st.divider()
        st.header("Cloudinary")
        if cloudinary_ready:
            st.success("Conectado")
            upload_enabled = st.toggle("Subir links automaticamente", value=True)
            st.session_state.setdefault("cloud_folder_input", cloudinary_settings["folder"])
            cloud_folder = st.text_input("Carpeta", key="cloud_folder_input")
        else:
            st.warning("Pendiente de configuracion local")
            st.caption("Agrega las llaves una sola vez en .streamlit/secrets.toml.")
            upload_enabled = False
            cloud_folder = st.session_state.get("cloud_folder_input", DEFAULT_CLOUDINARY_FOLDER)
        st.divider()
        save_local = st.toggle("Guardar copia local", value=True)
        st.header("Guardados")
        batches = saved_batches()
        if batches:
            for batch in batches:
                metadata_path = batch / "metadata.json"
                label = batch.name
                if metadata_path.exists():
                    try:
                        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                        label = f"{metadata.get('count', 0)} cert. - {batch.name}"
                    except Exception:
                        pass
                st.download_button(
                    label,
                    data=build_zip_from_folder(batch),
                    file_name=f"{batch.name}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )
        else:
            st.caption("Aun no hay certificados guardados.")

    hero_text, hero_logo = st.columns([1.45, .55], vertical_alignment="center")
    with hero_text:
        st.markdown(
            """
            <div class="mission-hero">
                <span class="kinnto-strip">CERTIFICATE LAB</span>
                <h1>Kinnto Certificados</h1>
                <div class="mission-copy">SER 1% MEJOR CADA DIA</div>
                <div class="signal-row">
                    <span class="signal-chip">Subir</span>
                    <span class="signal-chip">Previsualizar</span>
                    <span class="signal-chip">Generar</span>
                    <span class="signal-chip hot">Cloudinary listo</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_logo:
        if BRAND_LOGO_PATH.exists():
            st.image(str(BRAND_LOGO_PATH), use_container_width=True)

    upload_col, preview_col = st.columns([.82, 1.38], gap="large")

    with upload_col:
        st.subheader("Carga base")
        base_file = st.file_uploader("Arte del certificado", type=SUPPORTED_IMAGES)
        if base_file:
            st.success(f"Arte cargado: {base_file.name}")
        default_font_bytes, default_font_label = get_default_font_bytes()
        font_file = st.file_uploader("Fuente opcional", type=SUPPORTED_FONTS)
        if font_file:
            font_bytes = font_file.getvalue()
            st.success(f"Fuente cargada: {font_file.name}")
        else:
            font_bytes = default_font_bytes
            st.caption(f"Fuente activa: {default_font_label}")

        st.download_button(
            "Descargar plantilla CSV",
            data=CSV_TEMPLATE.encode("utf-8-sig"),
            file_name="plantilla_certificados.csv",
            mime="text/csv",
            use_container_width=True,
        )

        source_mode = st.radio("Entrada de personas", ["CSV", "Una persona"], horizontal=True)
        if source_mode == "CSV":
            csv_file = st.file_uploader("CSV", type=("csv",))
            if csv_file:
                df = read_csv(csv_file)
                source_label = Path(csv_file.name).stem
                st.success(f"CSV cargado: {csv_file.name}")
            else:
                df = pd.DataFrame()
                source_label = "csv"
        else:
            person_cols = st.columns(2)
            with person_cols[0]:
                manual_first_name = st.text_input("Nombre")
            with person_cols[1]:
                manual_last_name = st.text_input("Apellido")
            manual_document = st.text_input("Documento opcional")
            df = build_single_person_df(manual_first_name, manual_last_name, manual_document)
            source_label = slugify(f"{manual_first_name}_{manual_last_name}") or "una_persona"

        if not base_file:
            st.markdown(
                '<div class="kinnto-note">Carga una imagen base para empezar a previsualizar.</div>',
                unsafe_allow_html=True,
            )
            return
        if source_mode == "CSV" and df.empty:
            st.markdown(
                '<div class="kinnto-note">Carga un CSV o usa la plantilla para empezar.</div>',
                unsafe_allow_html=True,
            )
            return

        df = df.dropna(how="all").reset_index(drop=True)
        columns = list(df.columns)
        if not columns or df.empty:
            st.error("El CSV no tiene datos disponibles.")
            return

        st.subheader("Campos")
        if source_mode == "CSV":
            selector_cols = st.columns(2)
            with selector_cols[0]:
                full_name_options = ["No usar"] + columns
                full_name_default = full_name_options.index(
                    preferred_column(columns, ["nombre", "full name", "name"], "No usar")
                )
                full_name_col = st.selectbox(
                    "Nombre completo",
                    full_name_options,
                    index=full_name_default,
                )
                first_default_col = preferred_column(columns, ["first name", "nombre"], columns[0])
                first_default = columns.index(first_default_col)
                first_col = st.selectbox("Nombre", columns, index=first_default)
            with selector_cols[1]:
                last_options = ["No usar"] + columns
                last_default = last_options.index(
                    preferred_column(columns, ["last name", "apellido"], "No usar")
                )
                last_col = st.selectbox("Apellido", last_options, index=last_default)
                document_options = ["No usar"] + columns
                document_default = document_options.index(
                    preferred_column(columns, ["document", "documento", "cedula"], "No usar")
                )
                document_col = st.selectbox("Documento", document_options, index=document_default)
        else:
            full_name_col = "No usar"
            first_col = "first name"
            last_col = "last name"
            document_col = "document" if str(df.iloc[0].get("document", "")).strip() else "No usar"
            st.caption("Modo rapido: se usa nombre, apellido y documento opcional.")

        include_document = document_col != "No usar"
        st.session_state.setdefault("document_prefix", "Documento:")
        document_prefix = (
            st.text_input("Prefijo documento", key="document_prefix")
            if include_document
            else st.session_state.get("document_prefix", "")
        )

        st.subheader("Nombre en certificado")
        base_image = Image.open(io.BytesIO(base_file.getvalue()))
        max_x = max(base_image.width, 1)
        max_y = max(base_image.height, 1)

        st.session_state["center_name"] = True
        center_name = True
        name_x, name_y = position_inputs(
            "Mover nombre",
            "name_position",
            max_x,
            max_y,
            max_x // 2,
            int(max_y * .57),
            disable_x=center_name,
        )
        name_size, name_min_size, name_width, name_color = style_inputs(
            "name_style",
            max_x,
            78,
            28,
            min(950, max_x),
            "#FFFFFF",
        )

        doc_x = max_x // 2
        doc_y = int(max_y * .64)
        doc_size = 38
        doc_min_size = 18
        doc_width = min(720, max_x)
        doc_color = "#FFFFFF"
        center_doc = True
        if include_document:
            with st.expander("Documento opcional", expanded=False):
                st.session_state["center_doc"] = True
                center_doc = True
                doc_x, doc_y = position_inputs(
                    "Mover documento",
                    "document_position",
                    max_x,
                    max_y,
                    max_x // 2,
                    int(max_y * .64),
                    disable_x=center_doc,
                )
                doc_size, doc_min_size, doc_width, doc_color = style_inputs(
                    "document_style",
                    max_x,
                    38,
                    18,
                    min(720, max_x),
                    "#FFFFFF",
                )

        st.subheader("Preset de diseno")
        preset_name = st.text_input(
            "Nombre del preset",
            placeholder="Ej. Certificado onboarding",
            key="preset_name_input",
        )
        name_style = TextStyle(
            x=name_x,
            y=name_y,
            max_width=name_width,
            font_size=name_size,
            min_font_size=name_min_size,
            color=name_color,
            align_center=center_name,
        )
        document_style = TextStyle(
            x=doc_x,
            y=doc_y,
            max_width=doc_width,
            font_size=doc_size,
            min_font_size=doc_min_size,
            color=doc_color,
            align_center=center_doc,
        )
        if st.button("Guardar preset", use_container_width=True):
            if not preset_name.strip():
                st.warning("Ponle un nombre al preset.")
            else:
                preset = build_preset_data(
                    preset_name,
                    getattr(base_file, "name", "certificado"),
                    (base_image.width, base_image.height),
                    name_style,
                    document_style,
                    document_prefix,
                    cloud_folder,
                )
                preset_path = save_preset(preset)
                st.success(f"Preset guardado: {preset_path.stem}")

    with preview_col:
        st.subheader("Vista previa orbital")
        selected_row = st.slider("Fila", 1, len(df), 1, step=1) - 1 if len(df) > 1 else 0
        row = df.iloc[selected_row]
        name = compose_name(row, first_col, last_col, full_name_col)
        doc_value = ""
        if include_document:
            raw_doc = str(row.get(document_col, "")).strip()
            doc_value = f"{document_prefix} {raw_doc}".strip() if raw_doc and raw_doc.lower() != "nan" else ""

        preview_bytes = generate_certificate(
            base_file.getvalue(),
            font_bytes,
            name,
            name_style,
            doc_value,
            document_style,
        )

        editor_enabled = st.toggle("Editar con mouse", value=False, key="mouse_editor_enabled")
        editor_target = "name"
        if editor_enabled and include_document:
            target_label = st.radio(
                "Texto activo",
                ["Nombre", "Documento"],
                horizontal=True,
                key="mouse_editor_target",
            )
            editor_target = "document" if target_label == "Documento" else "name"

        if editor_enabled:
            editor_value = coordinate_editor_component(
                imageData=image_data_uri(base_file.getvalue()),
                imageWidth=base_image.width,
                imageHeight=base_image.height,
                target=editor_target,
                nameStyle=editor_text_style(name_style, name or "Nombre", base_image.width),
                documentStyle=editor_text_style(document_style, doc_value or "Documento", base_image.width),
                showDocument=bool(doc_value),
                lockHorizontalCenter=True,
                maxEditorHeightPx=560,
                key="coordinate_editor",
            )
            if apply_editor_value(editor_value):
                st.rerun()
        else:
            render_certificate_preview(preview_bytes)

        metric_cols = st.columns(3)
        metric_cols[0].metric("Personas", len(df))
        metric_cols[1].metric("Campos", len(columns))
        metric_cols[2].metric("Doc.", "Si" if include_document else "No")

        generate = st.button("Generar certificados", type="primary", use_container_width=True)

        if generate:
            if upload_enabled and cloudinary is None:
                st.error("Instala cloudinary para activar la subida.")
                return
            if upload_enabled and not cloudinary_ready:
                st.error("Faltan credenciales locales de Cloudinary.")
                return

            files: list[tuple[str, bytes]] = []
            rows = []
            errors = []
            progress = st.progress(0)

            for index, current_row in df.iterrows():
                current_name = compose_name(current_row, first_col, last_col, full_name_col)
                if not current_name:
                    errors.append({"fila": index + 1, "error": "Nombre vacio"})
                    continue

                current_doc = ""
                if include_document:
                    raw_doc = str(current_row.get(document_col, "")).strip()
                    current_doc = (
                        f"{document_prefix} {raw_doc}".strip()
                        if raw_doc and raw_doc.lower() != "nan"
                        else ""
                    )

                try:
                    image_bytes = generate_certificate(
                        base_file.getvalue(),
                        font_bytes,
                        current_name,
                        name_style,
                        current_doc,
                        document_style,
                    )
                    safe_name = f"{index + 1:04d}_{slugify(current_name)}.png"
                    files.append((safe_name, image_bytes))
                    url = ""
                    if upload_enabled:
                        url = upload_to_cloudinary(
                            image_bytes,
                            cloud_folder,
                            public_id=f"{index + 1:04d}_{slugify(current_name)}",
                        )

                    rows.append(
                        {
                            "source_index": index,
                            "fila": index + 1,
                            "nombre": current_name,
                            "documento": current_doc,
                            "archivo": safe_name,
                            "certificado": url,
                        }
                    )
                except Exception as exc:
                    errors.append({"fila": index + 1, "nombre": current_name, "error": str(exc)})
                progress.progress((index + 1) / len(df))

            result_df = pd.DataFrame(rows)
            display_df = result_df.drop(columns=["source_index"], errors="ignore")
            csv_bytes = build_treble_output_csv(df, rows)
            files.append(("certificados_treble.csv", csv_bytes))
            zip_bytes = build_zip(files)
            saved_dir = None
            if save_local and rows:
                saved_dir = save_generation(rows, files, source_label)

            st.success(f"Listo: {len(rows)} certificados generados.")
            if saved_dir:
                st.info(f"Guardado en certificados_guardados/{saved_dir.name}")
            dl_cols = st.columns(2)
            dl_cols[0].download_button(
                "Descargar ZIP",
                data=zip_bytes,
                file_name="certificados_kinnto.zip",
                mime="application/zip",
                use_container_width=True,
            )
            dl_cols[1].download_button(
                "Descargar CSV Treble",
                data=csv_bytes,
                file_name="certificados_treble.csv",
                mime="text/csv",
                use_container_width=True,
            )
            if not display_df.empty:
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            if errors:
                st.warning(f"{len(errors)} filas no se pudieron procesar.")
                st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
