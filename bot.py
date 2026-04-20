import os
import re
import json
import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

TOKEN = "8713273501:AAEEbe9DQcJGwDAebvjTpllBBNVzPKMMvFg"

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)


def clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def get_user_command(text: str):
    text = clean_text(text)

    if text == "يوت":
        return "youtube", ""
    if text.startswith("يوت "):
        return "youtube", clean_text(text[4:])

    if text == "بحث":
        return "search", ""
    if text.startswith("بحث "):
        return "search", clean_text(text[4:])

    return None, None


async def run_command(command):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


async def search_youtube(query: str):
    command = [
        "yt-dlp",
        f"ytsearch1:{query}",
        "--dump-single-json",
        "--no-playlist",
        "--default-search", "ytsearch"
    ]

    code, out, err = await run_command(command)

    if code != 0 or not out.strip():
        return None

    data = json.loads(out)

    if "entries" in data and data["entries"]:
        entry = data["entries"][0]
    else:
        entry = data

    return {
        "title": entry.get("title", "بدون عنوان"),
        "url": entry.get("webpage_url", ""),
    }


async def download_audio(query: str):
    safe_name = re.sub(r"[^a-zA-Z0-9_\u0600-\u06FF]+", "_", query)[:40]
    output_template = str(DOWNLOAD_DIR / f"{safe_name}_%(id)s.%(ext)s")

    command = [
        "yt-dlp",
        f"ytsearch1:{query}",
        "--no-playlist",
        "--default-search", "ytsearch",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_template
    ]

    code, out, err = await run_command(command)

    if code != 0:
        raise Exception(err if err else "فشل التحميل")

    files = sorted(
        DOWNLOAD_DIR.glob(f"{safe_name}_*.mp3"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    if not files:
        raise Exception("ما انحفظ ملف الصوت")

    return files[0]


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    action, query = get_user_command(text)

    if not action:
        return

    if not query:
        if action == "search":
            await update.message.reply_text("اكتب هيج:\nبحث اسم الاغنية")
        elif action == "youtube":
            await update.message.reply_text("اكتب هيج:\nيوت اسم الاغنية")
        return

    if action == "search":
        try:
            result = await search_youtube(query)

            if not result:
                await update.message.reply_text("ما لكيت نتيجة")
                return

            await update.message.reply_text(
                f"{result['title']}\n{result['url']}"
            )

        except Exception:
            await update.message.reply_text("صار خطأ بالبحث")
        return

    if action == "youtube":
        waiting = await update.message.reply_text("دا أرسل الأغنية...")
        file_path = None

        try:
            result = await search_youtube(query)
            if not result:
                await waiting.edit_text("ما لكيت نتيجة")
                return

            title = result["title"]
            file_path = await download_audio(query)

            with open(file_path, "rb") as audio:
                await update.message.reply_audio(
                    audio=audio,
                    title=title
                )

            await waiting.delete()

        except Exception:
            await waiting.edit_text("صار خطأ أثناء التحميل")
        finally:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
